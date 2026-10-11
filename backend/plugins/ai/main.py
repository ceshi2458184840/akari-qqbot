"""AI 对话插件。

配置（环境变量，改 systemd 的 Environment 即可）：
  AKARI_AI_BASE   默认 http://127.0.0.1:12111/v1
  AKARI_AI_KEY    默认空
  AKARI_AI_MODEL  默认 gpt-4o-mini
触发：群里被 @（官方号天然只推 @ 消息）、私聊、或以 ai/AI 开头。
"""
import os
import httpx

BASE = os.environ.get("AKARI_AI_BASE", "http://127.0.0.1:12111/v1").rstrip("/")
KEY = os.environ.get("AKARI_AI_KEY", "")
MODEL = os.environ.get("AKARI_AI_MODEL", "gpt-4o-mini")
SYSTEM = os.environ.get(
    "AKARI_AI_SYSTEM",
    "你是群聊里的一个活泼可爱的助手，说话简短自然、口语化，像真人聊天，不许用 markdown 和表情符号。",
)
HISTORY: dict[str, list] = {}   # 会话历史（内存，最多 8 轮）


async def _ask(key: str, user_text: str) -> str:
    hist = HISTORY.setdefault(key, [])
    hist.append({"role": "user", "content": user_text})
    hist[:] = hist[-16:]
    payload = {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM}] + hist, "temperature": 0.8}
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/chat/completions", headers=headers, json=payload)
        d = r.json()
    reply = (d.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    hist.append({"role": "assistant", "content": reply})
    return reply or "（我这边没组织好语言…再问一次？）"


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if not text:
            return
        scene = d.get("scene")
        # 群里只回应「被 @」或 ai 开头
        if scene == "group":
            raw = d.get("raw") or {}
            mentioned = any(
                seg.get("type") == "at" and str(seg.get("data", {}).get("qq")) in ("all", str(raw.get("self_id", "")))
                for seg in (raw.get("message") or []) if isinstance(seg, dict)
            ) if isinstance(raw.get("message"), list) else ("@" in text)
            if not (mentioned or text.lower().startswith("ai")):
                return
            text = text.replace("AI", "").replace("ai", "").strip() or "你好呀"
        try:
            reply = await _ask(f"{d.get('bot_id')}:{d.get('scene')}:{d.get('peer_id')}", text)
        except Exception as exc:
            reply = f"（AI 暂时联系不上：{exc}）"
        await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
