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
