from __future__ import annotations

import datetime as dt
import unittest
from datetime import date
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from fantasy_avail.mlb_api import (
    enrich_probables_with_schedule,
    fetch_mlb_schedule,
    format_game_time_pacific,
)
from fantasy_avail.models import ProbableStart


def _schedule_game(
    *,
    game_pk: int,
    game_date: str,
    away_abbr: str | None,
    home_abbr: str | None,
    away_name: str = "Away Team",
    home_name: str = "Home Team",
) -> dict:
    """Build a schedule game object matching MLB Stats API shape."""
    away_team: dict = {"id": 100, "name": away_name, "link": "/api/v1/teams/100"}
    home_team: dict = {"id": 200, "name": home_name, "link": "/api/v1/teams/200"}
    if away_abbr is not None:
        away_team["abbreviation"] = away_abbr
    if home_abbr is not None:
        home_team["abbreviation"] = home_abbr
    return {
        "gamePk": game_pk,
        "gameDate": f"{game_date}T23:10:00Z",
        "teams": {
            "away": {"team": away_team},
            "home": {"team": home_team},
        },
    }


def _mock_schedule_response(games: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"dates": [{"date": games[0]["gameDate"][:10], "games": games}]}
    return resp


def _probable(
    *,
    game_date: dt.date,
    away_abbr: str = "ATL",
    home_abbr: str = "NYM",
) -> ProbableStart:
    return ProbableStart(
        date=game_date,
        game_pk=None,
        pitcher_name="Chris Sale",
        pitcher_mlbam_id=123,
        pitcher_side="home",
        away_team="Atlanta Braves",
        home_team="New York Mets",
        away_abbr=away_abbr,
        home_abbr=home_abbr,
        fp_slug="chris-sale",
    )


class FormatGameTimePacificTests(unittest.TestCase):
    def test_returns_tbd_when_missing(self) -> None:
        self.assertEqual(format_game_time_pacific(None), "TBD")

    def test_formats_pt(self) -> None:
        utc = dt.datetime(2026, 7, 8, 23, 10, tzinfo=dt.timezone.utc)
        formatted = format_game_time_pacific(utc)
        self.assertTrue(formatted.endswith("PT"))
        pt = utc.astimezone(ZoneInfo("America/Los_Angeles"))
        self.assertIn(str(pt.hour % 12 or 12), formatted)


class EnrichProbablesWithScheduleTests(unittest.TestCase):
    def test_matches_by_date_and_teams(self) -> None:
        game_date = dt.date(2026, 7, 8)
        probables = [_probable(game_date=game_date)]
        game_dt = dt.datetime(2026, 7, 8, 23, 10, tzinfo=dt.timezone.utc)
        schedule = {
            (game_date, "ATL", "NYM"): (777001, game_dt),
        }

        enriched = enrich_probables_with_schedule(probables, schedule)

        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0].game_pk, 777001)
        self.assertEqual(enriched[0].game_datetime, game_dt)
        self.assertTrue(format_game_time_pacific(enriched[0].game_datetime).endswith("PT"))

    def test_leaves_unmatched_as_tbd(self) -> None:
        game_date = dt.date(2026, 7, 8)
        probables = [_probable(game_date=game_date, away_abbr="LAD", home_abbr="SF")]
        schedule = {
            (game_date, "ATL", "NYM"): (777001, dt.datetime(2026, 7, 8, 23, 10, tzinfo=dt.timezone.utc)),
        }

        enriched = enrich_probables_with_schedule(probables, schedule)

        self.assertIsNone(enriched[0].game_pk)
        self.assertIsNone(enriched[0].game_datetime)
        self.assertEqual(format_game_time_pacific(enriched[0].game_datetime), "TBD")


class FetchMlbScheduleTests(unittest.TestCase):
    def test_skips_games_without_abbreviations(self) -> None:
        """Unhydrated API responses omit abbreviation; schedule map stays empty."""
        session = MagicMock()
        session.get.return_value = _mock_schedule_response(
            [
                _schedule_game(
                    game_pk=777001,
                    game_date="2026-07-08",
                    away_abbr=None,
                    home_abbr=None,
                    away_name="Atlanta Braves",
                    home_name="New York Mets",
                )
            ]
        )

        schedule = fetch_mlb_schedule(session, date(2026, 7, 8), date(2026, 7, 8))

        self.assertEqual(schedule, {})
        session.get.assert_called_once()
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params.get("hydrate"), "team")

    def test_parses_hydrated_response(self) -> None:
        """Hydrated responses include abbreviations and populate the schedule map."""
        session = MagicMock()
        session.get.return_value = _mock_schedule_response(
            [
                _schedule_game(
                    game_pk=777001,
                    game_date="2026-07-08",
                    away_abbr="ATL",
                    home_abbr="NYM",
                )
            ]
        )

        schedule = fetch_mlb_schedule(session, date(2026, 7, 8), date(2026, 7, 8))

        game_date = date(2026, 7, 8)
        self.assertIn((game_date, "ATL", "NYM"), schedule)
        game_pk, game_dt = schedule[(game_date, "ATL", "NYM")]
        self.assertEqual(game_pk, 777001)
        self.assertEqual(game_dt, dt.datetime(2026, 7, 8, 23, 10, tzinfo=dt.timezone.utc))

        probables = [_probable(game_date=game_date)]
        enriched = enrich_probables_with_schedule(probables, schedule)
        self.assertNotEqual(format_game_time_pacific(enriched[0].game_datetime), "TBD")


if __name__ == "__main__":
    unittest.main()
