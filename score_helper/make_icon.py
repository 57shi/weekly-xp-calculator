# -*- coding: utf-8 -*-
"""生成应用图标：深色底 + 黄色 CS 字样 + 显示器/计算器元素"""
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
BG = (16, 21, 28, 255)          # 与界面一致的深色
YELLOW = (255, 214, 10, 255)    # 主题黄
GREEN = (55, 214, 122, 255)
GREY = (139, 152, 165, 255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角方底
rad = 46
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=rad, fill=BG)

# —— 上部：显示器轮廓（计算机元素）——
mx0, my0, mx1, my1 = 44, 34, 212, 148
d.rounded_rectangle([mx0, my0, mx1, my1], radius=14, outline=GREY, width=7)
d.rectangle([mx0 + 12, my0 + 12, mx1 - 12, my1 - 12], fill=(24, 31, 40, 255))
# 屏幕底座
d.rounded_rectangle([108, my1, 148, my1 + 20], radius=6, fill=GREY)
d.rounded_rectangle([84, my1 + 18, 172, my1 + 30], radius=8, fill=GREY)

# —— 屏幕里放 CS 字样 ——
def load_font(sz):
    for name in ("segoeuib.ttf", "arialbd.ttf", "seguibl.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:
            continue
    return ImageFont.load_default()

f_big = load_font(86)
txt = "CS"
bb = d.textbbox((0, 0), txt, font=f_big)
tw, th = bb[2] - bb[0], bb[3] - bb[1]
tx = (mx0 + mx1) / 2 - tw / 2 - bb[0]
ty = (my0 + my1) / 2 - th / 2 - bb[1]
d.text((tx + 2, ty + 2), txt, font=f_big, fill=(120, 90, 0, 255))
d.text((tx, ty), txt, font=f_big, fill=YELLOW)

# —— 下部：计算器等号/加号（计算器元素）——
by = 196
d.rounded_rectangle([70, by, 186, by + 40], radius=12, fill=(24, 31, 40, 255), outline=GREEN, width=4)
# 等号
d.rounded_rectangle([92, by + 12, 164, by + 17], radius=2, fill=GREEN)
d.rounded_rectangle([92, by + 23, 164, by + 28], radius=2, fill=GREEN)

img = img.resize((SIZE, SIZE), Image.LANCZOS)

out_dir = os.path.dirname(os.path.abspath(__file__))
ico = os.path.join(out_dir, "app.ico")
img.save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
png = os.path.join(out_dir, "app.png")
img.save(png)
print("ICO:", ico, os.path.getsize(ico), "bytes")
print("PNG:", png)
