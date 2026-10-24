#!/usr/bin/env python3
"""Render Meow-Meow's red-and-gold "study pact" card as a PNG that shows inline in iMessage.

    python3 scripts/card.py --input plan.json --out ~/meow-meow/card.png
    python3 scripts/card.py --sample --out ~/meow-meow/sample_card.png

plan.json:
{
  "title": "CSE 355 Exam Rescue",              # required, short
  "when": "Tue, Oct 27 · 4:00–5:30 PM",         # required, already in the student's time zone
  "where": "Hayden Library, Room 204",          # required
  "crew": ["Ava", "Leo", "Priya"],              # optional, first names
  "focus": ["DFA", "PDA", "CFG"],               # optional, topics to cover
  "luck": "Paw raised for an A."                # optional one-liner, a default is used otherwise
}

Needs Pillow (see SKILL.md, Setup). Fonts are bundled under assets/fonts (SIL Open Font License).
Exit codes: 0 ok, 2 bad or missing input, 4 Pillow missing.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
SAMPLE = ROOT / "assets" / "sample_plan.json"
MASCOT = ROOT / "assets" / "lucky_cat.png"

W, H = 1080, 1350
S = 2  # supersampling factor for smooth edges

RED = (184, 35, 47)
RED_DEEP = (122, 18, 28)
RED_SOFT = (214, 74, 72)
GOLD = (212, 168, 75)
GOLD_LIGHT = (243, 214, 140)
GOLD_DEEP = (160, 116, 38)
CREAM = (251, 243, 228)
INK = (74, 22, 26)
WHITE = (255, 252, 247)
PINK = (240, 160, 160)

LUCK_LINES = [
    "Paw raised for an A.",
    "Fortune favors the prepared.",
    "Good luck is just good planning.",
]


def fail(message: str, code: int):
    print(message, file=sys.stderr)
    sys.exit(code)


try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    fail("Pillow is missing. Run the Setup command in SKILL.md.", 4)


def font(name: str, size: int, style: str = "Regular"):
    f = ImageFont.truetype(str(FONTS / name), size * S)
    try:
        f.set_variation_by_name(style)
    except (OSError, ValueError):
        pass
    return f


def load_plan(path: Path) -> dict:
    try:
        plan = json.loads(path.read_text())
    except OSError:
        fail(f"Can't read {path}", 2)
    except ValueError as exc:
        fail(f"{path} is not valid JSON: {exc}", 2)
    missing = [k for k in ("title", "when", "where") if not str(plan.get(k) or "").strip()]
    if missing:
        fail(f"Plan is missing: {', '.join(missing)}", 2)
    return plan


def p(x: float) -> int:
    return int(round(x * S))


def text_w(draw, s: str, f) -> int:
    l, _, r, _ = draw.textbbox((0, 0), s, font=f)
    return r - l


def fit(draw, s: str, name: str, size: int, style: str, max_w: int):
    """Shrink a font until the text fits max_w (in unscaled px); ellipsize as a last resort."""
    while size > 18:
        f = font(name, size, style)
        if text_w(draw, s, f) <= p(max_w):
            return s, f
        size -= 2
    f = font(name, size, style)
    while s and text_w(draw, s + "…", f) > p(max_w):
        s = s[:-1]
    return s + "…", f


def background(img: Image.Image):
    d = ImageDraw.Draw(img)
    # vertical gradient, deep red to lucky red
    for y in range(p(H)):
        t = y / p(H)
        c = tuple(int(RED_DEEP[i] + (RED[i] - RED_DEEP[i]) * (1 - abs(t - 0.35) * 1.3)) for i in range(3))
        d.line([(0, y), (p(W), y)], fill=c)
    # seigaiha-style gold waves along the bottom of the header, very subtle
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)
    r = 46
    for row in range(5):
        y = 470 - row * 0 + row * 30
        off = (row % 2) * r
        for x in range(-r, W + r, r * 2):
            for k in (1.0, 0.72, 0.44):
                o.arc([p(x + off - r * k), p(y - r * k), p(x + off + r * k), p(y + r * k)],
                      180, 360, fill=GOLD + (34,), width=p(2))
    # scattered gold coins/stars in the header
    for (x, y, rr) in [(110, 120, 7), (960, 90, 9), (900, 300, 5), (170, 330, 5), (80, 230, 4), (1000, 210, 4)]:
        o.ellipse([p(x - rr), p(y - rr), p(x + rr), p(y + rr)], fill=GOLD_LIGHT + (150,))
    img.alpha_composite(overlay)


def cat(img: Image.Image, cx: int, cy: int, scale: float = 1.0):
    """An original, simple lucky cat: round head, raised left paw, closed happy eyes, gold coin."""
    d = ImageDraw.Draw(img)

    def e(x0, y0, x1, y1, **kw):
        d.ellipse([p(cx + x0 * scale), p(cy + y0 * scale), p(cx + x1 * scale), p(cy + y1 * scale)], **kw)

    def poly(pts, **kw):
        d.polygon([(p(cx + x * scale), p(cy + y * scale)) for x, y in pts], **kw)

    def arc(box, a0, a1, **kw):
        x0, y0, x1, y1 = box
        d.arc([p(cx + x0 * scale), p(cy + y0 * scale), p(cx + x1 * scale), p(cy + y1 * scale)], a0, a1, **kw)

    lw = max(p(4 * scale), 2)
    outline = GOLD_DEEP

    def mascot_cat(img: Image.Image, cx: int, cy: int, scale: float = 1.0):
        """Place the lucky-cat PNG mascot on the card."""
    if not MASCOT.exists():
        fail(f"Missing mascot image: {MASCOT}", 2)

    mascot = Image.open(MASCOT).convert("RGBA")

    # Resize the mascot to fit the header nicely
    target_w = int(360 * scale * S)
    target_h = int(360 * scale * S)
    mascot.thumbnail((target_w, target_h), Image.LANCZOS)

    # Center it around (cx, cy)
    x = p(cx) - mascot.width // 2
    y = p(cy) - mascot.height // 2

    # Soft glow behind the mascot
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        [
            x - p(25),
            y - p(20),
            x + mascot.width + p(25),
            y + mascot.height + p(20),
        ],
        fill=GOLD_LIGHT + (55,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(p(20)))
    img.alpha_composite(glow)

    # Paste mascot
    img.alpha_composite(mascot, (x, y))

    # soft glow behind the cat
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([p(cx - 230 * scale), p(cy - 200 * scale), p(cx + 230 * scale), p(cy + 250 * scale)],
               fill=GOLD_LIGHT + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(p(40)))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)

    # body
    e(-130, 20, 130, 230, fill=WHITE, outline=outline, width=lw)
    # raised paw (behind head): a rounded arm drawn as a tube, then the paw
    path = [(-100 + (-133 + 100) * t, 40 + (-95 - 40) * t) for t in [i / 24 for i in range(25)]]
    for x, y in path:
        e(x - 30 - 4, y - 30 - 4, x + 30 + 4, y + 30 + 4, fill=outline)
    for x, y in path:
        e(x - 30, y - 30, x + 30, y + 30, fill=WHITE)
    e(-178, -140, -88, -50, fill=WHITE, outline=outline, width=lw)
    e(-150, -112, -116, -78, fill=PINK)
    # ears
    poly([(-112, -112), (-92, -205), (-30, -142)], fill=WHITE, outline=outline, width=lw)
    poly([(112, -112), (92, -205), (30, -142)], fill=WHITE, outline=outline, width=lw)
    poly([(-98, -128), (-88, -180), (-52, -145)], fill=PINK)
    poly([(98, -128), (88, -180), (52, -145)], fill=PINK)
    # head
    e(-128, -160, 128, 60, fill=WHITE, outline=outline, width=lw)
    # red patch on head
    e(40, -150, 110, -95, fill=RED_SOFT)
    # happy closed eyes
    arc((-78, -70, -26, -30), 200, 340, fill=INK, width=p(6 * scale))
    arc((26, -70, 78, -30), 200, 340, fill=INK, width=p(6 * scale))
    # blush
    e(-100, -30, -66, -8, fill=PINK)
    e(66, -30, 100, -8, fill=PINK)
    # nose + mouth
    poly([(-9, -22), (9, -22), (0, -12)], fill=RED)
    arc((-20, -18, 0, 2), 0, 180, fill=INK, width=p(4 * scale))
    arc((0, -18, 20, 2), 0, 180, fill=INK, width=p(4 * scale))
    # whiskers
    for y0, y1 in ((-14, -20), (0, 2)):
        d.line([(p(cx - 70 * scale), p(cy + y0 * scale)), (p(cx - 128 * scale), p(cy + y1 * scale))],
               fill=GOLD_DEEP, width=p(3 * scale))
        d.line([(p(cx + 70 * scale), p(cy + y0 * scale)), (p(cx + 128 * scale), p(cy + y1 * scale))],
               fill=GOLD_DEEP, width=p(3 * scale))
    # red collar + gold bell
    d.rounded_rectangle([p(cx - 100 * scale), p(cy + 50 * scale), p(cx + 100 * scale), p(cy + 74 * scale)],
                        radius=p(12 * scale), fill=RED, outline=RED_DEEP, width=p(2))
    e(-22, 62, 22, 104, fill=GOLD, outline=GOLD_DEEP, width=lw)
    d.line([(p(cx - 18 * scale), p(cy + 80 * scale)), (p(cx + 18 * scale), p(cy + 80 * scale))],
           fill=GOLD_DEEP, width=p(3 * scale))
    # koban coin held at the front, stamped 11:11
    e(-6, 110, 130, 220, fill=GOLD, outline=GOLD_DEEP, width=lw)
    e(8, 122, 116, 208, outline=GOLD_LIGHT, width=p(3 * scale))
    f = font("Fraunces.ttf", int(30 * scale), "Black")
    s = "11:11"
    tw = text_w(d, s, f)
    d.text((p(cx + 62 * scale) - tw // 2, p(cy + 146 * scale)), s, font=f, fill=RED_DEEP)
    # holding paw over the coin
    e(-40, 150, 20, 205, fill=WHITE, outline=outline, width=lw)


def chip_row(d, x: int, y: int, items: list[str], max_x: int, fill, text_fill, f) -> int:
    """Draw pill chips left to right, wrapping; returns the y below the last row."""
    pad_x, pad_y, gap, h = 22, 10, 12, 54
    cur_x = x
    for item in items:
        tw = text_w(d, item, f) // S
        w = tw + pad_x * 2
        if cur_x + w > max_x and cur_x > x:
            cur_x = x
            y += h + gap
        d.rounded_rectangle([p(cur_x), p(y), p(cur_x + w), p(y + h)], radius=p(h / 2), fill=fill)
        d.text((p(cur_x + pad_x), p(y + pad_y)), item, font=f, fill=text_fill)
        cur_x += w + gap
    return y + h


def render(plan: dict, out: Path):
    img = Image.new("RGBA", (p(W), p(H)), RED + (255,))
    background(img)

    mascot_path = ROOT / "assets" / "lucky_cat.png"
    mascot = Image.open(mascot_path).convert("RGBA")

    # Size and position of the new cat image
    mascot.thumbnail((p(390), p(390)), Image.Resampling.LANCZOS)

    x = (img.width - mascot.width) // 2
    y = p(292) - mascot.height // 2

    img.alpha_composite(mascot, (x, y))

    d = ImageDraw.Draw(img)

    # header wordmark
    f_small = font("DMSans.ttf", 26, "SemiBold")
    label = "M E O W - M E O W   ·   S T U D Y   P A C T"
    d.text((p(W / 2) - text_w(d, label, f_small) // 2, p(42)), label, font=f_small, fill=GOLD_LIGHT)

    # cream card
    top, left, right, bottom = 520, 64, W - 64, H - 110
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([p(left), p(top + 14), p(right), p(bottom + 14)],
                                             radius=p(44), fill=(60, 6, 10, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(p(18))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([p(left), p(top), p(right), p(bottom)], radius=p(44), fill=CREAM,
                        outline=GOLD, width=p(5))
    d.rounded_rectangle([p(left + 14), p(top + 14), p(right - 14), p(bottom - 14)], radius=p(34),
                        outline=GOLD_LIGHT, width=p(2))

    inner_l, inner_r = left + 56, right - 56
    y = top + 50

    title, f_title = fit(d, str(plan["title"]), "Fraunces.ttf", 68, "Black", inner_r - inner_l)
    d.text((p(inner_l), p(y)), title, font=f_title, fill=RED_DEEP)
    y += 92

    def row(label: str, value: str, y: int) -> int:
        f_l = font("DMSans.ttf", 24, "Bold")
        d.text((p(inner_l), p(y)), label.upper(), font=f_l, fill=GOLD_DEEP)
        v, f_v = fit(d, value, "DMSans.ttf", 40, "SemiBold", inner_r - inner_l)
        d.text((p(inner_l), p(y + 34)), v, font=f_v, fill=INK)
        return y + 96

    y = row("When", str(plan["when"]), y)
    y = row("Where", str(plan["where"]), y)

    f_chip = font("DMSans.ttf", 28, "SemiBold")
    for label, key, fill, tf in (("Crew", "crew", RED, CREAM), ("Focus", "focus", GOLD, RED_DEEP)):
        items = [str(i) for i in (plan.get(key) or []) if str(i).strip()]
        if len(items) > 6:
            items = items[:5] + [f"+{len(items) - 5}"]
        if not items or y > bottom - 200:
            continue
        d.text((p(inner_l), p(y)), label.upper(), font=font("DMSans.ttf", 24, "Bold"), fill=GOLD_DEEP)
        y = chip_row(d, inner_l, y + 36, items, inner_r, fill, tf, f_chip) + 22

    # luck line, pinned near the card bottom
    luck = str(plan.get("luck") or LUCK_LINES[sum(map(ord, str(plan["title"]))) % len(LUCK_LINES)])
    luck, f_luck = fit(d, luck, "Fraunces.ttf", 36, "SemiBold", inner_r - inner_l - 60)
    ly = bottom - 82
    d.line([(p(inner_l), p(ly - 22)), (p(inner_r), p(ly - 22))], fill=GOLD_LIGHT, width=p(2))
    lw = text_w(d, luck, f_luck)
    d.text((p(W / 2) - lw // 2, p(ly - 4)), luck, font=f_luck, fill=RED)

    # footer
    foot = "made with luck by meow-meow  ·  team 11:11"
    f_foot = font("DMSans.ttf", 24, "Medium")
    d.text((p(W / 2) - text_w(d, foot, f_foot) // 2, p(H - 70)), foot, font=f_foot, fill=GOLD_LIGHT)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").resize((W, H), Image.LANCZOS).save(out, "PNG", optimize=True)
    print(str(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", type=Path)
    g.add_argument("--sample", action="store_true")
    ap.add_argument("--out", type=Path, default=Path.home() / "meow-meow" / "card.png")
    a = ap.parse_args()
    render(load_plan(SAMPLE if a.sample else a.input), a.out.expanduser())


if __name__ == "__main__":
    main()
