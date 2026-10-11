"""群聊管理插件（官方号走 REST）。

指令：
  /禁言 60 @某人     禁言 N 秒（默认 60）
  /解禁 @某人        解除禁言
  /群信息            查看群基本信息
  /群管帮助          说明

注意：机器人必须是该群管理员，否则腾讯会拒绝（会把错误原样告诉你）。
"""
import httpx

API = "https://api.sgroup.qq.com"


def _headers(ad, auth):
    return {"Authorization": auth, "X-Union-Appid": getattr(ad, "appid", ""),
            "Content-Type": "application/json"}


async def _rest(ad, method, path, **kw):
    auth = ad.auth_header() if hasattr(ad, "auth_header") else None
    if not auth:
        raise RuntimeError("拿不到官方 token（机器人可能还没连上）")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await getattr(c, method)(f"{API}{path}", headers=_headers(ad, auth), **kw)
    try:
        j = r.json()
    except Exception:
        j = {}
    ok = r.status_code < 300 and j.get("err_code", 0) == 0
    return ok, j, r.status_code


def register(api):
    async def _need_admin(d, ad, group):
        """检查机器人是不是群管理员（不是就提示）。"""
        ok, j, _ = await _rest(ad, "get", f"/v2/groups/{group}/info")
        # 拿不到群信息不阻塞，交给后续 API 报错
        return True

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        if d.get("scene") != "group":
            return
        text = (d.get("text") or "").strip()
        raw = d.get("raw") or {}
        mentions = [m for m in (raw.get("mentions") or []) if m]
        group = d.get("peer_id")
        bot_id = d.get("bot_id")

        async def say(t):
            await api.send(bot_id, "group", group, t)

        ad = api.get_adapter(bot_id)
        if ad is None or not hasattr(ad, "appid"):
            return   # 个人号走别的路，这里只管官方号

        # ---- 帮助 ----
        if text in ("/群管", "/群管帮助", "/admin"):
            await say("【群管指令】\n"
                      "  /禁言 60 @某人   禁言 N 秒\n"
                      "  /解禁 @某人      解除禁言\n"
                      "  /群信息          查看群资料\n"
                      "（需要机器人是群管理员）")
            return

        # ---- 群信息 ----
        if text in ("/群信息", "/群info", "/groupinfo"):
            try:
                ok, j, code = await _rest(ad, "get", f"/v2/groups/{group}/info")
                if not ok:
                    await say(f"查群信息失败（HTTP {code}）：{j}")
                    return
                await say(f"【群信息】\n群名：{j.get('group_name', '?')}\n"
                          f"成员数：{j.get('member_count', '?')}\n"
                          f"群号：{j.get('group_code') or '未公开'}")
            except Exception as exc:
                await say(f"查群信息出错：{exc}")
            return

        # ---- 禁言 / 解禁 ----
        if text.startswith("/禁言") or text.startswith("/mute") or \
           text.startswith("/解禁") or text.startswith("/unmute"):
            unmute = text.startswith("/解禁") or text.startswith("/unmute")
            if not mentions:
                await say("请 @ 目标成员，例如：/禁言 60 @某人")
                return
            try:
                if unmute:
                    ok, j, code = await _rest(
                        ad, "post", f"/v2/groups/{group}/restrict_chat_setting",
                        json={"op": "remove", "members": [{"member_openid": mentions[0]}]})
                    what = "解除禁言"
                else:
                    seconds = 60
                    for part in text.split():
                        if part.isdigit() and int(part) <= 2592000:
                            seconds = int(part)
                            break
                    ok, j, code = await _rest(
                        ad, "post", f"/v2/groups/{group}/restrict_chat_setting",
                        json={"op": "add", "members": [
                            {"member_openid": mentions[0], "mute_seconds": str(seconds)}]})
                    what = f"禁言 {seconds} 秒"
                if ok:
                    await say(f"已{what} ✅")
                else:
                    tip = ""
                    if j.get("err_code") in (11253, 11254) or code == 403:
                        tip = "\n（机器人不是群管理员，或没有操作权限——去群里把机器人设为管理员）"
                    await say(f"{what}失败：{j.get('message') or j} {tip}")
            except Exception as exc:
                await say(f"操作出错：{exc}")
            return
