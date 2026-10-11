"""状态插件：/status 汇报运行状态。"""
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
        online = [b for b in bots if (b.get("status") or {}).get("connected")]
        up = int(time.time() - START)
        h, m = up // 3600, (up % 3600) // 60
        msg = (
            "【AkariBot 运行状态】\n"
            f"账号：{len(online)}/{len(bots)} 在线\n"
            f"插件：{len(api.list_plugins() or [])} 个\n"
            f"在线时长：{h} 小时 {m} 分"
        )
        await api.send(d["bot_id"], d["scene"], d["peer_id"], msg)
