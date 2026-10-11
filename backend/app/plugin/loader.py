"""插件加载与钩子调度。

插件目录结构：
    plugins/<name>/
        plugin.json      {"name","version","entry","description","hooks":[...]}
        main.py          需导出 register(api)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from typing import Any, Awaitable, Callable


class PluginAPI:
    """暴露给插件的接口。"""

    def __init__(self, manager: "PluginManager", name: str):
        self._m = manager
        self.name = name
        self.log = manager.log

    def on(self, event_type: str) -> Callable:
        """装饰器：注册一个事件处理函数。event_type 如 'message' / 'notice'。"""
        def deco(fn: Callable[[dict], Awaitable[None]]):
            self._m.register(event_type, self.name, fn)
            return fn
        return deco

    async def send(self, bot_id: str, scene: str, peer_id: str, text: str) -> dict[str, Any]:
        return await self._m.send(bot_id, scene, peer_id, text)

    def list_plugins(self) -> list[dict[str, Any]]:
        """当前已安装插件列表。"""
        return self._m.info()

    def get_bots(self) -> list[dict[str, Any]]:
        """当前所有账号（含连接状态）。"""
        return self._m.get_bots()

    def get_adapter(self, bot_id: str):
        """拿到某个账号的适配器实例（高级插件用，如群管）。"""
        return self._m.get_adapter(bot_id)


class PluginManager:
    def __init__(self, root: str, bus, log=print):
        self.root = os.path.abspath(root)
        self.bus = bus
        self.log = log
        self.installed: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, list[tuple[str, Callable]]] = {}
        self._send_cb: Callable[..., Awaitable[dict]] | None = None
        self._bots_provider: Callable[[], list] | None = None
        self._adapter_provider: Callable[[str], Any] | None = None
        os.makedirs(self.root, exist_ok=True)

    # ---- 供 main 注入「发消息」能力 ----
    def set_send_callback(self, cb: Callable[..., Awaitable[dict]]) -> None:
        self._send_cb = cb

    async def send(self, bot_id: str, scene: str, peer_id: str, text: str) -> dict[str, Any]:
        if not self._send_cb:
            raise RuntimeError("send callback 未注入")
        return await self._send_cb(bot_id, scene, peer_id, text)

    def set_bots_provider(self, cb: Callable[[], list]) -> None:
        self._bots_provider = cb

    def set_adapter_provider(self, cb: Callable[[str], Any]) -> None:
        self._adapter_provider = cb

    def get_adapter(self, bot_id: str):
        try:
            return self._adapter_provider(bot_id) if self._adapter_provider else None
        except Exception:
            return None

    def get_bots(self) -> list:
        try:
            return self._bots_provider() if self._bots_provider else []
        except Exception:
            return []

    def register(self, event_type: str, plugin: str, fn: Callable) -> None:
        self._handlers.setdefault(event_type, []).append((plugin, fn))
        self.log(f"[plugin] {plugin} 订阅事件 {event_type}")

    # ---- 发现 / 加载 ----
    def discover(self) -> list[dict[str, Any]]:
        found = []
        for name in sorted(os.listdir(self.root)):
            d = os.path.join(self.root, name)
            manifest = os.path.join(d, "plugin.json")
            if os.path.isdir(d) and os.path.isfile(manifest):
                try:
                    meta = json.load(open(manifest, encoding="utf-8"))
                    meta["_dir"] = d
                    found.append(meta)
                except Exception as exc:
                    self.log(f"[plugin] {name} plugin.json 解析失败：{exc}")
        return found

    def load_all(self) -> None:
        for meta in self.discover():
            self.load(meta)

    def load(self, meta: dict[str, Any]) -> None:
        name = meta.get("name") or os.path.basename(meta["_dir"])
        entry = meta.get("entry", "main.py")
        path = os.path.join(meta["_dir"], entry)
        if not os.path.isfile(path):
            self.log(f"[plugin] {name} 缺少入口 {entry}")
            return
        try:
            spec = importlib.util.spec_from_file_location(f"akari_plugin_{name}", path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[spec.name] = mod  # type: ignore[union-attr]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if hasattr(mod, "register"):
                mod.register(PluginAPI(self, name))
            self.installed[name] = meta
            self.log(f"[plugin] 已加载 {name} v{meta.get('version', '?')}")
        except Exception as exc:
            self.log(f"[plugin] {name} 加载失败：{exc}")

    # ---- 事件分发 ----
    async def dispatch(self, event_type: str, event: dict[str, Any]) -> None:
        for plugin, fn in self._handlers.get(event_type, []):
            try:
                await fn(event)
            except Exception as exc:
                self.log(f"[plugin] {plugin} 处理 {event_type} 出错：{exc}")

    def info(self) -> list[dict[str, Any]]:
        return [
            {"name": m.get("name"), "version": m.get("version"),
             "description": m.get("description", ""), "hooks": m.get("hooks", [])}
            for m in self.installed.values()
        ]
