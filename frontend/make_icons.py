#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 AkariBot PWA 图标（QQ 蓝 + 机器人头）。"""
from PIL import Image, ImageDraw

def make(size: int, path: str):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * 0.22)
    # 圆角蓝底
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(18, 183, 245, 255))
    # 内部浅色渐变感（顶部高光条）
    d.rounded_rectangle([0, 0, size - 1, int(size * 0.5)], radius=r, fill=(56, 200, 250, 120))
    # 机器人头（白）
    cx, cy = size / 2, size * 0.56
    hw, hh = size * 0.30, size * 0.24
    d.rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh], radius=int(size * 0.08), fill=(255, 255, 255, 255))
    # 天线
    d.line([(cx, cy - hh), (cx, cy - hh - size * 0.10)], fill=(255, 255, 255, 255), width=max(2, int(size * 0.018)))
    d.ellipse([cx - size * 0.035, cy - hh - size * 0.16, cx + size * 0.035, cy - hh - size * 0.09], fill=(255, 255, 255, 255))
    # 眼睛
    ey = cy - size * 0.03
    for dx in (-hw * 0.45, hw * 0.45):
        d.ellipse([cx + dx - size * 0.045, ey - size * 0.045, cx + dx + size * 0.045, ey + size * 0.045], fill=(18, 183, 245, 255))
    # 嘴
    d.rounded_rectangle([cx - hw * 0.45, cy + size * 0.08, cx + hw * 0.45, cy + size * 0.13], radius=int(size * 0.02), fill=(18, 183, 245, 255))
    img.save(path)

for s in (192, 512):
    make(s, f"/home/ubuntu/projects/akari-qqbot/frontend/icon-{s}.png")
print("icons ok")
