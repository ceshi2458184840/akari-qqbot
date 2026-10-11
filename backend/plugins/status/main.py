"""状态插件：/status —— 卡片式状态汇报。"""
import time

START = time.time()


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        if text not in ("/status", "状态", "/状态", "#status"):
            return
        bots = api.get_bots() or []
        plugins = api.list_plugins() or []
        online = [b for b in bots if (b.get("status") or {}).get("connected")]
        up = int(time.time() - START)
        h, m = up // 3600, (up % 3600) // 60
        lines = ["╭─ AkariBot 状态 ─╮",
                 f"  账号     {len(online)}/{len(bots)} 在线",
                 f"  插件     {len(plugins)} 个",
                 f"  运行     {h} 小时 {m} 分"]
        for b in bots:
            st = b.get("status") or {}
            lines.append(f"  {'●' if st.get('connected') else '○'} {st.get('name') or b.get('label')}")
        lines.append("╰────────────────╯")
        await api.send(d["bot_id"], d["scene"], d["peer_id"], "\n".join(lines))
