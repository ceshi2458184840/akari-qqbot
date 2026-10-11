"""统一事件总线：适配器 → 插件钩子 / 前端 WebSocket。"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


class EventBus:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._hooks: list[Callable[[dict], Awaitable[None]]] = []
        self._log = print

    # ---- 前端订阅（WebSocket）----
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    # ---- 插件钩子 ----
    def register_hook(self, fn: Callable[[dict], Awaitable[None]]) -> None:
        self._hooks.append(fn)

    # ---- 发布 ----
    async def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
        for fn in list(self._hooks):
            try:
                await fn(event)
            except Exception as exc:  # 插件异常不能拖垮总线
                self._log(f"[bus] hook error: {exc}")
