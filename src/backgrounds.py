"""Background images: procedural forest landscapes (free, no API key) or Pexels photos."""
import io
import math
import os
import random

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1350
SS = 2  # supersampling factor for smooth tree edges

# Each palette: sky top, sky bottom (horizon), fog, far layer, near layer, sun glow
PALETTES = {
    "misty_morning": [(150, 178, 170), (226, 230, 214), (222, 228, 214), (128, 158, 148), (18, 40, 34), (255, 246, 220)],
    "golden_hour":   [(92, 120, 140), (246, 196, 132), (238, 200, 150), (150, 128, 110), (22, 30, 24), (255, 214, 150)],
    "deep_forest":   [(28, 56, 52), (108, 150, 128), (120, 158, 136), (60, 98, 84), (8, 20, 16), (210, 240, 200)],
    "blue_dusk":     [(28, 40, 72), (150, 160, 180), (140, 152, 170), (78, 92, 112), (8, 14, 22), (240, 220, 200)],
    "spring_green":  [(120, 176, 196), (220, 236, 206), (214, 232, 200), (112, 160, 110), (22, 54, 30), (255, 250, 220)],
    "autumn_haze":   [(120, 104, 108), (236, 190, 150), (226, 184, 150), (160, 110, 82), (36, 24, 18), (255, 220, 170)],
    "night_pines":   [(8, 14, 30), (44, 62, 88), (52, 70, 96), (34, 50, 70), (4, 8, 12), (220, 230, 255)],
}

SCENES = ["pine_forest", "rolling_hills", "misty_lake"]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _vertical_gradient(top, bottom, w, h):
    t = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    return np.repeat(arr, w, axis=1)


def _ridge(rng, w, base, amp, octaves=4):
    """Smooth random ridge line (list of y per x) made from summed sines."""
    x = np.arange(w)
    y = np.full(w, float(base))
    for o in range(octaves):
        freq = (o + 1) ** 1.6 * rng.uniform(0.6, 1.4) / w * math.pi * 2
        phase = rng.uniform(0, math.pi * 2)
        y += np.sin(x * freq + phase) * amp / (o + 1) ** 1.3
    return y


def _pine(draw, x, ground, height, color, rng):
    """Layered pine silhouette with slightly jagged tiers."""
    width = height * rng.uniform(0.32, 0.42)
    tiers = rng.randint(5, 9)
    trunk_w = max(2, width * 0.06)
    draw.rectangle([x - trunk_w, ground - height * 0.12, x + trunk_w, ground + 4], fill=color)
    for i in range(tiers):
        t = i / tiers
        tier_bottom = ground + height * 0.02 - t * height * 0.88
        tier_top = tier_bottom - height * (0.32 - 0.15 * t)
        half = width * (1 - t) * 0.5 + width * 0.05
        jag = half * rng.uniform(-0.12, 0.12)
        draw.polygon([(x - half - jag, tier_bottom), (x, tier_top), (x + half + jag, tier_bottom)], fill=color)
    draw.polygon([(x - width * 0.06, ground - height * 0.9), (x, ground - height * 1.02), (x + width * 0.06, ground - height * 0.9)], fill=color)


def _broadleaf(draw, x, ground, height, color, rng):
    """Deciduous tree: trunk plus a cluster of overlapping blobs."""
    trunk_w = max(2, height * 0.035)
    draw.rectangle([x - trunk_w, ground - height * 0.45, x + trunk_w, ground + 4], fill=color)
    crown_r = height * rng.uniform(0.26, 0.34)
    cy = ground - height + crown_r
    for _ in range(rng.randint(6, 10)):
        ox = rng.uniform(-crown_r * 0.8, crown_r * 0.8)
        oy = rng.uniform(-crown_r * 0.5, crown_r * 0.7)
        r = crown_r * rng.uniform(0.45, 0.75)
        draw.ellipse([x + ox - r, cy + oy - r, x + ox + r, cy + oy + r], fill=color)


