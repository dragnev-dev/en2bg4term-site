#!/usr/bin/env python3
"""Unit tests for build_data.py — stdlib unittest, no dependencies.

Run: python3 scripts/test_build_data.py

Covers the parser's pure functions, catching code regressions
"""

import unittest

import build_data as b


class TestStripLinks(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(b.strip_links("just text"), "just text")

    def test_simple_link(self):
        self.assertEqual(b.strip_links("[cache](https://x.io)"), "cache")

    def test_link_with_nested_parens_in_url(self):
        # Wikipedia-style URL with parens — LINK_RE allows one nesting level.
        src = "[OSI](https://en.wikipedia.org/wiki/OSI_model_(layer))"
        self.assertEqual(b.strip_links(src), "OSI")

    def test_empty_label(self):
        self.assertEqual(b.strip_links("[](https://x.io)"), "")

    def test_text_around_link(self):
        self.assertEqual(b.strip_links("see [docs](u) now"), "see docs now")


class TestSlugify(unittest.TestCase):
    def test_to_prefix_stripped(self):
        self.assertEqual(b.slugify("(to) access"), "access")

    def test_an_prefix_stripped(self):
        self.assertEqual(b.slugify("(an) access"), "access")

    def test_a_prefix_stripped(self):
        self.assertEqual(b.slugify("(a) cache"), "cache")

    def test_parenthetical_clarifier_stripped(self):
        self.assertEqual(b.slugify("cache (memory)"), "cache")

    def test_link_stripped_before_slugging(self):
        self.assertEqual(b.slugify("[load balancer](u)"), "load-balancer")

    def test_lowercased_and_punctuation_collapsed(self):
        self.assertEqual(b.slugify("Foo / Bar!!"), "foo-bar")

    def test_empty_falls_back_to_term(self):
        self.assertEqual(b.slugify("(to)"), "term")

    def test_non_ascii_collapses_to_dashes_then_trims(self):
        # No [a-z0-9] survives -> fallback.
        self.assertEqual(b.slugify("（）"), "term")


class TestPosFromMarker(unittest.TestCase):
    def test_to_is_verb(self):
        self.assertEqual(b.pos_from_marker("(to) map"), "verb")

    def test_a_and_an_are_noun(self):
        self.assertEqual(b.pos_from_marker("(a) map"), "noun")
        self.assertEqual(b.pos_from_marker("(an) input"), "noun")

    def test_adj_and_adv(self):
        self.assertEqual(b.pos_from_marker("(adj) manual"), "adj")
        self.assertEqual(b.pos_from_marker("(adv) inline"), "adv")

    def test_case_insensitive(self):
        self.assertEqual(b.pos_from_marker("(A) spooler"), "noun")

    def test_to_be_still_verb(self):
        self.assertEqual(b.pos_from_marker("(to be) informed"), "verb")

    def test_marker_after_link(self):
        # slugify already strips (to)/(a); pos must see through a leading link too.
        self.assertEqual(b.pos_from_marker("(a) [stride](https://x.io)"), "noun")

    def test_no_marker(self):
        self.assertEqual(b.pos_from_marker("boundary"), "")

    def test_non_pos_parenthetical_is_not_a_marker(self):
        self.assertEqual(b.pos_from_marker("(variable) scope"), "")
        self.assertEqual(b.pos_from_marker("resolution (gfx)"), "")


class TestJoinKey(unittest.TestCase):
    def test_lowercase_and_collapse_whitespace(self):
        self.assertEqual(b.join_key("  Load   Balancer  "), "load balancer")

    def test_strips_links(self):
        self.assertEqual(b.join_key("[Cache](u)"), "cache")


class TestParseExamples(unittest.TestCase):
    def test_basic_pair(self):
        text = "*   **cache**\n  *   EN: clear the cache\n  *   BG: изчисти кеша"
        out = b.parse_examples(text)
        self.assertEqual(out, {"cache": [{"en": "clear the cache",
                                          "bg": ["изчисти кеша"]}]})

    def test_each_en_starts_new_pair(self):
        text = ("*   **cache**\n"
                "  *   EN: one\n  *   BG: едно\n"
                "  *   EN: two\n  *   BG: две")
        out = b.parse_examples(text)
        self.assertEqual(out["cache"], [
            {"en": "one", "bg": ["едно"]},
            {"en": "two", "bg": ["две"]},
        ])

    def test_multiple_bg_per_en(self):
        text = "*   **cache**\n  *   EN: one\n  *   BG: едно\n  *   BG: първо"
        out = b.parse_examples(text)
        self.assertEqual(out["cache"], [{"en": "one", "bg": ["едно", "първо"]}])

    def test_orphan_bg_without_en(self):
        text = "*   **cache**\n  *   BG: само превод"
        out = b.parse_examples(text)
        self.assertEqual(out["cache"], [{"en": "", "bg": ["само превод"]}])

    def test_empty_shell_dropped(self):
        # A term header with no EN/BG lines produces no entry.
        text = "*   **cache**\n*   **other**\n  *   EN: x"
        out = b.parse_examples(text)
        self.assertNotIn("cache", out)
        self.assertIn("other", out)

    def test_lines_before_first_term_ignored(self):
        text = "  *   EN: stray\n*   **cache**\n  *   EN: real"
        out = b.parse_examples(text)
        self.assertEqual(out["cache"], [{"en": "real", "bg": []}])


DICT = """\
### A

| EN | BG | Коментар |
| -- | -- | -- |
| (to) access | достъп | |
| (an) access | достъп (съществително) | |
| [cache](https://x.io) | кеш | памет |

### B

| EN | BG |
| -- | -- |
| | empty-en-skipped |
| build | |
"""


class TestParseDictionary(unittest.TestCase):
    def setUp(self):
        self.terms, self.letters = b.parse_dictionary(DICT, {})

    def test_letters_collected(self):
        self.assertEqual(self.letters, ["A", "B"])

    def test_header_and_separator_rows_skipped(self):
        slugs = [t["slug"] for t in self.terms]
        self.assertNotIn("en", slugs)

    def test_rows_with_empty_cell_skipped(self):
        ens = [t["en_raw"] for t in self.terms]
        self.assertNotIn("build", ens)          # empty BG -> skipped
        self.assertNotIn("empty-en-skipped", [t["bg_raw"] for t in self.terms])

    def test_slug_collision_disambiguated(self):
        slugs = [t["slug"] for t in self.terms]
        self.assertEqual(slugs, ["access", "access-2", "cache"])

    def test_links_stripped_in_raw_fields(self):
        cache = next(t for t in self.terms if t["slug"] == "cache")
        self.assertEqual(cache["en_raw"], "cache")
        self.assertEqual(cache["en_md"], "[cache](https://x.io)")

    def test_optional_comment_column(self):
        cache = next(t for t in self.terms if t["slug"] == "cache")
        self.assertEqual(cache["comment_md"], "памет")

    def test_examples_attached_by_join_key(self):
        examples = {"cache": [{"en": "clear it", "bg": ["изчисти"]}]}
        terms, _ = b.parse_dictionary(DICT, examples)
        cache = next(t for t in terms if t["slug"] == "cache")
        self.assertEqual(cache["examples"], examples["cache"])

    def test_pos_derived_from_marker(self):
        access = next(t for t in self.terms if t["slug"] == "access")
        self.assertEqual(access["en_md"], "(to) access")
        self.assertEqual(access["pos"], "verb")
        cache = next(t for t in self.terms if t["slug"] == "cache")
        self.assertEqual(cache["pos"], "")  # unmarked


# `map` collides (marked both ways); `boundary` is a lone unmarked row.
POS_DICT_OK = """\
### M

EN | BG |
-- | -- |
(a) map | карта |
(to) map | съпоставям |
boundary | граница |
"""

# Same, plus a third bare `map` sense with no marker -> the collision gap.
POS_DICT_GAP = POS_DICT_OK + "map | речник |\n"


class TestCollisionPos(unittest.TestCase):
    def test_collision_groups_only_returns_shared_slugs(self):
        terms, _ = b.parse_dictionary(POS_DICT_OK, {})
        groups = b.collision_groups(terms)
        self.assertEqual(set(groups), {"map"})       # boundary is unique
        self.assertEqual(len(groups["map"]), 2)

    def test_lone_unmarked_row_is_allowed(self):
        # `boundary` collides with nothing, so its missing pos must not fail.
        terms, _ = b.parse_dictionary(POS_DICT_OK, {})
        b.validate_collision_pos(terms)

    def test_collision_row_without_pos_fails(self):
        terms, _ = b.parse_dictionary(POS_DICT_GAP, {})
        with self.assertRaises(b.ValidationError):
            b.validate_collision_pos(terms)

    def test_passes_once_every_collision_row_has_pos(self):
        terms, _ = b.parse_dictionary(POS_DICT_GAP, {})
        next(t for t in terms if t["en_raw"] == "map" and not t["pos"])["pos"] = "noun"
        b.validate_collision_pos(terms)


class TestHeadword(unittest.TestCase):
    def test_strips_leading_pos_marker(self):
        self.assertEqual(b.headword("(a) map"), "map")
        self.assertEqual(b.headword("(to) map"), "map")

    def test_strips_leading_non_pos_parenthetical(self):
        self.assertEqual(b.headword("(variable) scope"), "scope")

    def test_strips_trailing_parenthetical(self):
        self.assertEqual(b.headword("resolution (gfx)"), "resolution")

    def test_strips_links(self):
        self.assertEqual(b.headword("(a) [map](https://x.io)"), "map")

    def test_plain_word_unchanged(self):
        self.assertEqual(b.headword("mapping"), "mapping")

    def test_collisions_share_one_headword(self):
        # Every row of a slug-collision must yield the same headword.
        rows, _ = b.parse_dictionary(POS_DICT_GAP, {})
        maps = [b.headword(r["en_md"]) for r in rows if r["slug"].startswith("map")]
        self.assertEqual(set(maps), {"map"})


class TestMergeTerms(unittest.TestCase):
    def setUp(self):
        rows, _ = b.parse_dictionary(POS_DICT_GAP, {})
        # Stamp the "bare" sense so the collision group is fully POS-marked.
        next(r for r in rows if r["en_raw"] == "map" and not r["pos"])["pos"] = "noun"
        self.pages = b.merge_terms(rows)

    def _page(self, slug):
        return next(p for p in self.pages if p["slug"] == slug)

    def test_one_page_per_base_slug(self):
        slugs = [p["slug"] for p in self.pages]
        self.assertEqual(slugs.count("map"), 1)          # 3 rows -> 1 page
        self.assertNotIn("map-2", slugs)                 # no suffixed slugs

    def test_lone_row_is_single_sense(self):
        boundary = self._page("boundary")
        self.assertFalse(boundary["multi"])
        self.assertEqual(boundary["en_raw"], "boundary")
        self.assertEqual(len(boundary["groups"]), 1)
        self.assertEqual(len(boundary["groups"][0]["senses"]), 1)

    def test_collision_is_multi_and_grouped_by_pos(self):
        m = self._page("map")
        self.assertTrue(m["multi"])
        self.assertEqual(m["en_raw"], "map")             # headword, no marker
        by_pos = {g["pos"]: g for g in m["groups"]}
        self.assertEqual(set(by_pos), {"noun", "verb"})
        self.assertEqual(len(by_pos["noun"]["senses"]), 2)   # (a) map + bare map
        self.assertEqual(len(by_pos["verb"]["senses"]), 1)   # (to) map

    def test_groups_ordered_noun_before_verb(self):
        m = self._page("map")
        self.assertEqual([g["pos"] for g in m["groups"]], ["noun", "verb"])

    def test_group_carries_bulgarian_label(self):
        m = self._page("map")
        labels = {g["pos"]: g["pos_label"] for g in m["groups"]}
        self.assertEqual(labels["noun"], b.POS_LABELS["noun"])

    def test_sense_keeps_render_fields(self):
        sense = self._page("map")["groups"][0]["senses"][0]
        self.assertEqual(set(sense),
                         {"en_md", "bg_md", "bg_raw", "comment_md", "examples"})

    def test_bg_raw_summary_joins_senses(self):
        # карта + речка(съпоставям) + речник, deduped and ordered.
        self.assertEqual(self._page("map")["bg_raw"],
                         "карта; съпоставям; речник")

    def test_merged_pages_pass_validate(self):
        # Merged output must satisfy the deploy-blocking invariants.
        _, letters = b.parse_dictionary(POS_DICT_GAP, {})
        b.validate(self.pages, letters)


class TestValidate(unittest.TestCase):
    def _term(self, **kw):
        base = {"slug": "x", "en_raw": "x", "bg_raw": "у"}
        base.update(kw)
        return base

    def test_clean_data_passes(self):
        b.validate([self._term(slug="a"), self._term(slug="b")], ["A"])

    def test_duplicate_slug_rejected(self):
        with self.assertRaises(b.ValidationError):
            b.validate([self._term(slug="a"), self._term(slug="a")], ["A"])

    def test_empty_term_list_rejected(self):
        with self.assertRaises(b.ValidationError):
            b.validate([], [])

    def test_malformed_slug_rejected(self):
        with self.assertRaises(b.ValidationError):
            b.validate([self._term(slug="Bad Slug")], ["A"])

    def test_empty_en_or_bg_rejected(self):
        with self.assertRaises(b.ValidationError):
            b.validate([self._term(en_raw="")], ["A"])


if __name__ == "__main__":
    unittest.main()
