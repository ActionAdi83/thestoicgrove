"""Slide rendering: cover, quote slides and the closing call-to-action slide."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
LIGHT = (250, 248, 240)
DARK = (20, 34, 28)


def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    if weight:
        f.set_variation_by_axes([weight])
    return f


def _lum(img, box):
    arr = np.asarray(img.crop(box).convert("L"), dtype=np.float32)
    return float(arr.mean())


def _wrap(draw, text, fnt, max_w):
    """Greedy wrap, then shrink the width while the line count stays the same (balanced lines)."""
    def greedy(width):
        lines, cur = [], ""
        for word in text.split():
            test = f"{cur} {word}".strip()
            if draw.textlength(test, font=fnt) <= width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    lines = greedy(max_w)
    width = max_w
    while width > max_w * 0.55:
        trial = greedy(width - 20)
        if len(trial) != len(lines):
            break
        lines, width = trial, width - 20
    return lines


def _spaced(draw, xy, text, fnt, fill, spacing, anchor_center=True):
    """Draw text with letter spacing, horizontally centred on xy[0]."""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = xy[0] - total / 2 if anchor_center else xy[0]
    for c, w in zip(text, widths):
        draw.text((x, xy[1]), c, font=fnt, fill=fill)
        x += w + spacing
    return total


def _shadow_layer(size, draw_fn, color, blur):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), color)
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _prepare(bg, sky_bottom=None):
    """Returns (RGBA image, text colour, text region box) with contrast fixes applied.

    sky_bottom: for procedural art, the y where the landscape starts; text goes in the sky above it.
    None means a photo: darken it and use the full frame.
    """
    img = bg.convert("RGBA")
    if sky_bottom is None or sky_bottom < 560:
        # darken the whole photo with a soft vignette so white text always reads
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
        alpha = (95 + 120 * d).clip(0, 200).astype(np.uint8)
        overlay = np.zeros((H, W, 4), np.uint8)
        overlay[..., 3] = alpha
        img.alpha_composite(Image.fromarray(overlay, "RGBA"))
        return img, LIGHT, (90, 200, W - 90, H - 220)
    region = (90, 150, W - 90, min(int(H * 0.6), sky_bottom - 30))
    color = DARK if _lum(img, region) > 150 else LIGHT
    return img, color, region


def _prepare_misted(bg, sky_bottom):
    """For long quotes over generated art: let a band of mist (sky colour) rise over the trees."""
    img = bg.convert("RGBA")
    mist_color = np.asarray(img.crop((0, max(0, sky_bottom - 80), W, max(1, sky_bottom - 20))).convert("RGB")).reshape(-1, 3).mean(0)
    bottom = int(H * 0.8)
    ys = np.arange(H, dtype=np.float32)
    alpha = np.clip((ys - (sky_bottom - 120)) / 160, 0, 1) * np.clip((bottom - ys) / 200, 0, 1) * 225
    overlay = np.zeros((H, W, 4), np.uint8)
    overlay[..., :3] = mist_color.astype(np.uint8)
    overlay[..., 3] = alpha[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(overlay, "RGBA"))
    region = (90, 150, W - 90, bottom - 60)
    color = DARK if _lum(img, region) > 150 else LIGHT
    return img, color, region


def _footer(img, handle, page=None):
    d = ImageDraw.Draw(img)
    bottom_lum = _lum(img, (0, H - 120, W, H))
    col = LIGHT if bottom_lum < 140 else DARK
    f = font("Montserrat.ttf", 24, 500)
    _spaced(d, (W / 2, H - 78), handle.upper(), f, col + (210,), 3)
    if page:
        f2 = font("Montserrat.ttf", 22, 500)
        top_col = LIGHT if _lum(img, (W - 160, 30, W - 30, 90)) < 150 else DARK
        d.text((W - 60, 56), page, font=f2, fill=top_col + (190,), anchor="rs")


def _draw_block(img, color, blocks, region, gap=34):
    """blocks: list of (lines, font, line_height, fill, letter_spacing). Centred vertically in region."""
    d = ImageDraw.Draw(img)
    heights = [len(lines) * lh for lines, _, lh, _, _ in blocks]
    total = sum(heights) + gap * (len(blocks) - 1)
    y = region[1] + (region[3] - region[1] - total) / 2
    cx = (region[0] + region[2]) / 2
    shadow_col = (0, 0, 0, 120) if color == LIGHT else (255, 255, 255, 90)

    def paint(draw, fill_override=None):
        yy = y
        for (lines, fnt, lh, fill, spacing), h in zip(blocks, heights):
            for i, line in enumerate(lines):
                f = fill_override or fill
                if spacing:
                    _spaced(draw, (cx, yy + i * lh), line, fnt, f, spacing)
                else:
                    draw.text((cx, yy + i * lh), line, font=fnt, fill=f, anchor="ma")
            yy += h + gap

    img.alpha_composite(_shadow_layer(img.size, lambda dd, c: paint(dd, c), shadow_col, 10))
    paint(d)
    return y, total


def _fit_quote(d, text, region):
    max_w = region[2] - region[0] - 40
    avail_h = region[3] - region[1] - 260
    size = 58
    while True:
        qf = font("Lora-Italic.ttf", size, 450)
        lines = _wrap(d, text, qf, max_w)
        lh = int(size * 1.38)
        if len(lines) * lh <= avail_h or size <= 28:
            return size, qf, lines, lh
        size -= 2


def quote_slide(bg, quote, handle, page, sky_bottom=None):
    img, color, region = _prepare(bg, sky_bottom)
    d = ImageDraw.Draw(img)
    text = quote["text"].strip()
    max_w = region[2] - region[0] - 40
    size, qf, lines, lh = _fit_quote(d, text, region)
    if size < 40 and sky_bottom is not None and sky_bottom >= 560:  # too long for the open sky
        img, color, region = _prepare_misted(bg, sky_bottom)
        d = ImageDraw.Draw(img)
        max_w = region[2] - region[0] - 40
        size, qf, lines, lh = _fit_quote(d, text, region)
    af = font("Montserrat.ttf", 28, 600)
    blocks = [(lines, qf, lh, color + (255,), 0), ([f"— {quote['author'].upper()}"], af, 40, color + (235,), 4)]
    if quote.get("source"):
        sf = font("Lora-Italic.ttf", 24, 400)
        src_lines = _wrap(d, quote["source"], sf, max_w * 0.8)
        blocks.append((src_lines, sf, 32, color + (185,), 0))
    y, total = _draw_block(img, color, blocks, region)
    # decorative opening quote mark above the text
    mf = font("PlayfairDisplay.ttf", 150, 700)
    box = d.textbbox((0, 0), "“", font=mf)
    top = max(30, y - 30 - (box[3] - box[1]))
    d.text((W / 2 - (box[0] + box[2]) / 2, top - box[1]), "“", font=mf, fill=color + (90,))
    _footer(img, handle, page)
    return img.convert("RGB")


def cover_slide(bg, kicker, title, subtitle, handle, sky_bottom=None):
    img, color, region = _prepare(bg, sky_bottom)
    d = ImageDraw.Draw(img)
    max_w = region[2] - region[0] - 20
    size = 104
    while size > 56:
        tf = font("PlayfairDisplay.ttf", size, 700)
        tlines = _wrap(d, title, tf, max_w)
        if len(tlines) <= 3:
            break
        size -= 4
    kf = font("Montserrat.ttf", 28, 600)
    sf = font("Lora-Italic.ttf", 34, 400)
    blocks = [
        ([kicker.upper()], kf, 44, color + (220,), 6),
        (tlines, tf, int(size * 1.12), color + (255,), 0),
        (_wrap(d, subtitle, sf, max_w * 0.85), sf, 46, color + (225,), 0),
    ]
    y, total = _draw_block(img, color, blocks, region, gap=30)
    # thin rule under the block plus swipe hint
    rule_y = y + total + 40
    d.line([(W / 2 - 60, rule_y), (W / 2 + 60, rule_y)], fill=color + (200,), width=2)
    hf = font("Montserrat.ttf", 24, 600)
    _spaced(d, (W / 2, rule_y + 26), "SWIPE  →", hf, color + (210,), 4)
    _footer(img, handle)
    return img.convert("RGB")


def cta_slide(bg, handle, question, sky_bottom=None):
    img, color, region = _prepare(bg, sky_bottom)
    d = ImageDraw.Draw(img)
    max_w = region[2] - region[0] - 40
    qf = font("PlayfairDisplay.ttf", 64, 600)
    lf = font("Lora-Italic.ttf", 36, 400)
    hf = font("Montserrat.ttf", 32, 700)
    blocks = [
        (_wrap(d, question, qf, max_w), qf, 80, color + (255,), 0),
        (["Save this for the days you need it.", "Share it with someone who does."], lf, 52, color + (230,), 0),
        (["FOLLOW " + handle.upper()], hf, 44, color + (255,), 5),
    ]
    _draw_block(img, color, blocks, region, gap=46)
    _footer(img, handle)
    return img.convert("RGB")
