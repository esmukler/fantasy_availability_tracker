from __future__ import annotations

import time
import unittest
from pathlib import Path

from fantasy_avail.schemas import GetAvailableProbablePitchersResult, ProbablePitcherRow
from fantasy_avail.web.cache import DiskCache
from fantasy_avail.web.serialize import pitcher_row_to_web, result_to_web_payload


class DiskCacheTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "pitchers.json"
            cache = DiskCache(cache_path=cache_path, ttl_seconds=3600)
            payload = {"league_id": 1, "pitchers": []}

            fetched_at = cache.write(payload)
            cached = cache.read()

            self.assertIsNotNone(cached)
            assert cached is not None
            self.assertEqual(cached.data, payload)
            self.assertEqual(cached.fetched_at, fetched_at)

    def test_expires(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "pitchers.json"
            cache = DiskCache(cache_path=cache_path, ttl_seconds=1)
            cache.write({"pitchers": []})
            time.sleep(1.1)
            self.assertIsNone(cache.read())


class WebSerializeTests(unittest.TestCase):
    def test_result_to_web_payload_shape(self) -> None:
        row = ProbablePitcherRow(
            date="2026-07-08",
            game_pk=1,
            fp_slug="chris-sale",
            matchup={"away": "ATL", "home": "NYM"},
            side="home",
            mlb_name="Chris Sale",
            mlbam_id=123,
            is_available=True,
            pitcher_team="NYM",
            opponent_team="ATL",
            home_away="home",
            game_time_pt="Wed 4:10 PM PT",
            availability="free_agent",
            opposing_pitcher_name="Spencer Strider",
            mlb_season_stats={
                "wins": 8,
                "losses": 2,
                "era": "2.45",
                "whip": "0.98",
                "innings_pitched": "72.1",
                "strikeouts": 94,
            },
        )
        result = GetAvailableProbablePitchersResult(
            league_id=43384,
            start_date="2026-07-08",
            days=5,
            available=[row],
        )
        payload = result_to_web_payload(result, cached=False, cached_at=1_700_000_000.0)

        self.assertEqual(payload["league_id"], 43384)
        self.assertEqual(payload["date_range"], "Jul 8–12")
        self.assertEqual(payload["pitchers"][0]["name"], "Chris Sale")
        self.assertEqual(payload["pitchers"][0]["game_time_pt"], "4:10 PM PT")
        self.assertEqual(payload["pitchers"][0]["opposing_pitcher_name"], "Spencer Strider")
        self.assertEqual(payload["pitchers"][0]["stats"]["strikeouts"], 94)
        self.assertIn("cached_at", payload)

    def test_pitcher_row_to_web_minimal(self) -> None:
        row = ProbablePitcherRow(
            date="2026-07-08",
            game_pk=None,
            fp_slug="x",
            matchup={"away": "ATL", "home": "NYM"},
            side="away",
            mlb_name="Test Pitcher",
            mlbam_id=None,
            is_available=True,
        )
        web = pitcher_row_to_web(row)
        self.assertEqual(web["game_time_pt"], "TBD")
        self.assertIsNone(web["stats"])
        self.assertIsNone(web["opposing_pitcher_name"])


if __name__ == "__main__":
    unittest.main()
