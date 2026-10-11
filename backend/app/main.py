"""AkariBot Studio 后端入口。

统一装配：Store(持久化) + EventBus(总线) + Adapters(双模式) + PluginManager(插件) + FastAPI。
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .bus import EventBus
from .store import Store
from .adapters.onebot import OneBotAdapter
from .adapters.qqofficial import QQOfficialAdapter
from .plugin.loader import PluginManager
from .plugin import store as plugin_store

HOME = os.path.expanduser("~/.akari-qqbot")
DATA_DIR = os.environ.get("AKARI_DATA_DIR", HOME)
PLUGINS_ROOT = os.path.join(DATA_DIR, "plugins")


def log(*a):
    print("[akari]", *a, flush=True)


class Runtime:
    def __init__(self) -> None:
        self.store = Store(os.path.join(DATA_DIR, "data.sqlite3"))
        self.bus = EventBus()
        self.adapters: dict[str, Any] = {}
        self.plugins = PluginManager(PLUGINS_ROOT, self.bus, log=log)
        self.plugins.set_send_callback(self.send_message)
        self.plugins.set_card_callback(self.send_card)
        self.plugins.set_bots_provider(self.list_bots_with_status)
        self.plugins.set_adapter_provider(lambda bid: self.adapters.get(bid))

    def list_bots_with_status(self) -> list[dict[str, Any]]:
        out = []
        for b in self.store.list_bots():
            ad = self.adapters.get(b["id"])
            out.append({**b, "status": ad.status() if ad else {"connected": False}})
        return out

    def make_adapter(self, bot: dict[str, Any]):
        return OneBotAdapter(bot, self.bus, log) if bot["mode"] == "onebot" else QQOfficialAdapter(bot, self.bus, log)

    async def start_bot(self, bot_id: str) -> dict[str, Any]:
        bot = self.store.get_bot(bot_id)
        if not bot:
            raise HTTPException(404, "bot not found")
        if bot_id in self.adapters:
            return self.adapters[bot_id].status()
        ad = self.make_adapter(bot)
        self.adapters[bot_id] = ad
        await ad.start()
        self.store.set_enabled(bot_id, True)
        return ad.status()

    async def stop_bot(self, bot_id: str) -> None:
        ad = self.adapters.pop(bot_id, None)
        if ad:
            await ad.stop()
        self.store.set_enabled(bot_id, False)

    async def send_message(self, bot_id: str, scene: str, peer_id: str, text: str,
                           markdown: bool = False, keyboard: Any = None) -> dict[str, Any]:
        from .adapters.base import OutgoingMessage
        ad = self.adapters.get(bot_id)
        if not ad:
            raise HTTPException(400, "该账号未启动")
        return await ad.send(OutgoingMessage(bot_id=bot_id, mode=ad.mode, scene=scene,
                                             peer_id=peer_id, text=text, markdown=markdown,
                                             keyboard=keyboard))

    async def send_card(self, bot_id: str, scene: str, peer_id: str, text: str,
                        keyboard: dict[str, Any]) -> dict[str, Any]:
        """发卡片消息（带按钮）。"""
        return await self.send_message(bot_id, scene, peer_id, text,
                                       markdown=True, keyboard=keyboard)

    async def on_bus_event(self, event: dict[str, Any]) -> None:
        # 把消息事件同时喂给插件钩子
        if event.get("type") == "message":
            await self.plugins.dispatch("message", event)

    async def boot(self) -> None:
        self.bus.register_hook(self.on_bus_event)
        self.plugins.load_all()
        for bot in self.store.list_bots():
            if bot["enabled"]:
                try:
                    await self.start_bot(bot["id"])
                except Exception as exc:
                    log(f"自动启动 {bot['id']} 失败：{exc}")

    async def shutdown(self) -> None:
        for bid in list(self.adapters):
            await self.stop_bot(bid)


rt = Runtime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rt.boot()
    yield
    await rt.shutdown()


app = FastAPI(title="AkariBot Studio", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------- REST ----------------
class BotIn(BaseModel):
    mode: str                      # onebot | qqofficial
    label: str = ""
    config: dict[str, Any] = {}


@app.get("/api/health")
async def health():
    return {"ok": True, "bots": len(rt.store.list_bots()), "plugins": len(rt.plugins.installed)}


@app.get("/api/bots")
async def list_bots():
    return rt.list_bots_with_status()


@app.post("/api/bots")
async def add_bot(body: BotIn):
    if body.mode not in ("onebot", "qqofficial"):
        return JSONResponse({"error": "账号模式不支持"}, status_code=400)
    if body.mode == "qqofficial":
        cfg = body.config or {}
        if not str(cfg.get("appid", "")).strip() or not str(cfg.get("secret", "")).strip():
            return JSONResponse({"error": "官方机器人必须填写 AppID 和 AppSecret"}, status_code=400)
    label = (body.label or "").strip() or ("官方机器人" if body.mode == "qqofficial" else "个人号")
    bot = rt.store.add_bot(body.mode, label, body.config or {})
    return bot


@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str):
    return await rt.start_bot(bot_id)


@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str):
    await rt.stop_bot(bot_id)
    return {"ok": True}


@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str):
    await rt.stop_bot(bot_id)
    rt.store.delete_bot(bot_id)
    return {"ok": True}


@app.post("/api/send")
async def send(body: dict[str, Any]):
    try:
        return await rt.send_message(
            body["bot_id"], body.get("scene", "group"), str(body["peer_id"]),
            body.get("text", ""), bool(body.get("markdown")))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


# ---------------- 插件 ----------------
@app.get("/api/plugins")
async def list_plugins():
    return {"installed": rt.plugins.info(), "registry": rt.store.list_plugins()}


@app.post("/api/plugins/scan")
async def scan_plugins(body: dict[str, Any]):
    """扫描一个 Git 仓库里有哪些插件（不安装）。"""
    repo = body.get("repo_url", "").strip()
    if not repo:
        raise HTTPException(400, "repo_url 必填")
    try:
        found = plugin_store.scan_repo(repo, log=log)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"repo": repo, "plugins": [{k: v for k, v in m.items() if not k.startswith("_")} | {"path": m.get("_path")} for m in found]}


@app.post("/api/plugins/install")
async def install_plugins(body: dict[str, Any]):
    """安装一个 Git 仓库下的全部插件。"""
    repo = body.get("repo_url", "").strip()
    if not repo:
        raise HTTPException(400, "repo_url 必填")
    try:
        installed = plugin_store.install_repo(repo, PLUGINS_ROOT, log=log)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    for m in installed:
        rt.store.upsert_plugin(m.get("name", ""), m.get("version", "0"), repo, m.get("_installed_path", ""))
        rt.plugins.load(m)
    return {"installed": [m.get("name") for m in installed]}


@app.get("/api/plugins/{name}/config")
async def get_plugin_config(name: str):
    meta = rt.plugins.installed.get(name)
    if not meta:
        return JSONResponse({"error": "插件不存在"}, status_code=404)
    return {"name": name,
            "schema": meta.get("config", []),
            "values": rt.plugins.load_config(name)}


@app.post("/api/plugins/{name}/config")
async def set_plugin_config(name: str, body: dict[str, Any]):
    if name not in rt.plugins.installed:
        return JSONResponse({"error": "插件不存在"}, status_code=404)
    rt.plugins.save_config(name, body or {})
    rt.plugins.reload(name)
    return {"ok": True, "name": name}


@app.get("/api/tools")
async def list_tools():
    """当前所有可被 AI 调用的工具。"""
    return {"tools": rt.plugins.tools()}


@app.post("/api/ai/ask")
async def ai_ask(body: dict[str, Any]):
    """调试用：直接跑一次 AI（含工具调用），返回回复 + 用了哪些工具。"""
    import httpx
    text = str(body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text 为空"}, status_code=400)
    c = rt.plugins.load_config("ai")
    base = (c.get("base") or "http://127.0.0.1:12111/v1").rstrip("/")
    model = c.get("model") or "qwen3.8-27b"
    key = c.get("key") or ""
    tools = rt.plugins.tools()
    msgs: list[dict] = [
        {"role": "system", "content": "你是助手。涉及实时信息（天气、状态）必须调用工具，不要编造。"},
        {"role": "user", "content": text}]
    used: list[str] = []
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    async with httpx.AsyncClient(timeout=90) as cli:
        for _ in range(4):
            payload: dict = {"model": model, "messages": msgs}
            if tools:
                payload["tools"] = tools
            r = await cli.post(f"{base}/chat/completions", headers=headers, json=payload)
            d = r.json()
            if not d.get("choices"):
                return JSONResponse({"error": str(d)[:300]}, status_code=502)
            m = d["choices"][0]["message"]
            calls = m.get("tool_calls") or []
            if not calls:
                return {"reply": (m.get("content") or "").strip(), "tools_used": used, "model": model}
            msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
            for tc in calls:
                fn = (tc.get("function") or {}).get("name", "")
                try:
                    args = json.loads((tc.get("function") or {}).get("arguments") or "{}")
                except Exception:
                    args = {}
                res = await rt.plugins.run_tool(fn, args)
                used.append(fn)
                msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(res)})
    return {"reply": "（步骤过多）", "tools_used": used, "model": model}


@app.post("/api/plugins/reload")
async def reload_plugins():
    """热重载所有插件（改了代码/配置不用重启后端）。"""
    names = list(rt.plugins.installed)
    for n in names:
        rt.plugins.reload(n)
    tools = [t["function"]["name"] for t in rt.plugins.tools()]
    return {"ok": True, "plugins": len(names), "tools": tools}


# ---------------- WebSocket ----------------
@app.websocket("/ws")
async def ws_frontend(ws: WebSocket):
    """前端订阅：接收 message / bot_status 事件。"""
    await ws.accept()
    q = rt.bus.subscribe()
    try:
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        rt.bus.unsubscribe(q)


@app.websocket("/onebot/v11/ws")
async def ws_onebot(ws: WebSocket, bot: str = ""):
    """NapCat（个人号）反向 WebSocket 接入点。"""
    await ws.accept()
    ad = rt.adapters.get(bot)
    if not isinstance(ad, OneBotAdapter):
        await ws.close(code=1008, reason="未知 bot_id")
        return
    await ad.handle_connection(ws)


# ---------------- 静态前端 ----------------
from fastapi.staticfiles import StaticFiles  # noqa: E402

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
# APK / 文件下载（必须在根挂载之前，否则被 catch-all 吃掉）
DL_DIR = os.environ.get("AKARI_DL_DIR", "/var/www/apk")
if os.path.isdir(DL_DIR):
    app.mount("/dl", StaticFiles(directory=DL_DIR), name="dl")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def main() -> None:
    import uvicorn
    port = int(os.environ.get("AKARI_PORT", "8099"))
    uvicorn.run(app, host=os.environ.get("AKARI_HOST", "127.0.0.1"), port=port)


if __name__ == "__main__":
    main()
