# AkariBot Studio · 仿 QQ 界面的 QQ 机器人应用

一个自研的 QQ 机器人客户端：**界面尽量贴近 QQ 本体**，支持 **个人号扫码登录** 与 **QQ 官方机器人（AppID/Secret）** 双模式，内置 **插件商店**（从一个 GitHub 仓库链接一键拉取其下全部插件）。

## 为什么自己做

- 现有框架（AstrBot / MaiBot / LangBot）功能强，但界面是「管理面板」而非「聊天客户端」，没法像 QQ 一样直接切会话聊天。
- 需求：**一个人用的、长得像 QQ 的机器人工作台**——左侧是账号/会话列表，右侧是聊天窗口，可同时挂「个人号」和「官方机器人」。
- 插件系统参考麦麦（MaiBot）：插件以 Git 仓库为单位分发，填一个仓库地址即可拉取该仓库下的所有插件。

## 架构

```
┌─────────────────────────────────────────────┐
│  前端（仿 QQ UI，React）                      │
│  账号列表 · 会话列表 · 聊天窗口 · 插件商店     │
└───────────────┬─────────────────────────────┘
                │ REST + WebSocket
┌───────────────▼─────────────────────────────┐
│  后端（Python · FastAPI）                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ OneBot   │  │ QQ官方   │  │ 插件运行时  │ │
│  │ 适配器    │  │ 适配器    │  │ (钩子总线)  │ │
│  │ 个人号    │  │ AppID    │  │ 插件商店    │ │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│       │ 反向WS        │ WS+REST       │ Git   │
└───────┼──────────────┼───────────────┼───────┘
        │              │               │
   NapCat 客户端   QQ开放平台      GitHub 插件仓库
   (手机的 QQ)     (企鹅服务器)     (自己的组织)
```

### 双模式登录

| 模式 | 协议 | 登录方式 | 说明 |
|------|------|----------|------|
| 个人号 | OneBot v11（反向 WebSocket） | NapCat 扫码登录 QQ | 功能全、能收发任意会话；非官方协议，有风控风险 |
| 官方号 | QQ Bot API v2（WebSocket + REST） | 填 AppID + AppSecret | 腾讯官方，稳定合规；只能收到 @机器人 的群消息 |

### 插件系统

- 插件 = 一个目录 + `plugin.json`（`name` / `version` / `entry` / `description` / `hooks`）。
- 插件商店：填一个 **Git 仓库地址** → 后端拉取 → 扫描仓库内所有 `plugin.json` → 列出可安装插件 → 一键安装到 `plugins/`。
- 事件钩子：`on_message` / `on_group_message` / `on_notice` / `on_command`。

## 目录结构

```
akari-qqbot/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI 入口 + WebSocket
│       ├── bus.py               # 统一事件总线
│       ├── store.py             # 账号 / 配置持久化 (SQLite)
│       ├── adapters/
│       │   ├── base.py          # 适配器抽象 + 统一数据结构
│       │   ├── onebot.py        # 个人号（OneBot v11 反向 WS）
│       │   └── qqofficial.py    # 官方号（QQ Bot API v2）
│       └── plugin/
│           ├── loader.py        # 插件加载 / 钩子调度
│           └── store.py         # 插件商店（GitHub 源）
├── frontend/                    # 仿 QQ 界面
└── docs/
```

## 快速开始

```bash
# 后端
cd backend && pip install -r requirements.txt
python -m app.main            # 默认 http://127.0.0.1:8099

# 前端
cd frontend && npm install && npm run dev
```

## 分期

- **P1** 骨架 + 双模式登录 + 基础聊天 UI ← 进行中
- **P2** 插件系统 + 插件商店
- **P3** 打包成桌面 / 手机 App

## License

MIT
