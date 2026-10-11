"""帮助插件：/help 列出所有可用指令与已装插件。"""


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if text not in ("/help", "帮助", "/帮助", "#help"):
            return
        plugins = api.list_plugins() or []
        lines = ["【AkariBot 指令】",
                 "· /help — 查看帮助",
                 "· /status — 运行状态",
                 "· /ping — 存活测试",
                 "· /echo 内容 — 复读"]
        if plugins:
            lines.append("")
            lines.append("已装插件：" + "、".join(p.get("name", "?") for p in plugins))
        await api.send(d["bot_id"], d["scene"], d["peer_id"], "\n".join(lines))
