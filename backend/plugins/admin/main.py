"""群聊管理插件（官方号走 REST）。

指令（需机器人为群管理员）：
  /禁言 60 @某人     禁言 N 秒（默认 60）
  /解禁 @某人        解除禁言
  /群信息            查看群基本信息
"""
import httpx

API = "https://api.sgroup.qq.com"


def _token(ad):
    cli = getattr(ad, "_client", None)
    api = getattr(cli, "api", None)
    for src in (api, cli):
        for a in ("token", "_token", "access_token"):
            t = getattr(src, a, None) if src else None
            if t:
                return t
    return None


def _headers(ad, tok):
    return {"Authorization": f"QQBot {tok}", "X-Union-Appid": getattr(ad, "appid", ""),
            "Content-Type": "application/json"}


def register(api):
    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        if d.get("scene") != "group":
            return
        text = (d.get("text") or "").strip()
        raw = d.get("raw") or {}
        mentions = [m for m in (raw.get("mentions") or []) if m]
        group = d.get("peer_id")
        ad = api.get_adapter(d.get("bot_id"))
        if ad is None or not hasattr(ad, "appid"):
            return
        tok = _token(ad)
        if not tok:
            return

        # ---- 禁言 ----
        if text.startswith("/禁言") or text.startswith("/mute"):
            seconds = 60
            for part in text.split():
                if part.isdigit():
                    seconds = int(part)
                    break
            if not mentions:
                await api.send(d["bot_id"], "group", group, "请 @ 要禁言的成员，例如：/禁言 60 @某人")
                return
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(
                        f"{API}/v2/groups/{group}/restrict_chat_setting",
                        headers=_headers(ad, tok),
                        json={"op": "add", "members": [
                            {"member_openid": mentions[0], "mute_seconds": str(seconds)}]},
                    )
                ok = r.status_code < 300 and r.json().get("err_code", 0) == 0
                await api.send(d["bot_id"], "group", group,
                               f"已禁言 {seconds} 秒" if ok else f"禁言失败：{r.text[:120]}")
            except Exception as exc:
                await api.send(d["bot_id"], "group", group, f"禁言出错：{exc}")
            return

        # ---- 解禁 ----
        if text.startswith("/解禁") or text.startswith("/unmute"):
            if not mentions:
                await api.send(d["bot_id"], "group", group, "请 @ 要解禁的成员，例如：/解禁 @某人")
                return
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(
                        f"{API}/v2/groups/{group}/restrict_chat_setting",
                        headers=_headers(ad, tok),
                        json={"op": "remove", "members": [{"member_openid": mentions[0]}]},
                    )
                ok = r.status_code < 300 and r.json().get("err_code", 0) == 0
                await api.send(d["bot_id"], "group", group, "已解除禁言" if ok else f"解禁失败：{r.text[:120]}")
            except Exception as exc:
                await api.send(d["bot_id"], "group", group, f"解禁出错：{exc}")
            return

        # ---- 群信息 ----
        if text in ("/群信息", "/群info", "/groupinfo"):
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{API}/v2/groups/{group}/info", headers=_headers(ad, tok))
                j = r.json()
                await api.send(d["bot_id"], "group", group,
                               f"【群信息】\n群名：{j.get('group_name', '?')}\n成员数：{j.get('member_count', '?')}\n群号：{j.get('group_code') or '未公开'}")
            except Exception as exc:
                await api.send(d["bot_id"], "group", group, f"查询失败：{exc}")
            return
