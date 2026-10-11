"""AI 对话插件（带工具调用 / function calling）。

配置在 App 的「插件 → 设置」里填（存 plugins/ai/config.json）：
  base / key / model / system / max_steps —— 任意 OpenAI 兼容接口。
能力：自动获得所有插件注册的工具（查天气、看状态等），会自己调用，不瞎编。
环境变量 AKARI_AI_* 作为兜底默认值。
触发：群里被 @、私聊、或以 ai/AI 开头。
"""
import json
import os
import httpx

DEFAULTS = {
    "base": os.environ.get("AKARI_AI_BASE", "http://127.0.0.1:12111/v1"),
    "key": os.environ.get("AKARI_AI_KEY", ""),
    "model": os.environ.get("AKARI_AI_MODEL", "qwen3.8-27b"),
    "system": os.environ.get(
        "AKARI_AI_SYSTEM",
        "你是群聊里的一个活泼可爱的助手，说话简短自然、口语化，像真人聊天。"
        "你有一批工具可以调用（查天气、查询机器人状态等）；涉及实时信息时必须调用工具，"
        "不要凭记忆编造、也不要假装调用。回复里不要出现 markdown 语法。",
    ),
    "max_steps": os.environ.get("AKARI_AI_MAX_STEPS", "4"),
}
HISTORY: dict[str, list] = {}


def register(api):
    def cfg() -> dict:
        c = api.config or {}
        return {k: (c.get(k) or DEFAULTS[k]) for k in DEFAULTS}

    def _headers(c: dict) -> dict:
        h = {"Content-Type": "application/json"}
        if c["key"]:
            h["Authorization"] = f"Bearer {c['key']}"
        return h

    async def chat(key: str, user_text: str) -> str:
        c = cfg()
        tools = api.tools()
        hist = HISTORY.setdefault(key, [])
        hist.append({"role": "user", "content": user_text})
        hist[:] = hist[-16:]

        sys_prompt = c["system"]
        if tools:
            names = "、".join(t["function"]["name"] for t in tools)
            sys_prompt += f"\n当前可用工具：{names}。需要实时数据时必须调用。"

        messages: list[dict] = [{"role": "system", "content": sys_prompt}] + list(hist)
        base = c["base"].rstrip("/")
        try:
            steps = int(c.get("max_steps") or 4)
        except Exception:
            steps = 4

        async with httpx.AsyncClient(timeout=90) as cli:
            for _ in range(steps):
                payload: dict = {"model": c["model"], "messages": messages, "temperature": 0.8}
                if tools:
                    payload["tools"] = tools
                try:
                    r = await cli.post(f"{base}/chat/completions", headers=_headers(c), json=payload)
                    d = r.json()
                except Exception as exc:
                    return f"（AI 接口连不上：{exc}）"
                if not d.get("choices"):
                    err = d.get("error") or d
                    return f"（AI 没回应：{str(err)[:140]}）"
                m = d["choices"][0].get("message", {})
                calls = m.get("tool_calls") or []
                if not calls:
                    reply = (m.get("content") or "").strip() or "（我没想好说什么…）"
                    hist.append({"role": "assistant", "content": reply})
                    hist[:] = hist[-16:]
                    return reply
                messages.append({"role": "assistant", "content": m.get("content") or "",
                                 "tool_calls": calls})
                for tc in calls:
                    fn = (tc.get("function") or {}).get("name", "")
                    raw = (tc.get("function") or {}).get("arguments") or "{}"
                    try:
                        args = json.loads(raw)
                    except Exception:
                        args = {}
                    result = await api.run_tool(fn, args)
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                     "content": str(result)})
            return "（想得有点久，先这样吧～）"

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if not text or text.startswith("btn:") or text.startswith("/"):
            return
        if d.get("scene") == "group":
            raw = d.get("raw") or {}
            mentions = raw.get("mentions") or []
            if not (mentions or "@" in text or text.lower().startswith("ai")):
                return
            text = text.replace("@", "").strip()
            if text.lower().startswith("ai"):
                text = text[2:].strip()
            text = text or "你好呀"
        try:
            reply = await chat(f"{d.get('bot_id')}:{d.get('scene')}:{d.get('peer_id')}", text)
        except Exception as exc:
            reply = f"（AI 暂时联系不上：{exc}）"
        await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
