"""Loading quotes, themes, config and posting history."""
import glob
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUOTES_DIR = os.path.join(ROOT, "quotes")
STATE_PATH = os.path.join(ROOT, "state", "history.json")


def load_json(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def quote_id(text):
    return hashlib.sha1(_norm(text).encode()).hexdigest()[:10]


def load_quotes():
    """All curated quotes from quotes/themes/*.txt and quotes/authors/*.txt (deduplicated).

    Line format: text | author | source | tags   (tags optional, comma separated).
    Files in quotes/themes/ also get their file name as a tag.
    """
    quotes, seen = [], {}
    files = sorted(glob.glob(os.path.join(QUOTES_DIR, "themes", "*.txt"))) + \
        sorted(glob.glob(os.path.join(QUOTES_DIR, "authors", "*.txt")))
    for path in files:
        file_tag = os.path.splitext(os.path.basename(path))[0] if os.sep + "themes" + os.sep in path else None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2 or not parts[0] or not parts[1]:
                    continue
                tags = {t.strip() for t in (parts[3] if len(parts) > 3 else "").split(",") if t.strip()}
                if file_tag:
                    tags.add(file_tag)
                qid = quote_id(parts[0])
                if qid in seen:  # same quote in two files: merge tags
                    seen[qid]["tags"] |= tags
                    continue
                q = {"id": qid, "text": parts[0], "author": parts[1],
                     "source": parts[2] if len(parts) > 2 else "", "tags": tags}
                seen[qid] = q
                quotes.append(q)
    return quotes


def load_history():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"quotes": {}, "posts": [], "photos": []}


def save_history(history):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=1, ensure_ascii=False)
