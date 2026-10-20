"""Import sourced quotes from Wikiquote into candidate files for curation.

Only the sourced "Quotes" part of each page is used; "Disputed", "Misattributed",
"Quotes about ..." and similar sections are skipped.

Usage:
    python tools/import_wikiquote.py "Marcus Aurelius" "Seneca the Younger" ...
Writes quotes/_candidates/<page>.txt  (text | author | source), one quote per line.
"""
import os
import re
import sys
import time

import requests

API = "https://en.wikiquote.org/w/api.php"
UA = {"User-Agent": "QuoteCarouselBot/0.1 (personal, non-commercial curation)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "quotes", "_candidates")

STOP_SECTIONS = re.compile(r"disputed|misattributed|attributed|quotes about|about |see also|external links|sources|references|quotes from|notes|dubious|unsourced|criticism", re.I)
NON_LATIN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿऀ-ॿ぀-ヿ一-鿿]")
REF_LIKE = re.compile(r"^(book|chapter|ch\.|letter|epistle|p\.|pp\.|vol|section|[ivxlc]+[,.\s]|\d|§|as quoted|quoted in|translated|translation|variant|original|tr\.|\()", re.I)


def wikitext(page):
    for attempt in range(5):
        r = requests.get(API, params={"action": "parse", "page": page, "prop": "wikitext", "format": "json",
                                      "formatversion": 2, "redirects": 1}, headers=UA, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(10 * (attempt + 1))
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("info"))
    return data["parse"]["title"], data["parse"]["wikitext"]


def clean(s):
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)        # [[link|text]] -> text
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)             # [url text] -> text
    s = re.sub(r"\[https?://\S+\]", "", s)
    s = s.replace("'''", "").replace("''", "")
    s = s.replace("&nbsp;", " ").replace("&mdash;", "—").replace("&ndash;", "–")
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" *:")


def parse(title, text):
    """Yield (quote, source) from sourced sections."""
    heading_stack = {}
    in_quotes = True
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(=+)\s*(.*?)\s*\1\s*$", line)
        if m:
            level, name = len(m.group(1)), clean(m.group(2))
            heading_stack = {k: v for k, v in heading_stack.items() if k < level}
            heading_stack[level] = name
            if level == 2:
                in_quotes = not STOP_SECTIONS.search(name)
            elif STOP_SECTIONS.search(name):
                in_quotes = False
            elif level > 2 and not STOP_SECTIONS.search(heading_stack.get(2, "")):
                in_quotes = True
            i += 1
            continue
        if in_quotes and re.match(r"^\*[^*:]", line):
            main = clean(line[1:])
            subs = []
            j = i + 1
            while j < len(lines) and re.match(r"^\*\*|^:", lines[j]):
                subs.append(lines[j])
                j += 1
            # Greek/Latin original followed by an English translation: prefer the bold sub-bullet
            if NON_LATIN.search(main) or not main:
                eng = [clean(s.lstrip("*: ")) for s in subs if "'''" in s] or \
                      [clean(s.lstrip("*: ")) for s in subs if not NON_LATIN.search(s)]
                main = eng[0] if eng else ""
            refs = [clean(s.lstrip("*: ")) for s in subs]
            ref = next((r for r in refs if r and len(r) < 90 and REF_LIKE.match(r)), "")
            parts = [re.sub(r"\s*\([^)]*\)", "", v) for k, v in sorted(heading_stack.items()) if k > 2]
            if ref:  # "Book II" heading is redundant next to a "II, 1" reference
                parts = [p for p in parts if not re.match(r"^(book|letter|chapter)", p, re.I)]
            tr = re.search(r"\s*\((\w+(?: \w+)?) translation\)\s*$", main)
            if tr:
                main = main[:tr.start()]
                ref = f"{ref} (tr. {tr.group(1)})".strip()
            source = ", ".join(x for x in [" / ".join(p for p in parts if p), ref] if x)
            if main:
                yield main, source
            i = j
            continue
        i += 1


def good(q):
    if not 25 <= len(q) <= 260:
        return False
    if NON_LATIN.search(q) or "..." in q or "…" in q or "[" in q or "{" in q or "|" in q:
        return False
    if q.endswith(":") or q.lower().startswith(("see also", "as quoted", "quoted in")):
        return False
    return True


def main(pages):
    os.makedirs(OUT, exist_ok=True)
    for page in pages:
        try:
            title, text = wikitext(page)
        except Exception as e:  # noqa: BLE001
            print(f"!! {page}: {e}")
            continue
        author = re.sub(r"\s*\(.*\)$", "", title)
        seen, rows = set(), []
        for q, src in parse(title, text):
            q = q.strip().strip('"“”')
            if good(q) and q.lower() not in seen:
                seen.add(q.lower())
                rows.append(f"{q} | {author} | {src}")
        path = os.path.join(OUT, re.sub(r"[^A-Za-z0-9]+", "_", title) + ".txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# text | author | source   (UNREVIEWED candidates from Wikiquote)\n")
            f.write("\n".join(rows) + "\n")
        print(f"{title}: {len(rows)} candidates -> {os.path.relpath(path, ROOT)}", flush=True)
        time.sleep(4)


if __name__ == "__main__":
    main(sys.argv[1:])
