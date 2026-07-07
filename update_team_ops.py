#!/usr/bin/env python3
"""Refresh team_ops_{season}.csv from the MLB Stats API."""

from __future__ import annotations

import argparse
from pathlib import Path

import requests

from fantasy_avail.mlb_api import (
    default_team_ops_csv_path,
    record_team_ops_csv_refreshed,
    write_team_ops_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="MLB season year (default: current calendar year)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="CSV path (default: team_ops_{season}.csv in repo root)",
    )
    args = parser.parse_args()
    out = args.output if args.output is not None else default_team_ops_csv_path(args.season)
    session = requests.Session()
    write_team_ops_csv(session, out, season=args.season)
    record_team_ops_csv_refreshed()
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
