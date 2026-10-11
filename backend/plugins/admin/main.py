"""群聊管理插件（官方号走 botpy REST，自动带/刷新 token）。

指令：
  /禁言 60 @某人     禁言 N 秒（默认 60）
  /解禁 @某人        解除禁言
  /群信息            查看群基本信息
  /群管              指令说明

注意：机器人必须是该群管理员，否则腾讯会拒绝（错误会原样告诉你）。
"""


async def _rest(ad, method, path, params=None, **kw):
    return await ad.rest(method, path, route_params=params or {}, **kw)


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        if d.get("scene") != "group":
            return
        text = (d.get("text") or "").strip()
        raw = d.get("raw") or {}
        mentions = [m for m in (raw.get("mentions") or []) if m]
        group, bot_id = d.get("peer_id"), d.get("bot_id")

        async def say(t):
            await api.send(bot_id, "group", group, t)

        ad = api.get_adapter(bot_id)
        if ad is None or not hasattr(ad, "rest"):
            return   # 只处理官方号

        # ---- 说明 ----
        if text in ("/群管", "/群管帮助", "/admin"):
            await say("【群管指令】\n"
                      "  /禁言 60 @某人   禁言 N 秒\n"
                      "  /解禁 @某人      解除禁言\n"
                      "  /群信息          查看群资料\n"
                      "※ 机器人需要是群管理员")
            return

        # ---- 群信息（腾讯未开放该接口）----
        if text in ("/群信息", "/群info", "/groupinfo"):
            await say("QQ 官方机器人接口没有开放「查询群资料」。\n"
                      "能用的是：/禁言、/解禁（需机器人是群管理员）。")
            return

        # ---- 禁言 / 解禁 ----
        if text.startswith(("/禁言", "/mute", "/解禁", "/unmute")):
            unmute = text.startswith(("/解禁", "/unmute"))
            if not mentions:
                await say("请 @ 目标成员，例如：/禁言 60 @某人")
                return
            try:
                if unmute:
                    await _rest(ad, "POST", "/v2/groups/{group_openid}/restrict_chat_setting",
                                {"group_openid": group},
                                json={"op": "remove", "members": [{"member_openid": mentions[0]}]})
                    await say("已解除禁言 ✅")
                else:
                    seconds = 60
                    for part in text.split():
                        if part.isdigit() and int(part) <= 2592000:
                            seconds = int(part)
                            break
                    await _rest(ad, "POST", "/v2/groups/{group_openid}/restrict_chat_setting",
                                {"group_openid": group},
                                json={"op": "add", "members": [
                                    {"member_openid": mentions[0], "mute_seconds": str(seconds)}]})
                    await say(f"已禁言 {seconds} 秒 ✅")
            except Exception as exc:
                msg = str(exc)
                tip = "\n（多半是机器人不是群管理员，或没这个权限——去群里把它设为管理员）" \
                    if any(k in msg for k in ("403", "11253", "权限", "forbidden")) else ""
                await say(f"操作失败：{msg[:150]}{tip}")
            return
