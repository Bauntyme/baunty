"""
Anonim savollar uchun Instagram Story (9:16, 1080x1920) PNG shablon generatori.
Tezkor kesh va Windows/Linux shriftlari uchun xavfsiz fallback bilan ishlaydi.
"""
import io
import os
import logging
from typing import Dict, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_STORY_CARD_CACHE: Dict[str, bytes] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Windows va Linux muhitida mos keluvchi TrueType shriftni yuklaydi."""
    candidates = (
        [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_center_x(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, center_x: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    return int(center_x - width / 2)


def _draw_dashed_rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    radius: int,
    outline_color: Tuple[int, int, int, int],
    fill_color: Tuple[int, int, int, int],
    width: int = 4,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill_color)
    # Yuqori va pastki punktir chiziqlar
    step = 28
    dash = 16
    for x in range(x1 + radius, x2 - radius, step):
        dx2 = min(x + dash, x2 - radius)
        draw.line([(x, y1), (dx2, y1)], fill=outline_color, width=width)
        draw.line([(x, y2), (dx2, y2)], fill=outline_color, width=width)
    # Chap va o'ng punktir chiziqlar
    for y in range(y1 + radius, y2 - radius, step):
        dy2 = min(y + dash, y2 - radius)
        draw.line([(x1, y), (x1, dy2)], fill=outline_color, width=width)
        draw.line([(x2, y), (x2, dy2)], fill=outline_color, width=width)
    # Burchaklar
    d = radius * 2
    draw.arc([x1, y1, x1 + d, y1 + d], 180, 270, fill=outline_color, width=width)
    draw.arc([x2 - d, y1, x2, y1 + d], 270, 360, fill=outline_color, width=width)
    draw.arc([x1, y2 - d, x1 + d, y2], 90, 180, fill=outline_color, width=width)
    draw.arc([x2 - d, y2 - d, x2, y2], 0, 90, fill=outline_color, width=width)


def _draw_envelope_badge(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """Vektorli konvert belgisi (barcha tizimlarda toza ko'rinadi)."""
    r = 68
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(242, 184, 75, 42), outline=(242, 184, 75, 190), width=3)
    ew, eh = 68, 46
    ex1, ey1, ex2, ey2 = cx - ew // 2, cy - eh // 2, cx + ew // 2, cy + eh // 2
    draw.rounded_rectangle([ex1, ey1, ex2, ey2], radius=8, fill=(242, 184, 75, 255))
    draw.line([(ex1 + 4, ey1 + 5), (cx, cy + 4), (ex2 - 4, ey1 + 5)], fill=(20, 24, 56, 255), width=5)


def generate_anon_story_image(bot_username: str = "BauntyCinemabot") -> bytes:
    """Instagram Story (1080x1920) uchun anonim savol shablon rasmini PNG baytlarda yaratadi."""
    clean_bot = str(bot_username or "BauntyCinemabot").strip().lstrip("@")
    if clean_bot in _STORY_CARD_CACHE:
        return _STORY_CARD_CACHE[clean_bot]

    W, H = 1080, 1920
    # Vertikalgradient (Samarkand dark twilight -> indigo/violet)
    top_rgb = (10, 15, 42)
    mid_rgb = (26, 19, 68)
    bot_rgb = (42, 18, 66)

    grad = Image.new("RGBA", (1, H))
    px = grad.load()
    for y in range(H):
        if y < H // 2:
            t = y / (H // 2)
            r = int(top_rgb[0] + (mid_rgb[0] - top_rgb[0]) * t)
            g = int(top_rgb[1] + (mid_rgb[1] - top_rgb[1]) * t)
            b = int(top_rgb[2] + (mid_rgb[2] - top_rgb[2]) * t)
        else:
            t = (y - H // 2) / (H - H // 2)
            r = int(mid_rgb[0] + (bot_rgb[0] - mid_rgb[0]) * t)
            g = int(mid_rgb[1] + (bot_rgb[1] - mid_rgb[1]) * t)
            b = int(mid_rgb[2] + (bot_rgb[2] - mid_rgb[2]) * t)
        px[0, y] = (r, g, b, 255)

    img = grad.resize((W, H), Image.Resampling.BILINEAR)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Yumshoq dekorativ nurlar
    odraw.ellipse([-140, 140, 560, 840], fill=(242, 184, 75, 28))
    odraw.ellipse([540, 1020, 1260, 1740], fill=(92, 107, 255, 36))
    odraw.ellipse([260, 400, 820, 960], fill=(200, 52, 92, 22))

    # Asosiy markaziy karta (Instagram story safe-zone ichida)
    cx1, cy1, cx2, cy2 = 86, 410, W - 86, 1490
    odraw.rounded_rectangle(
        [cx1 + 10, cy1 + 16, cx2 + 10, cy2 + 16],
        radius=50,
        fill=(0, 0, 0, 115),
    )
    odraw.rounded_rectangle(
        [cx1, cy1, cx2, cy2],
        radius=48,
        fill=(18, 22, 54, 232),
        outline=(242, 184, 75, 195),
        width=4,
    )

    # Yuqori konvert nishoni
    center_x = W // 2
    _draw_envelope_badge(odraw, center_x, cy1 + 120)

    f_badge = _load_font(30, bold=True)
    f_title = _load_font(56, bold=True)
    f_sub = _load_font(32, bold=False)
    f_box = _load_font(35, bold=True)
    f_hint = _load_font(26, bold=False)
    f_bot = _load_font(30, bold=True)

    badge_txt = "ANONIM SAVOLLAR"
    odraw.text((_text_center_x(odraw, badge_txt, f_badge, center_x), cy1 + 210), badge_txt, font=f_badge, fill=(242, 184, 75, 255))

    t1 = "Menga anonim savol"
    t2 = "yoki fikr yozing"
    odraw.text((_text_center_x(odraw, t1, f_title, center_x), cy1 + 295), t1, font=f_title, fill=(246, 238, 220, 255))
    odraw.text((_text_center_x(odraw, t2, f_title, center_x), cy1 + 368), t2, font=f_title, fill=(246, 238, 220, 255))

    sub_txt = "Shaxsingiz 100% sir saqlanadi"
    odraw.text((_text_center_x(odraw, sub_txt, f_sub, center_x), cy1 + 468), sub_txt, font=f_sub, fill=(190, 195, 230, 235))

    # Link stiker joylash ramkasi
    bx1, by1, bx2, by2 = 156, cy1 + 565, W - 156, cy1 + 815
    _draw_dashed_rounded_rect(
        odraw,
        (bx1, by1, bx2, by2),
        radius=30,
        outline_color=(242, 184, 75, 240),
        fill_color=(10, 14, 34, 245),
        width=4,
    )

    box_label = "[ SHU YERGA LINKNI QO'YING ]"
    odraw.text((_text_center_x(odraw, box_label, f_box, center_x), by1 + 78), box_label, font=f_box, fill=(255, 255, 255, 255))

    hint_label = "Stiker belgisini bosing  ->  LINK"
    odraw.text((_text_center_x(odraw, hint_label, f_hint, center_x), by1 + 148), hint_label, font=f_hint, fill=(242, 184, 75, 235))

    bot_label = f"@{clean_bot}"
    odraw.text((_text_center_x(odraw, bot_label, f_bot, center_x), cy2 - 92), bot_label, font=f_bot, fill=(246, 238, 220, 210))

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    composed.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    _STORY_CARD_CACHE[clean_bot] = png_bytes
    return png_bytes
