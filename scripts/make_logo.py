#!/usr/bin/env python3
"""Draws the application icon:  assets/app_icon.ico (multi-size) and assets/app_icon.png.   Run: python scripts/make_logo.py"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
S = 1024  # drawn large, then scaled down (smooth edges at every size)

NAVY, NAVY_LIGHT = (27, 58, 95), (44, 84, 130)
BLUE, BLUE_BG = (21, 101, 192), (232, 241, 252)
ORANGE, ORANGE_BG = (198, 93, 18), (253, 234, 222)
RED, WHITE, GREY = (200, 38, 45), (255, 255, 255), (232, 235, 240)


def rr(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded-square tile with a soft vertical shade
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for y in range(S):
        t = y / S
        c = tuple(int(NAVY_LIGHT[i] * (1 - t) + NAVY[i] * t) for i in range(3)) + (255,)
        td.line([(0, y), (S, y)], fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), radius=210, fill=255)
    img.paste(tile, (0, 0), mask)

    # back slide (the "deck"), tilted, with a soft shadow
    back = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    rr(bd, (170, 200, 790, 640), 46, (170, 195, 230, 255))
    back = back.rotate(8, resample=Image.BICUBIC, center=(480, 420))
    shadow = back.filter(ImageFilter.GaussianBlur(14))
    shadow = Image.eval(shadow, lambda v: v)  # keep alpha
    img.alpha_composite(Image.new("RGBA", (S, S), (0, 0, 0, 0)))
    img.alpha_composite(back)

    # front slide
    d = ImageDraw.Draw(img)
    rr(d, (150, 260, 830, 780), 52, WHITE)
    rr(d, (205, 308, 520, 346), 19, NAVY)            # title bar
    rr(d, (205, 362, 420, 384), 11, (150, 165, 185))  # subtitle line
    rr(d, (200, 420, 480, 640), 28, BLUE_BG)          # card A
    d.ellipse((222, 438, 276, 492), fill=BLUE)
    rr(d, (292, 450, 448, 470), 10, BLUE)
    for i in range(3):
        rr(d, (226, 516 + i * 34, 440 - i * 22, 530 + i * 34), 7, (120, 150, 195))
    rr(d, (500, 420, 780, 640), 28, ORANGE_BG)        # card B
    d.ellipse((522, 438, 576, 492), fill=ORANGE)
    rr(d, (592, 450, 748, 470), 10, ORANGE)
    for i in range(3):
        rr(d, (526, 516 + i * 34, 740 - i * 30, 530 + i * 34), 7, (225, 170, 130))
    for i in range(4):                                # snapshot strip
        x = 200 + i * 148
        rr(d, (x, 668, x + 136, 740), 16, GREY)
        d.ellipse((x + 52, 678, x + 84, 710), fill=NAVY)

    # "+" badge = build / add
    d.ellipse((640, 640, 960, 960), fill=RED, outline=WHITE, width=22)
    d.rounded_rectangle((782, 700, 818, 900), radius=16, fill=WHITE)
    d.rounded_rectangle((700, 782, 900, 818), radius=16, fill=WHITE)
    return img


def main():
    OUT.mkdir(exist_ok=True)
    big = draw()
    big.resize((512, 512), Image.LANCZOS).save(OUT / "app_icon.png")
    big.resize((48, 48), Image.LANCZOS).save(OUT / "app_icon_48.png")  # header of the main window
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(OUT / "app_icon.ico", sizes=[(s, s) for s in sizes])
    print("wrote", OUT / "app_icon.png", "and", OUT / "app_icon.ico")


if __name__ == "__main__":
    main()
