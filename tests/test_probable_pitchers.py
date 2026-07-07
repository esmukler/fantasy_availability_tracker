from __future__ import annotations

import datetime as dt
import unittest

from fantasy_avail.models import ProbableStart
from fantasy_avail.services.probable_pitchers import (
    _index_probables_by_game,
    _opposing_pitcher_name,
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


if __name__ == "__main__":
    unittest.main()
