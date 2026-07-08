from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

from fantasy_avail.models import ProbableStart
from fantasy_avail.schemas import ProbablePitcherRow
from fantasy_avail.services import probable_pitchers
from fantasy_avail.services.probable_pitchers import (
    _index_probables_by_game,
    _opposing_pitcher_name,
    _probable_row_sort_key,
    default_start_date,
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


class DefaultStartDatePacificTests(unittest.TestCase):
    UTC = dt.timezone.utc

    def _run_at(self, moment: dt.datetime) -> dt.date:
        class _FrozenDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.astimezone(tz)

        with mock.patch.object(probable_pitchers.dt, "datetime", _FrozenDatetime):
            return default_start_date()

    def test_late_tuesday_pacific_still_before_midnight(self) -> None:
        # Tue Jul 7 2026 11:30 PM PT (still Tuesday in Pacific) -> Wednesday
        moment = dt.datetime(2026, 7, 8, 6, 30, tzinfo=self.UTC)  # 23:30 PT Tue
        self.assertEqual(self._run_at(moment), dt.date(2026, 7, 8))

    def test_after_midnight_pacific_rolls_forward(self) -> None:
        # Wed Jul 8 2026 12:30 AM PT -> Thursday
        moment = dt.datetime(2026, 7, 8, 7, 30, tzinfo=self.UTC)  # 00:30 PT Wed
        self.assertEqual(self._run_at(moment), dt.date(2026, 7, 9))

    def test_uses_pacific_not_host_utc(self) -> None:
        # 06:30 UTC on Jul 8 is already Wednesday in UTC/Eastern but still
        # Tuesday in Pacific, so tomorrow must be Wednesday (Jul 8), not Thursday.
        moment = dt.datetime(2026, 7, 8, 6, 30, tzinfo=self.UTC)
        self.assertEqual(self._run_at(moment).isoformat(), "2026-07-08")


if __name__ == "__main__":
    unittest.main()
