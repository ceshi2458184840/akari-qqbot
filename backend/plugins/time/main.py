"""时间插件：查当前时间/日期，支持时区。同时注册 get_time 工具给 AI 用。"""
import datetime
import zoneinfo

DEFAULT_TZ = "Asia/Shanghai"
ALIAS = {
    "北京": "Asia/Shanghai", "上海": "Asia/Shanghai", "中国": "Asia/Shanghai",
    "纽约": "America/New_York", "洛杉矶": "America/Los_Angeles", "伦敦": "Europe/London",
    "巴黎": "Europe/Paris", "东京": "Asia/Tokyo", "首尔": "Asia/Seoul",
    "香港": "Asia/Hong_Kong", "台北": "Asia/Taipei", "莫斯科": "Europe/Moscow",
    "悉尼": "Australia/Sydney", "迪拜": "Asia/Dubai", "新加坡": "Asia/Singapore",
}
WEEK = "一二三四五六日"


def _now(tz: str) -> str:
    zone = ALIAS.get(tz.strip(), tz.strip() or DEFAULT_TZ)
    try:
        z = zoneinfo.ZoneInfo(zone)
    except Exception:
        z = zoneinfo.ZoneInfo(DEFAULT_TZ)
        zone = DEFAULT_TZ
    t = datetime.datetime.now(z)
    return (f"【{zone}】{t.strftime('%Y-%m-%d')} 星期{WEEK[t.weekday()]}\n"
            f"时间：{t.strftime('%H:%M:%S')}")


def register(api):
    async def _tool_time(args):
        tz = (args or {}).get("timezone") or (api.config or {}).get("timezone") or DEFAULT_TZ
        return _now(tz)

    api.tool("get_time", "查询指定时区的当前日期和时间",
             {"type": "object",
              "properties": {"timezone": {"type": "string",
                                          "description": "IANA 时区名，如 Asia/Shanghai（默认北京）"}},
              "required": []},
             _tool_time)

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        for kw in ("/时间", "时间", "/time", "#时间", "现在几点"):
            if text.startswith(kw):
                tz = text[len(kw):].strip() or (api.config or {}).get("timezone") or DEFAULT_TZ
                await api.send(d["bot_id"], d["scene"], d["peer_id"], _now(tz))
                return
