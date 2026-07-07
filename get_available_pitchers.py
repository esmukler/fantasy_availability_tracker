#!/usr/bin/env python3

"""
Get MLB probable starters for the next N days and print the ones who are
currently Yahoo free agents or on waivers in your Fantasy Baseball league
(waivers are labeled with (W) in the text report).

Probable pitchers are scraped from Fantasy Pros' default "next 7 days" grid
(https://www.fantasypros.com/mlb/probable-pitchers.php). Only dates that appear
on that page are available; use --start-date and --days to filter within it.

By default the schedule window starts tomorrow (not today): the next N calendar
days beginning the day after you run the script (e.g. N=5 → tomorrow through four
days after).

Quickstart (recommended: virtualenv):

  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install -r requirements.txt

Then create an OAuth credentials JSON (default: oauth2.json) and run:

  python get_available_pitchers.py --league-id 43384 --show-unmatched

Optional JSON files:
  team_abbr_overrides.json — map StatsAPI-style abbreviations for display
  player_name_overrides.json — yahoo_name_by_slug / mlbam_by_slug for manual fixes

Optional Fantasy Pros login (full probable-pitchers table):
  fantasypros_cookie.txt — paste the browser Cookie header value (see fantasypros_cookie.example)

For available pitchers, MLB season stats (W-L, ERA, WHIP, IP, K, QS) are fetched from
StatsAPI (season + seasonAdvanced for quality starts).

Implementation lives in the fantasy_avail package; this file is the CLI entry point.
"""

from fantasy_avail.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
