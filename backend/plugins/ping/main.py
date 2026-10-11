"""存活测试插件：/ping → pong。"""


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip().lower()
        if text in ("/ping", "ping"):
            await api.send(d["bot_id"], d["scene"], d["peer_id"], "pong")
