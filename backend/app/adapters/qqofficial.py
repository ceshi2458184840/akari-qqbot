"""官方号适配器：QQ Bot API v2（AppID + AppSecret）。

用官方 SDK `qq-botpy` 建立 WebSocket 网关连接，REST 发消息。
只能收到 @机器人 的群消息 + 私聊（C2C）消息。
"""
from __future__ import annotations

import asyncio
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
            await self.adapter.bus.publish({"type": "bot_status", **self.adapter.status()})
            self.adapter.log(f"[qqofficial:{self.adapter.account_id}] 已上线：{self.robot.name}")

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

    async def _ingest_group(self, message) -> None:
        msg = IncomingMessage(
            bot_id=self.account_id, mode=self.mode, scene="group",
            peer_id=str(message.group_openid), sender_id=str(message.author.member_openid),
            sender_name="", text=(message.content or "").strip(), raw={}, message_id=str(message.id),
        )
        await self.bus.publish({"type": "message", "data": msg.__dict__})

    async def _ingest_c2c(self, message) -> None:
        msg = IncomingMessage(
            bot_id=self.account_id, mode=self.mode, scene="private",
            peer_id=str(message.author.user_openid), sender_id=str(message.author.user_openid),
            sender_name="", text=(message.content or "").strip(), raw={}, message_id=str(message.id),
        )
        await self.bus.publish({"type": "message", "data": msg.__dict__})

    async def send(self, msg: OutgoingMessage) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("官方号未启动")
        if msg.scene == "group":
            return await self._client.api.post_group_message(
                group_openid=msg.peer_id, msg_type=0, content=msg.text, msg_id=msg.reply_to)
        return await self._client.api.post_c2c_message(
            openid=msg.peer_id, msg_type=0, content=msg.text, msg_id=msg.reply_to)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        self.connected = False
