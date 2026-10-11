"""AI 对话插件。

配置在 App 的「插件 → 设置」里填（存 plugins/ai/config.json）：
  base / key / model / system —— 任意 OpenAI 兼容接口。
环境变量 AKARI_AI_* 作为兜底默认值。
触发：群里被 @、私聊、或以 ai/AI 开头。
"""
import os
import httpx

DEFAULTS = {
    "base": os.environ.get("AKARI_AI_BASE", "http://127.0.0.1:12111/v1"),
    "key": os.environ.get("AKARI_AI_KEY", ""),
    "model": os.environ.get("AKARI_AI_MODEL", "gpt-4o-mini"),
    "system": os.environ.get(
        "AKARI_AI_SYSTEM",
        "你是群聊里的一个活泼可爱的助手，说话简短自然、口语化，像真人聊天，不许用 markdown 和表情符号。",
    ),
}
HISTORY: dict[str, list] = {}


def register(api):
    def cfg() -> dict:
        c = api.config or {}
        return {k: (c.get(k) or DEFAULTS[k]) for k in DEFAULTS}

    async def ask(key: str, user_text: str) -> str:
        c = cfg()
        hist = HISTORY.setdefault(key, [])
        hist.append({"role": "user", "content": user_text})
        hist[:] = hist[-16:]
        payload = {"model": c["model"],
                   "messages": [{"role": "system", "content": c["system"]}] + hist,
                   "temperature": 0.8}
        headers = {"Content-Type": "application/json"}
        if c["key"]:
            headers["Authorization"] = f"Bearer {c['key']}"
        async with httpx.AsyncClient(timeout=60) as cli:
            r = await cli.post(f"{c['base'].rstrip('/')}/chat/completions", headers=headers, json=payload)
            d = r.json()
        reply = (d.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not reply:
            reply = f"（AI 没回应：{str(d)[:140]}）"
        hist.append({"role": "assistant", "content": reply})
        return reply

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if not text:
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
            reply = await ask(f"{d.get('bot_id')}:{d.get('scene')}:{d.get('peer_id')}", text)
        except Exception as exc:
            reply = f"（AI 暂时联系不上：{exc}）"
        await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
