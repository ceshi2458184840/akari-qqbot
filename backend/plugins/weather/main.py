"""天气插件：/天气 城市（走 wttr.in，免 key）。"""
import httpx
from urllib.parse import quote

DEFAULT_CITY = "北京"


async def _weather(city: str) -> str:
    url = f"https://wttr.in/{quote(city)}?format=j1&lang=zh"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, headers={"User-Agent": "curl/8"})
        d = r.json()
    cur = (d.get("current_condition") or [{}])[0]
    area = (d.get("nearest_area") or [{}])[0]
    name = ((area.get("areaName") or [{}])[0].get("value")) or city
    desc = ((cur.get("lang_zh") or cur.get("weatherDesc") or [{}])[0].get("value")) or ""
    temp = cur.get("temp_C", "?")
    feel = cur.get("FeelsLikeC", "?")
    hum = cur.get("humidity", "?")
    wind = cur.get("windspeedKmph", "?")
    return (f"【{name} 天气】{desc}\n"
            f"气温：{temp}℃（体感 {feel}℃）\n"
            f"湿度：{hum}%   风速：{wind} km/h")


def register(api):
    async def _tool_weather(args):
        city = (args or {}).get("city") or (api.config or {}).get("default_city") or DEFAULT_CITY
        try:
            return await _weather(city)
        except Exception as exc:
            return f"查天气失败：{exc}"

    api.tool("get_weather", "查询指定城市的实时天气（天气现象、气温、体感、湿度、风速）",
             {"type": "object",
              "properties": {"city": {"type": "string", "description": "城市名，如 北京、上海、Tokyo"}},
              "required": ["city"]},
             _tool_weather)

    @api.on("message")
    async def on_message(event):
        d = event.get("data", {})
        text = (d.get("text") or "").strip()
        for kw in ("/天气", "天气", "#天气"):
            if text.startswith(kw):
                city = text[len(kw):].strip() or (api.config or {}).get("default_city") or DEFAULT_CITY
                try:
                    reply = await _weather(city)
                except Exception as exc:
                    reply = f"查天气失败：{exc}"
                await api.send(d["bot_id"], d["scene"], d["peer_id"], reply)
                return
