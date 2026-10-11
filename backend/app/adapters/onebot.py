"""个人号适配器：OneBot v11 反向 WebSocket（对接 NapCat / Lagrange）。

NapCat 登录个人 QQ 号后，把它配置成「反向 WebSocket 客户端」连到这里，
我们用标准 OneBot v11 收发消息。
"""
from __future__ import annotations

import json
from typing import Any

from .base import BaseAdapter, IncomingMessage, OutgoingMessage


class OneBotAdapter(BaseAdapter):
    mode = "onebot"

    def __init__(self, account: dict[str, Any], bus, log=print):
        super().__init__(account, bus, log)
        cfg = account.get("config", {})
        self.token: str = str(cfg.get("token", "") or "")
        self._ws = None
        self._echo = 0

    # ---- NapCat 连进来时由 main.py 调用 ----
    async def handle_connection(self, websocket) -> None:
        # 简单鉴权：OneBot 规范把 token 放在 Authorization: Bearer <token>
        if self.token:
            auth = websocket.headers.get("authorization", "")
            if auth != f"Bearer {self.token}":
                await websocket.close(code=1008, reason="bad token")
                self.log(f"[onebot:{self.account_id}] token 校验失败，已拒绝连接")
                return
        self._ws = websocket
        self.connected = True
        await self.bus.publish({"type": "bot_status", **self.status()})
        self.log(f"[onebot:{self.account_id}] NapCat 已连入")
        try:
            async for raw in websocket.iter_text():
                try:
                    evt = json.loads(raw)
                except Exception:
                    continue
                await self._on_event(evt)
        finally:
            self.connected = False
            self._ws = None
            await self.bus.publish({"type": "bot_status", **self.status()})
            self.log(f"[onebot:{self.account_id}] 连接断开")

    async def _on_event(self, evt: dict[str, Any]) -> None:
        if evt.get("post_type") == "meta_event":
            return
        if evt.get("post_type") != "message":
            return
        scene = "group" if evt.get("message_type") == "group" else "private"
        peer = str(evt.get("group_id") if scene == "group" else evt.get("user_id"))
        sender = evt.get("sender", {}) or {}
        text = self._to_text(evt.get("message"))
        msg = IncomingMessage(
            bot_id=self.account_id, mode=self.mode, scene=scene, peer_id=peer,
            sender_id=str(evt.get("user_id", "")),
            sender_name=sender.get("card") or sender.get("nickname") or "",
            text=text, raw=evt, message_id=str(evt.get("message_id", "")),
        )
        await self.bus.publish({"type": "message", "data": msg.__dict__})

    @staticmethod
    def _to_text(message: Any) -> str:
        """把 OneBot 消息段数组拼成纯文本（图片等给占位）。"""
        if isinstance(message, str):
            return message
        if not isinstance(message, list):
            return ""
        out = []
        for seg in message:
            t = seg.get("type")
            if t == "text":
                out.append(seg.get("data", {}).get("text", ""))
            elif t == "image":
                out.append("[图片]")
            elif t == "face":
                out.append("[表情]")
            elif t == "at":
                out.append(f"@{seg.get('data', {}).get('qq', '')}")
        return "".join(out)

    async def _call(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._ws:
            raise RuntimeError("OneBot 未连接")
        self._echo += 1
        await self._ws.send_text(json.dumps({"action": action, "params": params, "echo": self._echo}))
        return {"echo": self._echo}

    async def send(self, msg: OutgoingMessage) -> dict[str, Any]:
        if msg.scene == "group":
            return await self._call("send_group_msg", {"group_id": int(msg.peer_id), "message": msg.text})
        return await self._call("send_private_msg", {"user_id": int(msg.peer_id), "message": msg.text})

    async def start(self) -> None:
        # 反向 WS 模式：这里只标记「等待 NapCat 连入」
        self.log(f"[onebot:{self.account_id}] 等待 NapCat 反向连接 ws://<host>:<port>/onebot/v11/ws")

    async def stop(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self.connected = False
