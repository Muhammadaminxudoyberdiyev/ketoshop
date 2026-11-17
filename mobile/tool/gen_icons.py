"""Ketoshop launcher icons from the shop's logo (the @ketoshop_uz avatar).

    python mobile/tool/gen_icons.py

Source: mobile/assets/brand/ketoshop_logo.jpg (round logo on cream #FEF7ED).
Writes assets/brand/ketoshop_logo_round.png (login screen) and android/app/src/main/res:
  mipmap-*/ic_launcher.png             Android 7 (round badge: cream + green ring + mark)
  mipmap-*/ic_launcher_foreground.png  Android 8+ adaptive foreground (mark only, transparent)
  mipmap-*/ic_launcher_monochrome.png  Android 13+ themed icon (mark silhouette)
  mipmap-anydpi-v26/ic_launcher.xml, values/ic_launcher_colors.xml

The icon keeps the logo's leaves + «KETO SHOP» wordmark and drops the small
tagline under it, which no phone could show legibly at icon size. A sharper
source (≥ 1024 px) can replace the jpg; the crop is relative to its size.
Needs Pillow (dev tool only, not part of the app).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "brand" / "ketoshop_logo.jpg"
RES = ROOT / "android" / "app" / "src" / "main" / "res"

CREAM = (254, 247, 237)       # the logo's own background
RING = (98, 112, 30)          # the logo's green ring
# Leaves + wordmark + swoosh, as fractions of the 320 px original.
MARK_BOX = (14 / 320, 56 / 320, 298 / 320, 242 / 320)
INNER_R = 148 / 320           # radius inside the green ring
OUTER_R = 157 / 320           # the ring's outer edge
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
SAFE_DP = 64                  # adaptive icons: content inside the 66 dp safe circle


def mark() -> Image.Image:
    """The mark cut out of the cream background: RGBA, soft edges."""
    logo = Image.open(SRC).convert("RGB")
    w, h = logo.size
    # Only what is inside the green ring (the jpg's corners are black).
    inner = Image.new("L", (w, h), 0)
    r = w * INNER_R
    ImageDraw.Draw(inner).ellipse((w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r), fill=255)
    box = tuple(round(f * s) for f, s in zip(MARK_BOX, (w, h, w, h)))
    crop = logo.crop(box)
    diff = ImageChops.difference(crop, Image.new("RGB", crop.size, CREAM)).convert("L")
    # colour distance from cream -> opacity; cream itself (and JPEG noise) is clear
    alpha = diff.point(lambda d: 0 if d < 6 else min(255, (d - 6) * 9))
    alpha = ImageChops.multiply(alpha, inner.crop(box)).filter(ImageFilter.GaussianBlur(0.4))
    out = crop.convert("RGBA")
    out.putalpha(alpha)
    return out.crop(out.getbbox())


def fit_in_circle(img: Image.Image, diameter: float) -> Image.Image:
    """Scale so every opaque pixel lies inside a circle of `diameter`
    around the image centre."""
    a = img.getchannel("A")
    w, h = img.size
    cx, cy = w / 2, h / 2
    r = 0.0
    px = a.load()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if px[x, y] > 40:
                r = max(r, math.hypot(x - cx, y - cy))
    scale = (diameter / 2) / r
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def centred(img: Image.Image, size: int, background=(0, 0, 0, 0)) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), background)
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def legacy_badge(m: Image.Image, size: int) -> Image.Image:
    """Android 7: a round badge like the logo itself."""
    s = size * 4  # draw large, shrink once for smooth edges
    badge = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    pad = round(s * 0.04)
    d.ellipse((pad, pad, s - pad, s - pad), fill=RING)
    ring = round(s * 0.025)
    d.ellipse((pad + ring, pad + ring, s - pad - ring, s - pad - ring), fill=CREAM)
    inner = s - 2 * (pad + ring)
    badge.alpha_composite(centred(fit_in_circle(m, inner * 0.86), s))
    return badge.resize((size, size), Image.LANCZOS)


def round_logo() -> None:
    """The whole logo with transparent corners, for the app's own screens
    (assets/brand/ketoshop_logo_round.png)."""
    logo = Image.open(SRC).convert("RGBA")
    w, h = logo.size
    s = 4
    mask = Image.new("L", (w * s, h * s), 0)
    r = w * s * OUTER_R
    ImageDraw.Draw(mask).ellipse((w * s / 2 - r, h * s / 2 - r, w * s / 2 + r, h * s / 2 + r), fill=255)
    logo.putalpha(mask.resize((w, h), Image.LANCZOS))
    logo.save(SRC.with_name("ketoshop_logo_round.png"), optimize=True)


def main() -> None:
    round_logo()
    m = mark()
    for name, k in DENSITIES.items():
        folder = RES / f"mipmap-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        full = round(108 * k)
        fg = centred(fit_in_circle(m, SAFE_DP * k), full)
        fg.save(folder / "ic_launcher_foreground.png", optimize=True)
        # Themed icon: solid shapes only (the logo's soft shadows would halo).
        white = Image.new("RGB", fg.size, (255, 255, 255))
        solid = fg.getchannel("A").point(lambda a: 255 if a > 150 else 0).filter(ImageFilter.GaussianBlur(0.5 * k))
        Image.merge("RGBA", (*white.split(), solid)).save(folder / "ic_launcher_monochrome.png", optimize=True)
        legacy_badge(m, round(48 * k)).save(folder / "ic_launcher.png", optimize=True)

    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(exist_ok=True)
    (anydpi / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
        '</adaptive-icon>\n', encoding="utf-8")
    (RES / "values" / "ic_launcher_colors.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="ic_launcher_background">#%02X%02X%02X</color>\n</resources>\n' % CREAM,
        encoding="utf-8")
    print("icons written to", RES)


if __name__ == "__main__":
    main()
