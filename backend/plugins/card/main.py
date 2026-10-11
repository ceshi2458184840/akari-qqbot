"""卡片 / 按钮消息插件。

发送「菜单」/「/卡片」→ 机器人回一张带按钮的卡片。
点按钮（回调型 action.type=1）→ 触发 interaction → 转成 `btn:<data>` 事件 → 这里响应。

按钮编排集中在 BUTTONS：data 是动作名，处理器在 _handle 里。
"""
import httpx

BUTTONS = [
    [("查天气", "weather"), ("运行状态", "status")],
    [("看看插件", "plugins"), ("打招呼", "hi")],
]


def _keyboard() -> dict:
    rows = []
    for row in BUTTONS:
        btns = []
        for i, (label, data) in enumerate(row):
            btns.append({
                "id": f"{data}_{i}",
                "render_data": {"label": label, "visited_label": label, "style": 1 if i == 0 else 0},
                "action": {"type": 1, "permission": {"type": 2}, "data": data,
                           "unsupport_tips": "请升级到最新版 QQ"},
            })
        rows.append({"buttons": btns})
    return {"content": {"rows": rows}}


def register(api):
    async def _weather(city="北京"):
        url = f"https://wttr.in/{city}?format=j1&lang=zh"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, headers={"User-Agent": "curl/8"})
            d = r.json()
        cur = (d.get("current_condition") or [{}])[0]
        desc = ((cur.get("lang_zh") or cur.get("weatherDesc") or [{}])[0].get("value")) or ""
        return f"{city}：{desc} {cur.get('temp_C','?')}℃（体感 {cur.get('FeelsLikeC','?')}℃）"

    async def _handle(api_, d, action):
        scene, bot_id, peer = d.get("scene"), d["bot_id"], d["peer_id"]
        if action == "weather":
            try:
                return await _weather("北京")
            except Exception as exc:
                return f"查天气失败了：{exc}"
        if action == "status":
            return await api.run_tool("get_bot_status", {})
        if action == "plugins":
            return await api.run_tool("list_plugins", {})
        if action == "hi":
            return "嗨～我在的，有什么需要尽管说！"
        return f"收到按钮：{action}"

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()

        # 1) 按钮回调
        if text.startswith("btn:"):
            await api.send(d["bot_id"], d["scene"], d["peer_id"],
                           await _handle(api, d, text[4:].strip()))
            return

        # 2) 触发卡片
        if text in ("菜单", "/菜单", "/卡片", "卡片", "/card"):
            title = (api.config or {}).get("title") or "AkariBot 功能菜单"
            try:
                msg = await api.send_card(d["bot_id"], d["scene"], d["peer_id"],
                                          title, _keyboard(), fallback=True)
                if msg is not None:
                    return
            except Exception as exc:
                api.log(f"[card] 卡片发送失败，降级纯文本：{exc}")
            await api.send(d["bot_id"], d["scene"], d["peer_id"],
                           "卡片发不出来（可能机器人没开通卡片权限）。\n"
                           "可用指令：/天气 城市、/status、/help")
