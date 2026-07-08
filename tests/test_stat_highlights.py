from __future__ import annotations

import unittest

from fantasy_avail.stat_highlights import (
    era_highlight,
    format_k_per_9,
    k_per_9,
    k_per_9_highlight,
    parse_innings_pitched,
    stat_highlights_for,
    whip_highlight,
)


class ParseInningsPitchedTests(unittest.TestCase):
    def test_baseball_thirds(self) -> None:
        self.assertAlmostEqual(parse_innings_pitched("72.1"), 72 + 1 / 3)
        self.assertAlmostEqual(parse_innings_pitched("72.2"), 72 + 2 / 3)

    def test_missing(self) -> None:
        self.assertIsNone(parse_innings_pitched("—"))
        self.assertIsNone(parse_innings_pitched(None))


class EraHighlightTests(unittest.TestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(era_highlight("3.99"), "good")
        self.assertIsNone(era_highlight("4.00"))
        self.assertIsNone(era_highlight("5.00"))
        self.assertEqual(era_highlight("5.01"), "warn")
        self.assertEqual(era_highlight("6.00"), "warn")
        self.assertEqual(era_highlight("6.01"), "bad")


class WhipHighlightTests(unittest.TestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(whip_highlight("1.19"), "good")
        self.assertIsNone(whip_highlight("1.20"))
        self.assertIsNone(whip_highlight("1.50"))
        self.assertEqual(whip_highlight("1.51"), "warn")
        self.assertEqual(whip_highlight("1.70"), "warn")
        self.assertEqual(whip_highlight("1.71"), "bad")


class KPer9Tests(unittest.TestCase):
    def test_computation(self) -> None:
        self.assertAlmostEqual(k_per_9(14, "18.0"), 7.0)
        self.assertAlmostEqual(k_per_9(18, "18.0"), 9.0)

    def test_format(self) -> None:
        self.assertEqual(format_k_per_9(7.0), "7")
        self.assertEqual(format_k_per_9(9.0), "9")
        self.assertEqual(format_k_per_9(9.5), "9.5")
        self.assertEqual(format_k_per_9(None), "—")

    def test_highlight_threshold(self) -> None:
        self.assertEqual(k_per_9_highlight(14, "18.0"), None)
        self.assertEqual(k_per_9_highlight(18, "18.0"), "good")
        self.assertEqual(k_per_9_highlight(95, "72.1"), "good")
        self.assertIsNone(k_per_9_highlight(72, "72.1"))


class StatHighlightsForTests(unittest.TestCase):
    def test_payload_shape(self) -> None:
        highlights = stat_highlights_for(
            {
                "era": "2.45",
                "whip": "0.98",
                "innings_pitched": "72.1",
                "strikeouts": 94,
            }
        )
        self.assertEqual(highlights, {"era": "good", "whip": "good", "k_per_9": "good"})


if __name__ == "__main__":
    unittest.main()
