"""卡片 / 按钮消息插件。

发送「菜单」→ 机器人回一张带按钮的卡片。
按钮默认是「指令型」(action.type=2)：点一下把命令填进输入框，回车即执行——
不需要在开放平台配回调地址，最稳。

想用「回调型」（点一下机器人立刻应答）就把配置 button_mode 改成 callback，
但那需要在 QQ 开放平台配好事件回调地址，否则客户端会提示「请求第三方失败」。
数据：每行两个按钮，第二个元素既是显示的命令也是回调数据。
"""
import httpx

BUTTONS = [
    [("查天气", "/天气 北京"), ("现在几点", "/时间")],
    [("运行状态", "/status"), ("看技能", "/help")],
]


def _keyboard(mode: str = "command") -> dict:
    rows = []
    for row in BUTTONS:
        btns = []
        for i, (label, data) in enumerate(row):
            act = {"type": 1 if mode == "callback" else 2, "permission": {"type": 2},
                   "data": data, "unsupport_tips": "请升级到最新版 QQ"}
            btns.append({
                "id": f"b{i}_{abs(hash(data)) % 9999}",
                "render_data": {"label": label, "visited_label": label, "style": 1 if i == 0 else 0},
                "action": act,
            })
        rows.append({"buttons": btns})
    return {"content": {"rows": rows}}


def register(api):
    def mode() -> str:
        return (api.config or {}).get("button_mode") or "command"

    async def _weather(city="北京"):
        url = f"https://wttr.in/{city}?format=j1&lang=zh"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, headers={"User-Agent": "curl/8"})
            d = r.json()
        cur = (d.get("current_condition") or [{}])[0]
        desc = ((cur.get("lang_zh") or cur.get("weatherDesc") or [{}])[0].get("value")) or ""
        return f"{city}：{desc} {cur.get('temp_C','?')}℃（体感 {cur.get('FeelsLikeC','?')}℃）"

    async def _handle(d, action):
        if action.startswith("/"):
            return None                     # 指令型数据：交回正常指令流程
        if "天气" in action:
            try:
                return await _weather("北京")
            except Exception as exc:
                return f"查天气失败了：{exc}"
        if action == "status":
            return await api.run_tool("get_bot_status", {})
        if action == "plugins":
            return await api.run_tool("list_plugins", {})
        return f"收到按钮：{action}"

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()

        # 1) 回调型按钮点击
        if text.startswith("btn:"):
            reply = await _handle(d, text[4:].strip())
            if reply:
                await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
            return

        # 2) 触发卡片
        if text in ("菜单", "/菜单", "/卡片", "卡片", "/card"):
            title = (api.config or {}).get("title") or "AkariBot 功能菜单 · 点按钮试试"
            msg = await api.send_card(d["bot_id"], d["scene"], d["peer_id"],
                                      title, _keyboard(mode()), fallback=True)
            if msg is None:
                await api.send(d["bot_id"], d["scene"], d["peer_id"],
                               "卡片发不出来（机器人可能没有卡片 / Markdown 权限）。\n"
                               "可用指令：/天气 城市、/时间、/status、/help")