def _tree_layer(rng, w, h, ground_y, tree_h, color, kind, density):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ground = _ridge(rng, w, ground_y, tree_h * 0.25)
    # solid ground under the trees
    pts = [(x, ground[x]) for x in range(0, w, 4)] + [(w, h), (0, h)]
    d.polygon(pts, fill=color)
    x = rng.uniform(-tree_h * 0.2, 0)
    while x < w + tree_h * 0.3:
        gx = int(min(max(x, 0), w - 1))
        th = tree_h * rng.uniform(0.6, 1.15)
        if kind == "pine" or (kind == "mixed" and rng.random() < 0.6):
            _pine(d, x, ground[gx] + tree_h * 0.04, th, color, rng)
        else:
            _broadleaf(d, x, ground[gx] + tree_h * 0.04, th, color, rng)
        x += tree_h * rng.uniform(0.12, 0.32) / density
    return layer


def _hill_layer(rng, w, h, base_y, amp, color, trees=0, tree_h=0):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ridge = _ridge(rng, w, base_y, amp, octaves=3)
    d.polygon([(x, ridge[x]) for x in range(0, w, 4)] + [(w, h), (0, h)], fill=color)
    for _ in range(trees):
        x = rng.uniform(0, w)
        th = tree_h * rng.uniform(0.6, 1.2)
        if rng.random() < 0.15:  # mostly pines: big round broadleaf crowns look cartoonish
            _broadleaf(d, x, ridge[int(x) % w] + 6, th * 0.7, color, rng)
        else:
            _pine(d, x, ridge[int(x) % w] + 6, th, color, rng)
    return layer


def _fog_band(w, h, y_center, thickness, color, alpha):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = color
    ys = np.arange(h)
    a = np.exp(-((ys - y_center) / thickness) ** 2) * alpha
    arr[..., 3] = a[:, None].astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _sun_glow(w, h, cx, cy, radius, color, strength):
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / radius
    a = np.clip(np.exp(-dist ** 2) * strength, 0, 255).astype(np.uint8)
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a
    return Image.fromarray(arr, "RGBA")


def _stars(img, rng, count):
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x, y = rng.uniform(0, img.width), rng.uniform(0, img.height * 0.45)
        r = rng.uniform(0.6, 1.8) * SS
        b = rng.randint(150, 255)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20), 255))


