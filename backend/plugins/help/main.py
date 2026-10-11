"""帮助插件：/help —— 排版清晰的指令表。"""


def _pad(items):
    w = max((len(a) for a, _ in items), default=0)
    return [f"  {a.ljust(w)}   {b}" for a, b in items]


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if text not in ("/help", "帮助", "/帮助", "#help", "/菜单", "菜单"):
            return
        plugins = api.list_plugins() or []
        cmds = [
            ("/help", "打开这张指令表"),
            ("/status", "查看运行状态"),
            ("/ping", "测试机器人在不在"),
            ("/echo 内容", "复读一遍"),
            ("/天气 城市", "查询城市天气"),
            ("/禁言 60 @人", "群内禁言（管理员）"),
            ("/解禁 @人", "解除禁言（管理员）"),
            ("/群信息", "查看群资料"),
            ("@机器人", "直接聊天（AI 对话）"),
        ]
        body = "\n".join(_pad(cmds))
        names = "、".join(p.get("name", "?") for p in plugins) or "无"
        msg = ("╭─ AkariBot 指令 ─╮\n"
               f"{body}\n"
               "╰────────────────╯\n"
               f"已装插件（{len(plugins)}）：{names}")
        await api.send(d["bot_id"], d["scene"], d["peer_id"], msg)
