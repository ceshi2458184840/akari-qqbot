"""官方号适配器：QQ Bot API v2（AppID + AppSecret）。

用官方 SDK `qq-botpy` 建立 WebSocket 网关连接，REST 发消息。
只能收到 @机器人 的群消息 + 私聊（C2C）消息。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .base import BaseAdapter, IncomingMessage, OutgoingMessage

try:
    import botpy  # type: ignore
    from botpy.message import C2CMessage, GroupMessage  # type: ignore
    BOTPY_OK = True
except Exception:  # SDK 未装时不至于整个后端起不来
    BOTPY_OK = False


if BOTPY_OK:

    class _Client(botpy.Client):  # type: ignore[misc]
        def __init__(self, adapter: "QQOfficialAdapter", **kw: Any):
            super().__init__(**kw)
            self.adapter = adapter

        async def on_ready(self):
            self.adapter.connected = True
            try:
                self.adapter.bot_name = getattr(self.robot, "name", "") or ""
                self.adapter.bot_avatar = getattr(self.robot, "avatar", "") or ""
            except Exception:
                pass
            await self.adapter.bus.publish({"type": "bot_status", **self.adapter.status()})
            self.adapter.log(f"[qqofficial:{self.adapter.account_id}] 已上线：{getattr(self.robot, 'name', '?')}")

        async def on_group_at_message_create(self, message: "GroupMessage"):
            await self.adapter._ingest_group(message)

        async def on_c2c_message_create(self, message: "C2CMessage"):
            await self.adapter._ingest_c2c(message)


class QQOfficialAdapter(BaseAdapter):
    mode = "qqofficial"

    def __init__(self, account: dict[str, Any], bus, log=print):
        super().__init__(account, bus, log)
        cfg = account.get("config", {})
        self.appid: str = str(cfg.get("appid", ""))
        self.secret: str = str(cfg.get("secret", ""))
        self.sandbox: bool = bool(cfg.get("sandbox", False))
        self._client = None
        self._task: asyncio.Task | None = None
        self.bot_name = ""
        self.bot_avatar = ""
        # 被动回复上下文：peer_key -> {"id": 最近收到的 msg_id, "ts": 时间, "seq": 已回复次数}
        self._recent: dict[str, dict[str, Any]] = {}

    # ---- 被动回复：官方 API 要求回复带 msg_id 且在 5 分钟窗口内 ----
    def _remember(self, scene: str, peer: str, msg_id: str) -> None:
        if msg_id:
            self._recent[f"{scene}:{peer}"] = {"id": msg_id, "ts": time.time(), "seq": 0}

    def _reply_ctx(self, scene: str, peer: str) -> tuple[str | None, int]:
        rec = self._recent.get(f"{scene}:{peer}")
        if not rec:
            return None, 1
        if time.time() - rec["ts"] > 280:      # 超过窗口只能发主动消息（配额受限）
            return None, 1
        rec["seq"] += 1
        if rec["seq"] > 5:                     # 同一 msg_id 最多回 5 条
            return None, 1
        return rec["id"], rec["seq"]

    async def start(self) -> None:
        if not BOTPY_OK:
            self.log(f"[qqofficial:{self.account_id}] 未安装 qq-botpy，跳过（pip install qq-botpy）")
            return
        if not self.appid or not self.secret:
            self.log(f"[qqofficial:{self.account_id}] 缺少 appid/secret")
            return
        intents = botpy.Intents(public_messages=True)
        self._client = _Client(self, intents=intents, is_sandbox=self.sandbox)
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await self._client.start(appid=self.appid, secret=self.secret)
        except Exception as exc:
            self.log(f"[qqofficial:{self.account_id}] 启动失败：{exc}")
            self.connected = False

    async def _user_info(self, openid: str) -> dict[str, Any]:
        """调官方 API 拿用户昵称/头像（失败则返回空，不阻塞消息）。"""
        try:
            token = None
            api = getattr(self._client, "api", None)
            for attr in ("token", "_token", "access_token"):
                token = getattr(api, attr, None) or getattr(self._client, attr, None)
                if token:
                    break
            if not token:
                return {}
            import httpx
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.get(
                    f"https://api.sgroup.qq.com/v2/users/{openid}",
                    headers={"Authorization": f"QQBot {token}", "X-Union-Appid": self.appid},
                )
                if r.status_code == 200:
                    d = r.json()
                    return {"name": d.get("username", ""), "avatar": d.get("avatar", "")}
        except Exception as exc:
            self.log(f"[qqofficial:{self.account_id}] 获取用户信息失败：{exc}")
        return {}

    async def _ingest_group(self, message) -> None:
        openid = str(message.author.member_openid)
        self._remember("group", str(message.group_openid), str(message.id))
        info = await self._user_info(openid)
        mentions = []
        try:
            for m in (getattr(message, "mentions", None) or []):
                mentions.append(str(getattr(m, "id", "") or getattr(m, "member_openid", "")))
        except Exception:
            pass
        raw = {"group_openid": str(message.group_openid), "member_openid": openid,
               "mentions": [x for x in mentions if x],
               "message_type": "group"}
        msg = IncomingMessage(
            bot_id=self.account_id, mode=self.mode, scene="group",
            peer_id=str(message.group_openid), sender_id=openid,
            sender_name=info.get("name") or openid[-6:],
            sender_avatar=info.get("avatar", ""),
            text=(message.content or "").strip(), raw=raw, message_id=str(message.id),
        )
        await self.bus.publish({"type": "message", "data": msg.__dict__})

    async def _ingest_c2c(self, message) -> None:
        openid = str(message.author.user_openid)
        self._remember("private", openid, str(message.id))
        info = await self._user_info(openid)
        msg = IncomingMessage(
            bot_id=self.account_id, mode=self.mode, scene="private",
            peer_id=openid, sender_id=openid,
            sender_name=info.get("name") or openid[-6:],
            sender_avatar=info.get("avatar", ""),
            text=(message.content or "").strip(), raw={}, message_id=str(message.id),
        )
        await self.bus.publish({"type": "message", "data": msg.__dict__})

    async def send(self, msg: OutgoingMessage) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("官方号未启动")
        reply_id, seq = self._reply_ctx(msg.scene, msg.peer_id)
        if msg.reply_to:
            reply_id = msg.reply_to
        md = None
        if msg.markdown:
            try:
                from botpy.types.message import MarkdownPayload
                md = MarkdownPayload(content=msg.text)
            except Exception:
                md = {"content": msg.text}
        kwargs: dict[str, Any] = {"msg_type": 2 if md else 0, "content": msg.text,
                                  "msg_id": reply_id, "msg_seq": seq, "markdown": md}
        if msg.scene == "group":
            return await self._client.api.post_group_message(group_openid=msg.peer_id, **kwargs)
        return await self._client.api.post_c2c_message(openid=msg.peer_id, **kwargs)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        self.connected = False
