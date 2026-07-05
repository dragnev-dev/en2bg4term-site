#!/usr/bin/env python3
"""Unit tests for the TEMPORARY patches.py layer — delete both together.

Run: python3 scripts/test_patches.py
"""

import io
import unittest
from contextlib import redirect_stderr

import patches


def _term(en, bg, pos=""):
    return {"en_raw": en, "bg_raw": bg, "pos": pos}


class TestDropDuplicates(unittest.TestCase):
    def test_keeps_first_drops_later_identical(self):
        terms = [_term("condition", "условие"),
                 _term("condition", "условие"),
                 _term("other", "друго")]
        patches.apply(terms)
        conds = [t for t in terms if t["en_raw"] == "condition"]
        self.assertEqual(len(conds), 1)
        self.assertIn("other", [t["en_raw"] for t in terms])  # non-dupe kept

    def test_warns_when_duplicate_absent(self):
        # Source already de-duplicated: entry present once, nothing to drop.
        terms = [_term("condition", "условие")]
        buf = io.StringIO()
        with redirect_stderr(buf):
            patches.apply(terms)
        self.assertEqual(len(terms), 1)


class TestEnrichPos(unittest.TestCase):
    def test_stamps_missing_pos(self):
        terms = [_term("boundary", "граничен")]
        patches.apply(terms)
        self.assertEqual(terms[0]["pos"], "adj")

    def test_does_not_override_existing_pos(self):
        terms = [_term("boundary", "граничен", pos="noun")]
        buf = io.StringIO()
        with redirect_stderr(buf):
            patches.apply(terms)
        self.assertEqual(terms[0]["pos"], "noun")           # left untouched
        self.assertIn("source now carries a marker", buf.getvalue())

    def test_warns_on_unmatched_entry(self):
        terms = [_term("boundary", "граничен")]  # matches; leaves others unused
        buf = io.StringIO()
        with redirect_stderr(buf):
            patches.apply(terms)
        # Every other POS_ENRICHMENT key matched nothing -> a warning each.
        self.assertIn("matched no row", buf.getvalue())


class TestPatchDataIntegrity(unittest.TestCase):
    def test_enrichment_values_are_known_pos(self):
        import build_data as b
        self.assertLessEqual(set(patches.POS_ENRICHMENT.values()),
                             set(b.POS_BY_MARKER.values()))

    def test_no_row_is_both_dropped_and_enriched(self):
        self.assertFalse(set(patches.DROP_DUPLICATES) & set(patches.POS_ENRICHMENT))


if __name__ == "__main__":
    unittest.main()
