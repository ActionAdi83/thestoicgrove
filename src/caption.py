"""Cover texts and Instagram captions."""


def cover_text(plan, themes, rng):
    n = len(plan["quotes"])
    if plan["kind"] == "theme":
        t = themes["themes"][plan["key"]]
        return f"{n} quotes on", rng.choice(t["titles"]), t["subtitle"]
    author = plan["key"]
    meta = themes["authors"].get(author, {})
    title = rng.choice(themes["author_titles"]).format(author=author)
    kicker = f"{n} lessons from" if title == author else f"{n} quotes"
    return kicker, title, meta.get("subtitle", "Timeless wisdom")


def caption(plan, themes, handle, rng):
    n = len(plan["quotes"])
    authors = list(dict.fromkeys(q["author"] for q in plan["quotes"]))
    if plan["kind"] == "theme":
        t = themes["themes"][plan["key"]]
        hook = rng.choice(t["hooks"])
        specific = t["hashtags"]
        featured = "Featuring " + " · ".join(authors)
    else:
        author = plan["key"]
        hook = rng.choice(themes["author_hooks"]).format(author=author, n=n)
        tag = themes["authors"].get(author, {}).get("hashtag")
        specific = [tag] if tag else []
        featured = themes["authors"].get(author, {}).get("subtitle", "")

    # Instagram caps hashtags at 5 per post
    tags = list(dict.fromkeys(themes["base_hashtags"] + specific))
    rotating = [h for h in themes["rotating_hashtags"] if h not in tags]
    rng.shuffle(rotating)
    tags = (tags + rotating)[:5]

    lines = [
        hook,
        "",
        featured,
        "",
        "💬 Which one hit hardest? Comment its number.",
        "🔖 Save this for the days you need it.",
        f"🌲 Follow {handle} for daily Stoic wisdom.",
        "",
        " ".join(tags),
    ]
    return "\n".join(lines)
