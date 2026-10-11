"""示例插件：/echo 复读。"""


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if text.startswith("/echo"):
            reply = text[len("/echo"):].strip() or "（空）"
            await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
