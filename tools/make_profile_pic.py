"""Profile picture: a single pine in front of a soft sun, misty forest behind."""
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.backgrounds import PALETTES, _fog_band, _lerp, _pine, _sun_glow, _tree_layer, _vertical_gradient  # noqa: E402

S = 2160  # draw at 2x, save 1080


def make(palette, seed, out):
    rng = random.Random(seed)
    sky_top, sky_bot, fog, far, near, glow = PALETTES[palette]
    img = Image.fromarray(_vertical_gradient(sky_top, sky_bot, S, S).astype(np.uint8)).convert("RGBA")
    img.alpha_composite(_sun_glow(S, S, S / 2, S * 0.42, S * 0.5, glow, 170))
    d = ImageDraw.Draw(img)
    r = S * 0.2  # sun disc
    d.ellipse([S / 2 - r, S * 0.42 - r, S / 2 + r, S * 0.42 + r], fill=_lerp(glow, sky_bot, 0.25) + (235,))
    for i, (g, th) in enumerate([(0.70, 0.10), (0.80, 0.13)]):
        img.alpha_composite(_tree_layer(rng, S, S, S * g, S * th, _lerp(far, near, 0.25 + 0.3 * i) + (255,), "pine", 1.3))
        img.alpha_composite(_fog_band(S, S, S * g, S * 0.04, fog, 130))
    hero = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hero)
    hd.rectangle([0, S * 0.9, S, S], fill=near + (255,))
    _pine(hd, S / 2, S * 0.93, S * 0.68, near + (255,), random.Random(seed + 1))
    img.alpha_composite(hero)
    img.convert("RGB").resize((1080, 1080), Image.LANCZOS).save(out, quality=95)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for i, pal in enumerate(["misty_morning", "deep_forest", "golden_hour"], 1):
        make(pal, 40 + i, os.path.join(root, "brand", f"profile_{i}.jpg"))
