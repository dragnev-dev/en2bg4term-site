#!/usr/bin/env python3
"""TEMPORARY source patches — enrich the POS-annotation gap and drop real dupes.

Same-word rows (rows whose English slug collides, e.g. `map`, `charge`) must
carry a leading POS marker — `(to)` / `(a)` / `(an)` / `(adj)` / `(adv)` — so
their senses can eventually be grouped onto one page per part of speech. The
`validate_collision_pos` check in build_data.py enforces that.

`apply()` stamps a POS on the still-unmarked colliding rows and
removes the two exact-duplicate rows. It is deliberately self-contained.
"""

import sys

# Exact-duplicate rows to drop (keep the first occurrence, drop the rest).
# Keyed by (en_raw, bg_raw).
DROP_DUPLICATES = [
    ("condition", "условие"),
    ("contemporary", "съвременен"),
]

# POS for colliding rows the source doesn't yet mark. Keyed by (en_raw, bg_raw)
# -> one of "verb" / "noun" / "adj" / "adv" (mirrors build_data.POS_BY_MARKER).
POS_ENRICHMENT = {
    ("article", "статия"): "noun",
    ("article", "изделие, артикул (ч)"): "noun",
    ("article", "абзац"): "noun",
    ("assigned", "разпределен, назначен, прихванат"): "adj",
    ("assigned (tasks)", "разпределени/раздадени задачи"): "adj",
    ("boundary", "граничен"): "adj",
    ("(proposal) breakdown", "разбивка"): "noun",
    ("(electrical) breakdown", "пробив"): "noun",
    ("compilation", "събиране, струпване, окомплектоване (ч)"): "noun",
    ("compilation", "изграждане"): "noun",
    ("control", "управление, надзор"): "noun",
    ("current", "(прил). текущ, сегашен"): "adj",
    ("desktop", "настолен (прил.)"): "adj",
    ("document", "статия, описание, свидетелство, сведение"): "noun",
    ("header", "заглавна част, заглавно поле"): "noun",
    ("header", "заглавка, колонтитул(ч)"): "noun",
    ("import", "внос, внасяне, вмъкване, привнасяне"): "noun",
    ("informed", "обоснован, обмислен"): "adj",
    ("inherent", "присъщ, неотменим, вроден"): "adj",
    ("inherent", "присъщ, свойствен"): "adj",
    ("intercept", "отклонение (мат)"): "noun",
    ("intercept", "прихващане"): "noun",
    ("interleaving (data)", "преплитане, преподреждане (на данни)"): "noun",
    ("interleaving", "преплитане"): "noun",
    ("manual", "_прил._ ръчен"): "adj",
    ("manual", "_същ._ ръководство, упътване"): "noun",
    ("map", "карта(ч)"): "noun",
    ("map", "речник"): "noun",
    ("mapping", "картиране, картографиране"): "noun",
    ("mapping", "изображение, съпоставяне, отношение"): "noun",
    ("margin", "отстояние"): "noun",
    ("margin", "горница"): "noun",
    ("parent", "родителски, майчински, бащински"): "adj",
    ("plaintext", "обикновен текст(ч)"): "noun",
    ("plaintext", "явен текст(ч)"): "noun",
    # (а) provision / (а) residual use a Cyrillic "а" that isn't a valid marker;
    ("(а) provision", "продоволствие"): "noun",
    ("(а) residual", "несъответствие, остатък"): "noun",
    ("residual", "остатъчен"): "adj",
    ("resolution (gfx)", "разделителна способност (на екрана)_"): "noun",
    ("resolution (of issue)", "разрешаване казус(ч)"): "noun",
    ("(variable) scope", "видимост, област на видимост"): "noun",
    ("setup", "нагласям, настройвам"): "verb",
    ("setup", "постановка, положение"): "noun",
    # "to order" (both verbs) lacks the parenthesised marker;
    ("to order", "редя, подреждам"): "verb",
    ("to order", "поръчвам, давам нареждане"): "verb",
    ("volume", "сила на звука"): "noun",
    ("volume", "обем"): "noun",
}


def _warn(msg: str) -> None:
    print(f"patches.py: {msg}", file=sys.stderr)


def apply(terms: list) -> None:
    """Mutate `terms` in place: drop duplicate rows, then stamp missing POS."""
    _drop_duplicates(terms)
    _enrich_pos(terms)


def _key(t: dict) -> tuple:
    return (t["en_raw"], t["bg_raw"])


def _drop_duplicates(terms: list) -> None:
    targets = set(DROP_DUPLICATES)
    seen: set = set()
    kept = []
    for t in terms:
        k = _key(t)
        if k in targets:
            if k in seen:
                continue  # a later identical copy — drop it
            seen.add(k)
        kept.append(t)
    terms[:] = kept

    for k in DROP_DUPLICATES:
        if k not in seen:
            _warn(f"DROP_DUPLICATES entry {k} matched no row — remove it")
    # `seen` only tells us a first copy existed; a lone copy (nothing dropped)
    # means the source de-duplicated. Detect that via the post-drop count.
    remaining = [t for t in terms if _key(t) in targets]
    kept_keys = {_key(t) for t in remaining}
    for k in DROP_DUPLICATES:
        if k in seen and k not in kept_keys:
            _warn(f"DROP_DUPLICATES entry {k} left no row — unexpected")


def _enrich_pos(terms: list) -> None:
    used: set = set()
    obsolete: set = set()
    for t in terms:
        k = _key(t)
        pos = POS_ENRICHMENT.get(k)
        if pos is None:
            continue
        if t.get("pos"):
            obsolete.add(k)  # source now marks this row
        else:
            t["pos"] = pos
            used.add(k)

    for k in obsolete:
        _warn(f"POS_ENRICHMENT entry {k} — source now carries a marker, remove it")
    for k in set(POS_ENRICHMENT) - used - obsolete:
        _warn(f"POS_ENRICHMENT entry {k} matched no row — remove it")
