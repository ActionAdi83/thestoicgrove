"""Command line entry point.

    python -m src.main preview [--count 3]        render the next carousel(s) to preview/ (state untouched)
    python -m src.main build --out out            plan + render the next carousel into out/ (post.json + JPEGs)
    python -m src.main publish --post out/post.json --base-url https://.../   publish and record history
    python -m src.main check                      verify the Instagram token and show quota
    python -m src.main refresh-token              print a refreshed long-lived token
    python -m src.main stats                      library size per theme/author and how long it lasts
"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import sys
from collections import Counter

from . import backgrounds, caption, content, render
from .instagram import Instagram, refresh_token

PEXELS_QUERY = {"nature": "forest path", "solitude": "misty forest", "patience": "old trees", "mortality": "autumn forest",
                "change": "autumn forest", "time": "forest sunrise", "simplicity": "single tree", "fear": "dark forest fog"}


def _today():
    return dt.datetime.now(dt.timezone.utc).date()


def build_post(out_dir, seed=None, history=None):
    cfg, themes = content.load_json("config.json"), content.load_json("themes.json")
    quotes = content.load_quotes()
    history = history or content.load_history()
    rng = random.Random(seed)
    from .planner import plan_carousel
    plan = plan_carousel(quotes, themes, cfg, history, rng, _today())

    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".jpg"):
            os.remove(os.path.join(out_dir, f))

    handle = cfg["handle"]
    total = len(plan["quotes"]) + 2
    pexels = backgrounds.make_background_source(rng, history.get("photos", []))
    palette = rng.choice(list(backgrounds.PALETTES))
    query = PEXELS_QUERY.get(plan["key"], rng.choice(backgrounds.PEXELS_QUERIES))
    photos = []

    def bg(i):
        if pexels:
            try:
                img, pid, _ = pexels.get(query)
                photos.append(pid)
                return img, None
            except Exception as e:  # noqa: BLE001  fall back to generated art if Pexels fails
                print(f"Pexels failed ({e}); using generated background", file=sys.stderr)
        img, meta = backgrounds.procedural(rng.randint(0, 2**31), palette=palette)
        return img, meta["sky_bottom"]

    kicker, title, subtitle = caption.cover_text(plan, themes, rng)
    files = []
    img, sky = bg(0)
    slides = [render.cover_slide(img, kicker, title, subtitle, handle, sky)]
    for i, q in enumerate(plan["quotes"], start=2):
        img, sky = bg(i)
        slides.append(render.quote_slide(img, q, handle, f"{i - 1}/{total - 2}", sky))
    img, sky = bg(total)
    slides.append(render.cta_slide(img, handle, rng.choice(themes["cta_questions"]), sky))

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    for i, s in enumerate(slides, 1):
        name = f"{stamp}-{i:02d}.jpg"
        s.save(os.path.join(out_dir, name), quality=92, optimize=True, progressive=True)
        files.append(name)

    post = {
        "kind": plan["kind"], "key": plan["key"], "title": title,
        "quote_ids": [q["id"] for q in plan["quotes"]],
        "quotes": [f'{q["text"]} — {q["author"]}' for q in plan["quotes"]],
        "caption": caption.caption(plan, themes, handle, rng),
        "images": files, "photos": photos,
    }
    with open(os.path.join(out_dir, "post.json"), "w", encoding="utf-8") as f:
        json.dump(post, f, indent=1, ensure_ascii=False)
    return post


def _contact_sheet(folder, names, cols=5):
    from PIL import Image
    tw, th = 324, 405
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "white")
    for i, n in enumerate(names):
        im = Image.open(os.path.join(folder, n)).resize((tw, th))
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(os.path.join(folder, "_overview.jpg"), quality=88)


def record(post, result):
    history = content.load_history()
    day = _today().isoformat()
    for qid in post["quote_ids"]:
        history["quotes"][qid] = day
    history["posts"].append({"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             "kind": post["kind"], "key": post["key"], "title": post["title"], **result})
    history["photos"] = (history.get("photos", []) + post.get("photos", []))[-3000:]
    content.save_history(history)


def _client():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("IG_ACCESS_TOKEN is not set")
    return Instagram(token, content.load_json("config.json")["api_version"])


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.main")
    sub = p.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("preview")
    pv.add_argument("--count", type=int, default=1)
    pv.add_argument("--seed", type=int)
    b = sub.add_parser("build")
    b.add_argument("--out", default="out")
    b.add_argument("--seed", type=int)
    pb = sub.add_parser("publish")
    pb.add_argument("--post", default="out/post.json")
    pb.add_argument("--base-url", required=True)
    pb.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    sub.add_parser("refresh-token")
    sub.add_parser("stats")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji in captions on Windows consoles

    if a.cmd == "preview":
        root = os.path.join(content.ROOT, "preview")
        history = content.load_history()
        for k in range(a.count):
            out = os.path.join(root, f"post_{k + 1}")
            shutil.rmtree(out, ignore_errors=True)
            post = build_post(out, None if a.seed is None else a.seed + k, history)
            # pretend it was posted so the next preview picks different content
            for qid in post["quote_ids"]:
                history["quotes"][qid] = _today().isoformat()
            history["posts"].append({"key": post["key"]})
            _contact_sheet(out, post["images"])
            print(f"\n=== {out}  [{post['kind']}: {post['key']}] {post['title']}")
            print(post["caption"])
    elif a.cmd == "build":
        post = build_post(a.out, a.seed)
        print(f"[{post['kind']}: {post['key']}] {post['title']} -> {len(post['images'])} slides in {a.out}")
    elif a.cmd == "publish":
        with open(a.post, encoding="utf-8") as f:
            post = json.load(f)
        base = a.base_url.rstrip("/") + "/"
        urls = [base + name for name in post["images"]]
        if a.dry_run:
            print("DRY RUN, would publish:", *urls, "", post["caption"], sep="\n")
            return
        ig = _client()
        print(f"Publishing to @{ig.me()['username']}: {post['title']}")
        result = ig.publish_carousel(urls, post["caption"])
        record(post, result)
        print(f"Published: {result['permalink']}")
    elif a.cmd == "check":
        ig = _client()
        print(json.dumps(ig.me(), indent=1))
        print(json.dumps(ig.publishing_limit(), indent=1))
    elif a.cmd == "refresh-token":
        token, expires = refresh_token(os.environ.get("IG_ACCESS_TOKEN", "").strip())
        print(token)
        print(f"expires in {int(expires or 0) // 86400} days", file=sys.stderr)
    elif a.cmd == "stats":
        cfg, themes = content.load_json("config.json"), content.load_json("themes.json")
        quotes = content.load_quotes()
        tags = Counter(t for q in quotes for t in q["tags"])
        authors = Counter(q["author"] for q in quotes)
        print(f"{len(quotes)} quotes, {len(authors)} authors")
        print("themes:", ", ".join(f"{k} {v}" for k, v in tags.most_common()))
        print("authors:", ", ".join(f"{k} {v}" for k, v in authors.most_common()))
        per_day = 3 * cfg["quotes_per_post"]
        print(f"at 3 posts/day x {cfg['quotes_per_post']} quotes: {len(quotes) / per_day:.0f} days before any quote repeats")


if __name__ == "__main__":
    main()
