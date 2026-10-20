"""Decides what the next carousel is about and which quotes go in it."""
import datetime as dt
import math
from collections import defaultdict


def _days_since(date_str, today):
    if not date_str:
        return 10_000
    return (today - dt.date.fromisoformat(date_str[:10])).days


def plan_carousel(quotes, themes, config, history, rng, today=None):
    """Returns dict(kind, key, quotes) where kind is 'theme' or 'author'."""
    today = today or dt.date.today()
    n = min(config["quotes_per_post"], 8)  # cover + 8 quotes + CTA = 10 slides (API maximum)
    cooldown = config["quote_cooldown_days"]
    used = history["quotes"]
    recent = {p["key"] for p in history["posts"][-config["recent_posts_without_repeat"]:]}
    fresh = [q for q in quotes if _days_since(used.get(q["id"]), today) >= cooldown]

    by_theme, by_author = defaultdict(list), defaultdict(list)
    for q in fresh:
        by_author[q["author"]].append(q)
        for t in q["tags"]:
            if t in themes["themes"]:
                by_theme[t].append(q)

    options = []
    for key, qs in by_theme.items():
        if len(qs) >= n and key not in recent:
            options.append(("theme", key, len(qs)))
    for key, qs in by_author.items():
        if len(qs) >= n and key not in recent:
            options.append(("author", key, len(qs)))

    if not options:  # library exhausted for now: fall back to least recently used quotes on any theme
        return _fallback(quotes, themes, used, n, rng)

    share = config["author_carousel_share"]
    weights = []
    for kind, key, count in options:
        w = math.sqrt(count) * (share if kind == "author" else 1 - share)
        if kind == "author" and key in config["stoic_core"]:
            w *= 2.5  # the core Stoics are the identity of the account
        weights.append(w)
    kind, key, _ = rng.choices(options, weights=weights)[0]
    pool = by_theme[key] if kind == "theme" else by_author[key]
    picked = _pick(pool, n, kind, config, used, rng)
    return {"kind": kind, "key": key, "quotes": picked}


def _pick(pool, n, kind, config, used, rng):
    pool = pool[:]
    rng.shuffle(pool)
    pool.sort(key=lambda q: used.get(q["id"], ""))  # never-used first, then oldest
    if kind == "author":
        picked = pool[:n]
    else:
        core = set(config["stoic_core"])
        per_author = defaultdict(int)
        picked = []
        # first guarantee a few core Stoic voices, then fill with variety
        for want_core in (True, False):
            for q in pool:
                if len(picked) >= n or q in picked:
                    continue
                if want_core and (q["author"] not in core or
                                  sum(p["author"] in core for p in picked) >= config["min_stoic_per_theme_post"]):
                    continue
                if per_author[q["author"]] >= config["max_per_author_in_theme_post"]:
                    continue
                picked.append(q)
                per_author[q["author"]] += 1
        for q in pool:  # still short (few authors on this theme): relax the per-author cap
            if len(picked) >= n:
                break
            if q not in picked:
                picked.append(q)
    # open with a short, punchy quote; the rest in random order
    picked.sort(key=lambda q: len(q["text"]))
    first, rest = picked[0], picked[1:]
    rng.shuffle(rest)
    return [first] + rest


def _fallback(quotes, themes, used, n, rng):
    by_theme = defaultdict(list)
    for q in quotes:
        for t in q["tags"]:
            if t in themes["themes"]:
                by_theme[t].append(q)
    key = rng.choice([k for k, v in by_theme.items() if len(v) >= n])
    pool = sorted(by_theme[key], key=lambda q: (used.get(q["id"], ""), rng.random()))
    return {"kind": "theme", "key": key, "quotes": pool[:n]}
