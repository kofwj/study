# -*- coding: utf-8 -*-
"""生成 PWA 图标（太阳 + 光芒，主题蓝底）。跑一次产出到 frontend/public/icons/，PNG 随仓库提交。"""
import math
import os
from PIL import Image, ImageDraw

BG = (58, 164, 224)      # #3aa4e0 主题蓝
RAY = (255, 152, 0)      # #ff9800 光芒橙
SUN = (255, 193, 7)      # #ffc107 太阳黄
RING = (255, 160, 0)     # #ffa000 描边


def draw_sun(size):
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    ray_r = size * 0.46         # 光芒外半径
    inner = size * 0.16         # 光芒内圈
    n = 12
    for i in range(n):
        a0 = (360 / n * i - 90) * math.pi / 180
        a2 = (360 / n * (i + 1) - 90) * math.pi / 180
        amid = (a0 + a2) / 2
        p1 = (cx + inner * math.cos(a0), cy + inner * math.sin(a0))
        p2 = (cx + ray_r * math.cos(amid), cy + ray_r * math.sin(amid))
        p3 = (cx + inner * math.cos(a2), cy + inner * math.sin(a2))
        d.polygon([p1, p2, p3], fill=RAY)
    r = size * 0.22
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SUN,
              outline=RING, width=max(2, size // 64))
    return img


out = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "icons")
os.makedirs(out, exist_ok=True)
for name, s in [("icon-192", 192), ("icon-512", 512),
                ("apple-touch-icon", 180), ("favicon", 64)]:
    draw_sun(s).save(os.path.join(out, name + ".png"))
    print("wrote", name, s)