"""Makes the tall Pinterest-style cover image (1000x1500) with Pillow. No AI image service needed."""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 1500
FONT_DIR = Path(__file__).resolve().parent / "fonts"

# (background, text, accent)
PALETTES = [
    ("#1D2B2F", "#E9ECE6", "#C9A24B"),  # slate / limewash / ochre
    ("#2E6B5E", "#F1F2EC", "#E3D9A8"),  # verdigris
    ("#E9ECE6", "#1D2B2F", "#2E6B5E"),  # limewash
    ("#3A3F58", "#EEF0F5", "#D9B38C"),  # dusk
    ("#C9D3C4", "#1D2B2F", "#3A3F58"),  # sage
    ("#2B2B2B", "#F0EEE8", "#8FB8A8"),  # charcoal
]


def _font(name, size):
    for path in (FONT_DIR / name, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_cover(headline, subline, site_name, seed, out_path):
    idx = int(hashlib.sha1(seed.encode("utf-8")).hexdigest(), 16) % len(PALETTES)
    bg, fg, accent = PALETTES[idx]
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # drawing-sheet frame and title block
    m = 44
    d.rectangle([m, m, W - m, H - m], outline=accent, width=4)
    block_y = H - m - 190
    d.line([m, block_y, W - m, block_y], fill=accent, width=4)

    # headline: biggest size that fits in the box
    x, max_w, top, max_h = 96, W - 2 * 96, 190, 760
    chosen = None
    for size in range(200, 84, -6):
        f = _font("BarlowCondensed-Bold.ttf", size)
        lines = _wrap(d, headline, f, max_w)
        line_h = int(size * 1.02)
        widest = max((d.textlength(l, font=f) for l in lines), default=0)
        if len(lines) <= 6 and len(lines) * line_h <= max_h and widest <= max_w:
            chosen = (f, lines, line_h)
            break
    if chosen is None:
        f = _font("BarlowCondensed-Bold.ttf", 84)
        chosen = (f, _wrap(d, headline, f, max_w)[:6], int(84 * 1.02))
    f, lines, line_h = chosen
    y = top
    for line in lines:
        d.text((x, y), line, font=f, fill=fg)
        y += line_h

    if subline:
        sf = _font("Barlow-Regular.ttf", 54)
        y += 36
        for line in _wrap(d, subline, sf, max_w)[:2]:
            d.text((x, y), line, font=sf, fill=accent)
            y += 66

    # title block: site name left, small plan symbol right
    nf = _font("BarlowCondensed-Bold.ttf", 64)
    d.text((m + 52, block_y + 62), site_name, font=nf, fill=fg)
    sx, sy, s = W - m - 52 - 78, block_y + 56, 78
    d.rectangle([sx, sy, sx + s, sy + s], outline=fg, width=4)
    d.rectangle([sx + 20, sy + 20, sx + s - 20, sy + s - 20], outline=accent, width=4)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path
