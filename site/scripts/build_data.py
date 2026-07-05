#!/usr/bin/env python3
"""Parse README.md + examples.md into site/data/terms.json for Hugo.
Source files are read from $DICT_SRC / $EXAMPLES_SRC (local paths or URLs).
Stdlib only.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
REPO_ROOT = SITE_DIR.parent

DICT_SRC = os.environ.get("DICT_SRC", str(REPO_ROOT / "README.md"))
EXAMPLES_SRC = os.environ.get("EXAMPLES_SRC", str(REPO_ROOT / "examples.md"))
OUT = SITE_DIR / "data" / "terms.json"

LINK_RE = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")  # [label](url) -> label; url may nest one level of parens (e.g. Wikipedia)
PREFIX_RE = re.compile(r"^\((?:to|an|a)\)\s+", re.I)    # leading (to)/(an)/(a)
# Leading POS marker -> part of speech
POS_MARKER_RE = re.compile(r"^\(\s*(to|an|a|adj|adv)\b[^)]*\)", re.I)
POS_BY_MARKER = {"to": "verb", "a": "noun", "an": "noun", "adj": "adj", "adv": "adv"}
PAREN_RE = re.compile(r"\([^)]*\)")                     # parenthetical clarifiers
SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")            # dictionary letter header
EX_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")          # examples letter header
EX_TERM_RE = re.compile(r"^\*\s+\*\*(.+?)\*\*")         # *   **term** (...)
EX_LINE_RE = re.compile(r"^\s*\*\s+(EN|BG):\s*(.+?)\s*$")

# Header / separator rows to skip (cf. excapeWordArray in js/site.js).
SKIP_CELL = {"en", "bg", "забележка", "коментар", ""}

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")  # what slugify is meant to emit


class ValidationError(Exception):
    """Raised when parsed output violates a build-blocking invariant."""


def read_source(src: str) -> str:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=30) as resp:
            return resp.read().decode("utf-8")
    return Path(src).read_text(encoding="utf-8")


def strip_links(text: str) -> str:
    return LINK_RE.sub(r"\1", text)


def slugify(en_text: str) -> str:
    """English term -> URL slug. Strips links, (to)/(an)/(a), parentheticals."""
    s = strip_links(en_text)
    s = PREFIX_RE.sub("", s)
    s = PAREN_RE.sub("", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "term"


def pos_from_marker(en_md: str) -> str:
    """Leading POS marker ((to)/(a)/(an)/(adj)/(adv)) -> pos, else ''."""
    m = POS_MARKER_RE.match(strip_links(en_md).strip())
    return POS_BY_MARKER[m.group(1).lower()] if m else ""


def join_key(text: str) -> str:
    """Normalized key for matching dictionary terms to example blocks."""
    return re.sub(r"\s+", " ", strip_links(text).strip()).lower()


def parse_examples(text: str) -> dict:
    """Return {join_key: [{"en": str, "bg": [str, ...]}, ...]}."""
    out: dict[str, list] = {}
    current = None  # current example pair being filled
    key = None
    for line in text.splitlines():
        m = EX_TERM_RE.match(line)
        if m:
            key = join_key(m.group(1))
            out.setdefault(key, [])
            current = None
            continue
        if key is None:
            continue
        m = EX_LINE_RE.match(line)
        if m:
            kind, val = m.group(1), m.group(2)
            if kind == "EN":
                # Each EN line starts a new example pair, so terms with
                # multiple EN/BG pairs render as separate examples.
                current = {"en": val, "bg": []}
                out[key].append(current)
            else:
                if current is None:
                    current = {"en": "", "bg": []}
                    out[key].append(current)
                current["bg"].append(val)
    # Drop empty shells.
    for k in list(out):
        out[k] = [e for e in out[k] if e["en"] or e["bg"]]
        if not out[k]:
            del out[k]
    return out


def parse_dictionary(text: str, examples: dict):
    terms = []
    letters = []
    seen_slugs: dict[str, int] = {}
    current_letter = None

    for raw in text.splitlines():
        sec = SECTION_RE.match(raw)
        if sec:
            current_letter = sec.group(1).strip()
            letters.append(current_letter)
            continue
        if current_letter is None or "|" not in raw:
            continue

        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        en_md, bg_md = cells[0], cells[1]
        comment_md = cells[2] if len(cells) > 2 else ""

        # Skip table header / separator rows.
        if en_md.lower() in SKIP_CELL or set(en_md) <= set("-: "):
            continue
        if not en_md or not bg_md:
            continue

        en_raw = strip_links(en_md).strip()
        bg_raw = strip_links(bg_md).strip()

        base = slugify(en_md)
        n = seen_slugs.get(base, 0) + 1
        seen_slugs[base] = n
        slug = base if n == 1 else f"{base}-{n}"

        terms.append({
            "slug": slug,
            "letter": current_letter,
            "en_raw": en_raw,
            "en_md": en_md,
            "bg_raw": bg_raw,
            "bg_md": bg_md,
            "comment_md": comment_md,
            "pos": pos_from_marker(en_md),
            "examples": examples.get(join_key(en_md), []),
        })

    return terms, letters


def collision_groups(terms: list) -> dict:
    """{base_slug: [term, ...]} for base slugs shared by more than one row."""
    groups: dict[str, list] = {}
    for t in terms:
        groups.setdefault(slugify(t["en_md"]), []).append(t)
    return {k: v for k, v in groups.items() if len(v) > 1}


def validate(terms: list, letters: list) -> None:
    """Fail the build on data that would deploy broken pages.

    Avoids cases of incorrectly parsing the source data, preventing bad deployments
    """
    errors = []
    if not terms:
        errors.append("no terms parsed — check DICT_SRC and section/table format")
    if not letters:
        errors.append("no letter sections found")

    seen: dict[str, int] = {}
    for t in terms:
        seen[t["slug"]] = seen.get(t["slug"], 0) + 1
    dupes = sorted(s for s, n in seen.items() if n > 1)
    if dupes:
        errors.append(f"duplicate slugs (would collide URLs): {dupes}")

    for t in terms:
        if not SLUG_RE.match(t["slug"]):
            errors.append(f"malformed slug {t['slug']!r} for en={t['en_raw']!r}")
        if not t["en_raw"] or not t["bg_raw"]:
            errors.append(f"empty en/bg for slug {t['slug']!r}")

    if errors:
        raise ValidationError(
            "terms.json failed validation:\n  - " + "\n  - ".join(errors))


def validate_collision_pos(terms: list) -> None:
    """Fail the build if any same-word (slug-colliding) row lacks a POS.

    Grouping senses onto one page per part of speech needs every colliding row
    to declare its POS via a leading (to)/(a)/(an)/(adj)/(adv) marker
    """
    missing = [f"{base}: {t['en_raw']!r} / {t['bg_raw']!r}"
               for base, rows in sorted(collision_groups(terms).items())
               for t in rows if not t.get("pos")]
    if missing:
        raise ValidationError(
            "same-word rows missing a POS marker "
            "((to)/(a)/(an)/(adj)/(adv)):\n  - " + "\n  - ".join(missing))


def main():
    dict_text = read_source(DICT_SRC)
    ex_text = read_source(EXAMPLES_SRC)
    examples = parse_examples(ex_text)
    terms, letters = parse_dictionary(dict_text, examples)

    # TEMPORARY: fill the POS-annotation gap and drop real duplicates until the
    # source carries a marker on every same-word row. Strip by deleting
    # scripts/patches.py — validate_collision_pos then enforces the source.
    try:
        import patches
    except ImportError:
        patches = None
    if patches is not None:
        patches.apply(terms)

    validate(terms, letters)
    validate_collision_pos(terms)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"letters": letters, "terms": terms}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    matched = sum(1 for t in terms if t["examples"])
    print(f"terms: {len(terms)}  letters: {len(letters)}  with-examples: {matched}")
    print(f"example keys: {len(examples)}  unmatched: "
          f"{len(examples) - len({join_key(t['en_md']) for t in terms if t['examples']})}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
