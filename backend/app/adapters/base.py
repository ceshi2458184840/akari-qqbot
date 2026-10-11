"""统一数据结构 + 适配器抽象。

不管底层是 OneBot（个人号）还是 QQ 官方 API，上层只认这套结构。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IncomingMessage:
    """一条进来的消息（已归一化）。"""
    bot_id: str              # 属于哪个已配置账号（AccountEntry.id）
    mode: str                # "onebot" | "qqofficial"
    scene: str               # "group" | "private"
    peer_id: str             # 群号 / 用户号（个人号是 QQ 号；官方号是 openid）
    sender_id: str
    sender_name: str = ""
    sender_avatar: str = ""
    peer_name: str = ""
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""


@dataclass
class OutgoingMessage:
    """要发出去的消息。"""
    bot_id: str
    mode: str
    scene: str
    peer_id: str
    text: str
    reply_to: Optional[str] = None
    markdown: bool = False
    keyboard: Any = None


class BaseAdapter:
    """所有适配器的父类。"""

    mode = "base"

    def __init__(self, account: dict[str, Any], bus, log=print):
        self.account = account
        self.account_id: str = account.get("id", "")
        self.bus = bus
        self.log = log
        self.connected = False

    async def start(self) -> None:      # noqa: D401
        raise NotImplementedError

    async def stop(self) -> None:       # noqa: D401
        raise NotImplementedError

    async def send(self, msg: OutgoingMessage) -> dict[str, Any]:  # noqa: D401
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {"id": self.account_id, "mode": self.mode, "connected": self.connected,
                "name": getattr(self, "bot_name", ""), "avatar": getattr(self, "bot_avatar", "")}
