from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fantasy_avail.opponent_ops_highlights import (
    ensure_opponent_highlights,
    opponent_highlight_for_abbr,
    opponent_highlight_tiers_from_csv,
)


def _write_sample_csv(path: Path) -> None:
  with path.open("w", newline="", encoding="utf-8") as f:
      w = csv.writer(f)
      w.writerow(["rank", "team", "abbr", "ops"])
      teams = [
          ("Team A", "AAA"),
          ("Team B", "BBB"),
          ("Team C", "CCC"),
          ("Team D", "DDD"),
          ("Team E", "EEE"),
          ("Team F", "FFF"),
          ("Team G", "GGG"),
          ("Team H", "HHH"),
          ("Team I", "III"),
          ("Team J", "JJJ"),
          ("Team K", "KKK"),
          ("Team L", "LLL"),
          ("Team M", "MMM"),
          ("Team N", "NNN"),
          ("Team O", "OOO"),
          ("Team P", "PPP"),
          ("Team Q", "QQQ"),
          ("Team R", "RRR"),
          ("Team S", "SSS"),
          ("Team T", "TTT"),
          ("Team U", "UUU"),
          ("Team V", "VVV"),
          ("Team W", "WWW"),
          ("Team X", "XXX"),
          ("Team Y", "YYY"),
          ("Team Z1", "ZZ1"),
          ("Team Z2", "ZZ2"),
          ("Team Z3", "ZZ3"),
          ("Team Z4", "ZZ4"),
          ("Team Z5", "ZZ5"),
      ]
      for i, (name, abbr) in enumerate(teams, start=1):
          w.writerow([i, name, abbr, f".{700 - i:03d}"])


class OpponentHighlightTiersTests(unittest.TestCase):
    def test_tier_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "team_ops.csv"
            _write_sample_csv(path)
            tiers = opponent_highlight_tiers_from_csv(path)

        self.assertEqual(tiers["AAA"], "bad")
        self.assertEqual(tiers["EEE"], "bad")
        self.assertEqual(tiers["FFF"], "warn")
        self.assertEqual(tiers["JJJ"], "warn")
        self.assertEqual(tiers["ZZ1"], "good")
        self.assertEqual(tiers["ZZ5"], "good")
        self.assertNotIn("KKK", tiers)
        self.assertNotIn("WWW", tiers)

    def test_ensure_opponent_highlights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "team_ops_2026.csv"
            _write_sample_csv(csv_path)
            payload = {
                "start_date": "2026-07-08",
                "pitchers": [
                    {"opponent_team": "AAA"},
                    {"opponent_team": "FFF"},
                    {"opponent_team": "ZZ5"},
                    {"opponent_team": "KKK"},
                ],
            }
            from fantasy_avail.opponent_ops_highlights import default_team_ops_csv_path

            with patch(
                "fantasy_avail.opponent_ops_highlights.default_team_ops_csv_path",
                return_value=csv_path,
            ):
                ensure_opponent_highlights(payload)

        pitchers = payload["pitchers"]
        self.assertEqual(pitchers[0]["opponent_highlight"], "bad")
        self.assertEqual(pitchers[1]["opponent_highlight"], "warn")
        self.assertEqual(pitchers[2]["opponent_highlight"], "good")
        self.assertIsNone(pitchers[3]["opponent_highlight"])

    def test_lookup_is_case_insensitive(self) -> None:
        self.assertEqual(opponent_highlight_for_abbr("lad", {"LAD": "bad"}), "bad")


if __name__ == "__main__":
    unittest.main()
