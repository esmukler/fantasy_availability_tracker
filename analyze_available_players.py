#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from fantasy_avail.article_availability_summary import (
    ArticleAnalysisResult,
    run_article_availability_summary,
    run_article_availability_summary_with_debug,
)
from fantasy_avail.services.article_analysis import analyze_article_availability
from fantasy_avail.yahoo import AVAIL_SOURCE_WAIVERS

_NONE_TEXT = "(none)"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Fetch an article URL and summarize only the players mentioned who are "
            "currently available in your Yahoo fantasy league."
        )
    )
    p.add_argument("--url", required=True, help="Article URL to analyze")
    p.add_argument("--league-id", type=int, default=43384, help="Yahoo league id")
    p.add_argument("--oauth", default="oauth2.json", help="Path to Yahoo OAuth JSON credentials")
    p.add_argument(
        "--token-dir",
        default=".yahoo_tokens",
        help="Directory for cached Yahoo OAuth tokens",
    )
    p.add_argument(
        "--no-waivers",
        action="store_true",
        help="Exclude waiver players (only include free agents)",
    )
    p.add_argument(
        "--max-snippets",
        type=int,
        default=2,
        help="Max number of article snippets per matched player (default: 2)",
    )
    p.add_argument(
        "--debug-unmatched",
        action="store_true",
        help="Show detected names and which names were not matched as available",
    )
    p.add_argument("--json", action="store_true", help="Print JSON output")
    p.add_argument(
        "--main-players-only",
        action="store_true",
        help="Use main-player extraction pipeline (same as MCP analyze_article_availability)",
    )
    return p


def _summaries_from_main_players_result(result) -> list:
    from fantasy_avail.article_availability_summary import MentionSummary

    summaries = []
    for item in result.available:
        summaries.append(
            MentionSummary(
                player_name=item.player_name,
                normalized_name=item.normalized_name,
                availability=item.availability,
                yahoo_player=item.yahoo_player,
                snippets=item.snippets,
            )
        )
    return summaries


def _run_main_players_analysis(args: argparse.Namespace):
    result = analyze_article_availability(
        args.url,
        include_waivers=not args.no_waivers,
        max_snippets=args.max_snippets,
        league_id=args.league_id,
    )
    summaries = _summaries_from_main_players_result(result)
    debug = ArticleAnalysisResult(
        summaries=summaries,
        mentioned_names=result.main_players,
        unmatched_names=result.not_in_pool,
    )
    return summaries, debug, result


def _run_analysis(args: argparse.Namespace):
    if args.main_players_only:
        return _run_main_players_analysis(args)
    if args.debug_unmatched:
        debug_result = run_article_availability_summary_with_debug(
            url=args.url,
            league_id=args.league_id,
            oauth_path=args.oauth,
            token_dir=args.token_dir,
            include_waivers=not args.no_waivers,
            max_snippets=args.max_snippets,
        )
        return debug_result.summaries, debug_result, None

    summaries = run_article_availability_summary(
        url=args.url,
        league_id=args.league_id,
        oauth_path=args.oauth,
        token_dir=args.token_dir,
        include_waivers=not args.no_waivers,
        max_snippets=args.max_snippets,
    )
    return summaries, None, None


def _json_payload(summaries: list) -> list:
    payload = []
    for s in summaries:
        payload.append(
            {
                "player_name": s.player_name,
                "normalized_name": s.normalized_name,
                "availability": s.availability,
                "snippets": s.snippets,
            }
        )
    return payload


def _print_debug_sections(debug_result: ArticleAnalysisResult) -> None:
    print("\nDebug: detected player-like names")
    print("-" * 72)
    if debug_result.mentioned_names:
        for name in debug_result.mentioned_names:
            print(f"- {name}")
    else:
        print(_NONE_TEXT)

    print("\nDebug: detected names not matched as available")
    print("-" * 72)
    if debug_result.unmatched_names:
        for name in debug_result.unmatched_names:
            print(f"- {name}")
    else:
        print(_NONE_TEXT)


def _print_text_output(
    summaries: list, debug_result: Optional[ArticleAnalysisResult], league_id: int
) -> None:
    print(f"Available players mentioned in article (league_id={league_id})")
    print("-" * 72)
    if not summaries:
        print(_NONE_TEXT)
        if debug_result is not None:
            _print_debug_sections(debug_result)
        return

    for i, s in enumerate(summaries):
        if i > 0:
            print()
        waiver_marker = " (W)" if s.availability == AVAIL_SOURCE_WAIVERS else ""
        print(f"[AVAIL]{waiver_marker} {s.player_name}")
        for snip in s.snippets:
            print(f"  - {snip}")

    if debug_result is not None:
        _print_debug_sections(debug_result)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.max_snippets < 1:
        print("--max-snippets must be >= 1", file=sys.stderr)
        return 2

    try:
        summaries, debug_result, main_result = _run_analysis(args)
    except Exception as e:
        print(f"Failed to analyze article: {e}", file=sys.stderr)
        return 1

    if args.json:
        if args.main_players_only and main_result is not None:
            print(json.dumps(main_result.to_dict(), indent=2))
            return 0
        payload = _json_payload(summaries)
        if args.debug_unmatched and debug_result is not None:
            wrapper = {
                "available_summaries": payload,
                "detected_names": debug_result.mentioned_names,
                "unmatched_names": debug_result.unmatched_names,
            }
            print(json.dumps(wrapper, indent=2))
            return 0
        print(json.dumps(payload, indent=2))
        return 0

    _print_text_output(summaries, debug_result, args.league_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
