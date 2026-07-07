from __future__ import annotations

import argparse
import datetime as dt
from typing import List, Optional

from fantasy_avail.services.probable_pitchers import run_probable_pitchers_cli


def _parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}', expected YYYY-MM-DD") from e


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Find MLB probable starters for the next N days who are free agents or on waivers "
            "in a Yahoo Fantasy Baseball league.\n\n"
            "Prereqs:\n"
            "  - Create a Yahoo OAuth app and download/compose an OAuth JSON file (client_id/client_secret).\n"
            "  - First run will open a browser for Yahoo login and cache tokens on disk.\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--league-id", type=int, default=43384, help="Yahoo league_id (default: 43384)")
    p.add_argument("--days", type=int, default=5, help="Number of days starting at start-date (default: 5)")
    p.add_argument(
        "--start-date",
        type=_parse_date,
        default=dt.date.today() + dt.timedelta(days=1),
        help="First day of the schedule window, YYYY-MM-DD (default: tomorrow)",
    )
    p.add_argument(
        "--oauth",
        default="oauth2.json",
        help="Path to Yahoo OAuth JSON credentials (default: oauth2.json)",
    )
    p.add_argument(
        "--token-dir",
        default=".yahoo_tokens",
        help="Directory to store cached Yahoo tokens (default: .yahoo_tokens)",
    )
    p.add_argument(
        "--abbr-overrides",
        default="team_abbr_overrides.json",
        help="JSON file mapping StatsAPI team abbreviations to your preferred ones",
    )
    p.add_argument(
        "--player-overrides",
        default="player_name_overrides.json",
        help="JSON with yahoo_name_by_slug and mlbam_by_slug for manual Yahoo/MLBAM fixes",
    )
    p.add_argument(
        "--opponent-colors-csv",
        default=None,
        metavar="PATH",
        help=(
            "team_ops CSV (rank,team,ops) for opponent color tiers: top 5 OPS red, "
            "next 5 yellow, bottom 7 green. Default: team_ops_{season}.csv in the repo"
        ),
    )
    p.add_argument(
        "--no-opponent-colors",
        action="store_true",
        help="Disable terminal coloring of opponent team abbreviations",
    )
    p.add_argument(
        "--fp-cookie-file",
        default="fantasypros_cookie.txt",
        help=(
            "File containing Fantasy Pros Cookie header value (for logged-in full grid). "
            "Default: fantasypros_cookie.txt — see fantasypros_cookie.example. "
            "Use empty path to skip: --fp-cookie-file ''"
        ),
    )
    p.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Also print probable pitchers that did not match a Yahoo FA or waiver pitcher name",
    )
    p.add_argument(
        "--all-probables",
        action="store_true",
        help="Show all probable pitchers, marking each as AVAILABLE or TAKEN",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (still prints errors to stderr)",
    )
    p.add_argument(
        "--season",
        type=int,
        default=None,
        help="MLB season year for stats (default: year of --start-date)",
    )
    p.add_argument(
        "--skip-team-ops-update",
        action="store_true",
        help="Do not refresh team_ops_{season}.csv (normally updated at most once per day)",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_probable_pitchers_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
