"""插件商店：从一个 Git 仓库地址拉取该仓库下的全部插件。

参考麦麦（MaiBot）的分发方式：插件以仓库为单位，填 URL → 扫出所有 plugin.json → 装。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)


def scan_repo(repo_url: str, log=print) -> list[dict[str, Any]]:
    """浅克隆仓库并扫描所有 plugin.json，返回插件元数据（不安装）。"""
    tmp = tempfile.mkdtemp(prefix="akari-plugin-")
    try:
        r = _run(["git", "clone", "--depth", "1", repo_url, tmp])
        if r.returncode != 0:
            raise RuntimeError(f"git clone 失败：{r.stderr.strip()[:300]}")
        found: list[dict[str, Any]] = []
        for dirpath, _dirnames, filenames in os.walk(tmp):
            if ".git" in dirpath.split(os.sep):
                continue
            if "plugin.json" in filenames:
                try:
                    meta = json.load(open(os.path.join(dirpath, "plugin.json"), encoding="utf-8"))
                except Exception:
                    continue
                meta["_path"] = os.path.relpath(dirpath, tmp)
                meta["_repo"] = repo_url
                found.append(meta)
        log(f"[store] 仓库 {repo_url} 扫描到 {len(found)} 个插件")
        return found
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_repo(repo_url: str, plugins_root: str, log=print) -> list[dict[str, Any]]:
    """克隆仓库并把其中所有插件复制到 plugins_root/<name>。"""
    tmp = tempfile.mkdtemp(prefix="akari-plugin-")
    installed: list[dict[str, Any]] = []
    try:
        r = _run(["git", "clone", "--depth", "1", repo_url, tmp])
        if r.returncode != 0:
            raise RuntimeError(f"git clone 失败：{r.stderr.strip()[:300]}")
        os.makedirs(plugins_root, exist_ok=True)
        for dirpath, _dirnames, filenames in os.walk(tmp):
            if ".git" in dirpath.split(os.sep) or "plugin.json" not in filenames:
                continue
            try:
                meta = json.load(open(os.path.join(dirpath, "plugin.json"), encoding="utf-8"))
            except Exception:
                continue
            name = meta.get("name") or os.path.basename(dirpath)
            dest = os.path.join(plugins_root, name)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(dirpath, dest)
            meta["_repo"] = repo_url
            meta["_installed_path"] = dest
            installed.append(meta)
            log(f"[store] 已安装插件 {name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return installed
