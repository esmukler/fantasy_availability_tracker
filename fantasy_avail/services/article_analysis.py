from __future__ import annotations

from typing import Dict, List, Optional

from fantasy_avail.article_availability_summary import (
    article_text_from_soup,
    fetch_article_soup,
    summarize_available_player_mentions,
)
from fantasy_avail.yahoo import (
    FANTASY_AVAIL_SOURCE_KEY,
    availability_index_from_lookups,
    lookup_players_availability,
)
from fantasy_avail.article_main_players import extract_main_players
from fantasy_avail.availability_cache import AvailabilityCache, get_availability_cache
from fantasy_avail.config import AppConfig, load_config
from fantasy_avail.name_utils import normalize_name
from fantasy_avail.schemas import AnalyzeArticleAvailabilityResult, ArticleAvailablePlayer


def _snippets_for_main_players(
    article_text: str,
    main_players: List[str],
    available_by_name: Dict[str, dict],
    *,
    max_snippets: int,
) -> List[ArticleAvailablePlayer]:
    subset: Dict[str, dict] = {}
    for name in main_players:
        key = normalize_name(name)
        hit = available_by_name.get(key)
        if hit:
            subset[key] = hit
    if not subset:
        return []

    mentions = summarize_available_player_mentions(
        article_text,
        subset,
        max_snippets=max_snippets,
    )
    return [ArticleAvailablePlayer.from_mention(m) for m in mentions]


def analyze_article_availability(
    url: str,
    *,
    include_waivers: bool = True,
    max_snippets: int = 2,
    league_id: Optional[int] = None,
    refresh: bool = False,
    cache: Optional[AvailabilityCache] = None,
    config: Optional[AppConfig] = None,
) -> AnalyzeArticleAvailabilityResult:
    cfg = config or load_config()
    lid = league_id if league_id is not None else cfg.league_id
    c = cache or get_availability_cache()
    warnings: List[str] = []

    try:
        soup = fetch_article_soup(url)
        article_text = article_text_from_soup(soup)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch article: {e}") from e

    extraction = extract_main_players(html=soup, text=article_text)
    warnings.extend(extraction.warnings)

    league_reused = c.has_league(lid) and not refresh
    league = c.get_league(lid, refresh=refresh)
    lookups = lookup_players_availability(
        league,
        extraction.main_players,
        include_waivers=include_waivers,
    )
    available_by_name = availability_index_from_lookups(lookups)
    was_cached = league_reused

    available_main_keys = {
        normalize_name(name)
        for name in extraction.main_players
        if normalize_name(name) in available_by_name
    }
    not_in_pool = [
        name
        for name in extraction.main_players
        if normalize_name(name) not in available_by_name
    ]

    available = _snippets_for_main_players(
        article_text,
        extraction.main_players,
        available_by_name,
        max_snippets=max_snippets,
    )

    mentioned_keys = {a.normalized_name for a in available}
    for key in available_main_keys - mentioned_keys:
        hit = available_by_name[key]
        available.append(
            ArticleAvailablePlayer(
                player_name=str(hit.get("name") or key.title()),
                normalized_name=key,
                availability=str(hit.get(FANTASY_AVAIL_SOURCE_KEY) or "free_agent"),
                snippets=[],
                yahoo_player=hit,
            )
        )
        warnings.append(
            f"No article snippet matched {hit.get('name')}; player is in FA/waiver pool."
        )

    available.sort(key=lambda a: a.player_name.lower())

    return AnalyzeArticleAvailabilityResult(
        url=url,
        league_id=lid,
        cached=was_cached,
        main_players=extraction.main_players,
        available=available,
        not_in_pool=not_in_pool,
        also_named=extraction.also_named,
        extraction_warnings=warnings,
    )