def _grain(img, rng, amount=7):
    arr = np.asarray(img).astype(np.int16)
    noise = np.random.default_rng(rng.randint(0, 2**31)).normal(0, amount, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def procedural(seed, palette=None, scene=None):
    rng = random.Random(seed)
    palette_name = palette or rng.choice(list(PALETTES))
    scene = scene or rng.choice(SCENES)
    sky_top, sky_bot, fog, far, near, glow = PALETTES[palette_name]
    w, h = W * SS, H * SS

    img = Image.fromarray(_vertical_gradient(sky_top, sky_bot, w, h).astype(np.uint8)).convert("RGBA")
    if palette_name == "night_pines":
        _stars(img, rng, 260)
    sun_y = h * rng.uniform(0.28, 0.48)
    img.alpha_composite(_sun_glow(w, h, w * rng.uniform(0.25, 0.75), sun_y, w * 0.45, glow, 150))
    sky = np.asarray(img.convert("L"), dtype=np.int16)

    if scene == "pine_forest":
        layers, horizon = rng.randint(5, 7), rng.uniform(0.6, 0.68)
        for i in range(layers):
            t = i / (layers - 1)
            color = _lerp(far, near, t ** 1.4)
            ground = h * (horizon + (1.02 - horizon) * t ** 1.3)
            tree_h = h * (0.07 + 0.30 * t ** 1.8)
            img.alpha_composite(_tree_layer(rng, w, h, ground, tree_h, color + (255,), "pine", 1.25 - 0.3 * t))
            if i < layers - 1:
                img.alpha_composite(_fog_band(w, h, ground, h * 0.05, fog, 150 - 15 * i))
    elif scene == "rolling_hills":
        layers = rng.randint(4, 6)
        for i in range(layers):
            t = i / (layers - 1)
            color = _lerp(far, near, t ** 1.3)
            base = h * (0.55 + 0.38 * t ** 1.2)
            trees = int(rng.randint(2, 10) * (0.5 + t))
            img.alpha_composite(_hill_layer(rng, w, h, base, h * (0.03 + 0.04 * t), color + (255,), trees, h * (0.05 + 0.25 * t ** 2)))
            if i < layers - 1:
                img.alpha_composite(_fog_band(w, h, base, h * 0.04, fog, 120))
    else:  # misty_lake: forest on the far shore mirrored in still water
        shore = h * rng.uniform(0.62, 0.7)
        top = Image.new("RGBA", (w, int(shore)), (0, 0, 0, 0))
        top.alpha_composite(img.crop((0, 0, w, int(shore))))
        for i in range(3):
            t = i / 2
            color = _lerp(far, _lerp(far, near, 0.75), t)
            layer = _tree_layer(rng, w, int(shore), shore * (0.88 + 0.07 * t), h * (0.05 + 0.08 * t), color + (255,), "pine", 1.1)
            top.alpha_composite(layer)
            top.alpha_composite(_fog_band(w, int(shore), shore * (0.86 + 0.08 * t), h * 0.03, fog, 110))
        reflection = top.transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(3 * SS))
        water = Image.new("RGBA", (w, h - int(shore)), (0, 0, 0, 0))
        water.alpha_composite(reflection.crop((0, 0, w, h - int(shore))))
        tint = _vertical_gradient(_lerp(fog, near, 0.4), near, w, h - int(shore)).astype(np.uint8)
        tint_img = Image.fromarray(tint).convert("RGBA")
        water = Image.blend(water, tint_img, 0.45)
        d = ImageDraw.Draw(water)
        for _ in range(60):  # ripples
            y = rng.uniform(0, water.height)
            x = rng.uniform(0, w)
            ln = rng.uniform(40, 220) * SS
            d.line([(x, y), (x + ln, y)], fill=fog + (rng.randint(20, 60),), width=SS)
        img.paste(top, (0, 0))
        img.paste(water, (0, int(shore)))
        img.alpha_composite(_fog_band(w, h, shore, h * 0.025, fog, 140))

    # first row (from the top) where the landscape noticeably departs from the empty sky
    diff = np.abs(np.asarray(img.convert("L"), dtype=np.int16) - sky) > 12
    rows = np.nonzero(diff.mean(axis=1) > 0.01)[0]
    sky_bottom = int(rows[0] / SS) if len(rows) else H

    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    return _grain(img, rng), {"name": f"{scene}/{palette_name}", "sky_bottom": sky_bottom}


# ---------------------------------------------------------------- Pexels

PEXELS_QUERIES = [
    "misty forest", "pine forest", "forest path", "sunlight forest", "green forest",
    "mountain forest", "moss forest", "forest fog", "green hills", "tall trees",
    "forest canopy", "autumn forest", "forest lake", "redwood forest", "fern forest",
]


def _cover_crop(img, w=W, h=H):
    scale = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


class PexelsSource:
    """Free stock photos (https://www.pexels.com/api/). Needs PEXELS_API_KEY."""

    def __init__(self, api_key, used_ids, rng):
        self.key = api_key
        self.used = set(used_ids)
        self.rng = rng
        self.pool = []

    def _fill(self, query):
        page = self.rng.randint(1, 8)
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": self.key},
            params={"query": query, "orientation": "portrait", "per_page": 40, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        photos = [p for p in r.json().get("photos", []) if p["id"] not in self.used]
        self.rng.shuffle(photos)
        self.pool.extend(photos)

    def get(self, query):
        tries = 0
        while not self.pool and tries < 4:
            self._fill(query if tries == 0 else self.rng.choice(PEXELS_QUERIES))
            tries += 1
        if not self.pool:
            raise RuntimeError("Pexels returned no unused photos")
        photo = self.pool.pop()
        self.used.add(photo["id"])
        data = requests.get(photo["src"]["large2x"], timeout=60).content
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return _cover_crop(img), photo["id"], photo.get("photographer", "")


def make_background_source(rng, used_photo_ids):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    return PexelsSource(key, used_photo_ids, rng) if key else None
