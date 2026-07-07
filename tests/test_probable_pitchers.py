from __future__ import annotations

import datetime as dt
import unittest

from fantasy_avail.models import ProbableStart
from fantasy_avail.schemas import ProbablePitcherRow
from fantasy_avail.services.probable_pitchers import (
    _index_probables_by_game,
    _opposing_pitcher_name,
    _probable_row_sort_key,
)


def _probable_start(
    *,
    date: str,
    pitcher_name: str,
    side: str,
    away_abbr: str = "ATL",
    home_abbr: str = "NYM",
) -> ProbableStart:
    return ProbableStart(
        date=dt.date.fromisoformat(date),
        game_pk=None,
        pitcher_name=pitcher_name,
        pitcher_mlbam_id=None,
        pitcher_side=side,
        away_team=away_abbr,
        home_team=home_abbr,
        away_abbr=away_abbr,
        home_abbr=home_abbr,
        fp_slug=pitcher_name.lower().replace(" ", "-"),
    )


class OpposingPitcherJoinTests(unittest.TestCase):
    def test_both_sides_present_returns_opposing_name(self) -> None:
        away = _probable_start(
            date="2026-07-08",
            pitcher_name="Spencer Strider",
            side="away",
        )
        home = _probable_start(
            date="2026-07-08",
            pitcher_name="Chris Sale",
            side="home",
        )
        by_game = _index_probables_by_game([away, home])

        self.assertEqual(_opposing_pitcher_name(away, by_game), "Chris Sale")
        self.assertEqual(_opposing_pitcher_name(home, by_game), "Spencer Strider")

    def test_only_one_side_present_returns_none(self) -> None:
        away = _probable_start(
            date="2026-07-08",
            pitcher_name="Spencer Strider",
            side="away",
        )
        by_game = _index_probables_by_game([away])

        self.assertIsNone(_opposing_pitcher_name(away, by_game))


def _pitcher_row(
    *,
    date: str,
    name: str,
    era: str | None = None,
) -> ProbablePitcherRow:
    stats = None if era is None else {"era": era}
    return ProbablePitcherRow(
        date=date,
        game_pk=None,
        fp_slug=name.lower().replace(" ", "-"),
        matchup={"away": "ATL", "home": "NYM"},
        side="home",
        mlb_name=name,
        mlbam_id=1,
        is_available=True,
        mlb_season_stats=stats,
    )


class ProbableRowSortTests(unittest.TestCase):
    def test_sorts_by_date_then_era_ascending(self) -> None:
        rows = [
            _pitcher_row(date="2026-07-09", name="High ERA", era="5.00"),
            _pitcher_row(date="2026-07-08", name="Ace", era="2.10"),
            _pitcher_row(date="2026-07-08", name="Mid", era="3.50"),
            _pitcher_row(date="2026-07-08", name="No Stats"),
        ]
        rows.sort(key=_probable_row_sort_key)
        self.assertEqual(
            [r.mlb_name for r in rows],
            ["Ace", "Mid", "No Stats", "High ERA"],
        )

    def test_missing_stats_sort_last_within_day(self) -> None:
        rows = [
            _pitcher_row(date="2026-07-08", name="No Stats"),
            _pitcher_row(date="2026-07-08", name="Low ERA", era="1.80"),
        ]
        rows.sort(key=_probable_row_sort_key)
        self.assertEqual([r.mlb_name for r in rows], ["Low ERA", "No Stats"])


if __name__ == "__main__":
    unittest.main()
