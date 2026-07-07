from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from fantasy_avail.name_utils import normalize_name
from fantasy_avail.yahoo import (
    AVAIL_SOURCE_FREE_AGENT,
    AVAIL_SOURCE_WAIVERS,
    FANTASY_AVAIL_SOURCE_KEY,
    enrich_available_by_name_for_names,
    init_league,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SPACE_RE = re.compile(r"\s+")
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9 ]+")

_SUMMARY_KEYWORDS = (
    "injury",
    "injured",
    "returns",
    "returning",
    "starting",
    "starter",
    "lineup",
    "called up",
    "promotion",
    "demotion",
    "activated",
    "activation",
    "rotation",
    "closer",
    "save",
    "role",
    "hot",
    "cold",
    "streak",
)

_FALLBACK_POSITIONS = ("C", "1B", "2B", "3B", "SS", "OF", "Util", "SP", "RP")


@dataclass(frozen=True)
class MentionSummary:
    player_name: str
    normalized_name: str
    availability: str
    yahoo_player: Dict[str, Any]
    snippets: List[str]


@dataclass(frozen=True)
class ArticleAnalysisResult:
    summaries: List[MentionSummary]
    mentioned_names: List[str]
    unmatched_names: List[str]


_ARTICLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_article_soup(url: str, timeout: int = 30) -> BeautifulSoup:
    resp = requests.get(url, headers=_ARTICLE_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
        tag.decompose()
    return soup


def _article_body_tag(soup: BeautifulSoup):
    return soup.find("article") or soup.find("main")


def article_text_from_soup(soup: BeautifulSoup) -> str:
    chunks: List[str] = []
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        chunks.append(title)

    article_tag = _article_body_tag(soup)
    if article_tag is not None:
        paragraphs = article_tag.find_all(["p", "li"])
        tables = article_tag.find_all("table")
    else:
        paragraphs = soup.find_all("p")
        tables = soup.find_all("table")

    for p in paragraphs:
        txt = p.get_text(" ", strip=True)
        if txt:
            chunks.append(txt)

    for table in tables:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            row_text = " | ".join(c.get_text(" ", strip=True) for c in cells if c.get_text(strip=True))
            if row_text:
                chunks.append(row_text)

    text = "\n".join(chunks)
    text = _SPACE_RE.sub(" ", text).strip()
    if not text:
        raise ValueError("Could not extract readable article text from URL.")
    return text


def fetch_article_text(url: str, timeout: int = 30) -> str:
    return article_text_from_soup(fetch_article_soup(url, timeout=timeout))


def _dedupe_players(players: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for p in players:
        key = str(
            p.get("player_id")
            or p.get("player_key")
            or p.get("name")
            or json.dumps(p, sort_keys=True, default=str)
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _tag_players(players: Iterable[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    tagged: List[Dict[str, Any]] = []
    for p in players:
        row = dict(p)
        row[FANTASY_AVAIL_SOURCE_KEY] = source
        tagged.append(row)
    return tagged


def _fetch_free_agents_all_positions(league) -> List[Dict[str, Any]]:
    all_free_agents: List[Dict[str, Any]] = []
    try:
        all_free_agents = league.free_agents() or []
    except TypeError:
        for pos in _FALLBACK_POSITIONS:
            all_free_agents.extend(league.free_agents(pos) or [])
    except Exception:
        for pos in _FALLBACK_POSITIONS:
            try:
                all_free_agents.extend(league.free_agents(pos) or [])
            except Exception:
                continue
    return _dedupe_players(all_free_agents)


def _fetch_waivers(league) -> List[Dict[str, Any]]:
    waiver_players: List[Dict[str, Any]] = []
    try:
        waiver_players = league.waivers() or []
    except Exception:
        waiver_players = []
    return _dedupe_players(waiver_players)


def fetch_yahoo_available_players(league, include_waivers: bool = True) -> List[Dict[str, Any]]:
    all_free_agents = _fetch_free_agents_all_positions(league)
    tagged = _tag_players(all_free_agents, AVAIL_SOURCE_FREE_AGENT)
    if not include_waivers:
        return tagged

    waiver_players = _fetch_waivers(league)
    fa_names = {normalize_name(str(p.get("name") or "")) for p in tagged}
    for p in waiver_players:
        nm = normalize_name(str(p.get("name") or ""))
        if not nm or nm in fa_names:
            continue
        row = dict(p)
        row[FANTASY_AVAIL_SOURCE_KEY] = AVAIL_SOURCE_WAIVERS
        tagged.append(row)

    return tagged


def index_players_by_normalized_name(players: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for p in players:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        key = normalize_name(name)
        if key and key not in idx:
            idx[key] = p
    return idx


def split_sentences(text: str) -> List[str]:
    text = _SPACE_RE.sub(" ", text).strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _normalized_words(text: str) -> str:
    t = _NON_ALNUM_SPACE_RE.sub(" ", text.lower())
    return _SPACE_RE.sub(" ", t).strip()


def _sentence_mentions_name(sentence: str, normalized_name: str) -> bool:
    if not normalized_name:
        return False
    haystack = f" {_normalized_words(sentence)} "
    needle = f" {normalized_name} "
    return needle in haystack


def _rank_and_trim_snippets(snippets: Sequence[str], max_snippets: int) -> List[str]:
    ranked = sorted(
        snippets,
        key=lambda s: sum(1 for k in _SUMMARY_KEYWORDS if k in s.lower()),
        reverse=True,
    )
    unique: List[str] = []
    seen: set[str] = set()
    for s in ranked:
        if s in seen:
            continue
        seen.add(s)
        unique.append(s)
        if len(unique) >= max_snippets:
            break
    return unique


def extract_candidate_player_names(article_text: str) -> List[str]:
    # Basic capitalized-name heuristic to aid debugging and alias tuning.
    pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
    candidates = pattern.findall(article_text)
    out: List[str] = []
    seen: set[str] = set()
    for name in candidates:
        cleaned = _SPACE_RE.sub(" ", name.strip())
        key = normalize_name(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def summarize_available_player_mentions(
    article_text: str,
    available_by_name: Dict[str, Dict[str, Any]],
    max_snippets: int = 2,
) -> List[MentionSummary]:
    sentences = split_sentences(article_text)
    hits: Dict[str, List[str]] = {}

    for sentence in sentences:
        for normalized_name in available_by_name.keys():
            if _sentence_mentions_name(sentence, normalized_name):
                hits.setdefault(normalized_name, []).append(sentence)

    out: List[MentionSummary] = []
    for normalized_name, snippet_list in hits.items():
        unique = _rank_and_trim_snippets(snippet_list, max_snippets)
        player = available_by_name[normalized_name]
        out.append(
            MentionSummary(
                player_name=str(player.get("name") or normalized_name.title()),
                normalized_name=normalized_name,
                availability=str(player.get(FANTASY_AVAIL_SOURCE_KEY) or AVAIL_SOURCE_FREE_AGENT),
                yahoo_player=player,
                snippets=unique,
            )
        )

    out.sort(key=lambda m: m.player_name.lower())
    return out


def analyze_article_against_availability(
    article_text: str,
    available_by_name: Dict[str, Dict[str, Any]],
    max_snippets: int = 2,
) -> ArticleAnalysisResult:
    summaries = summarize_available_player_mentions(
        article_text,
        available_by_name,
        max_snippets=max_snippets,
    )
    mentioned_names = extract_candidate_player_names(article_text)
    matched_keys = {s.normalized_name for s in summaries}
    unmatched_names = [
        name for name in mentioned_names if normalize_name(name) not in matched_keys
    ]
    return ArticleAnalysisResult(
        summaries=summaries,
        mentioned_names=mentioned_names,
        unmatched_names=unmatched_names,
    )


def run_article_availability_summary(
    *,
    url: str,
    league_id: int,
    oauth_path: str,
    token_dir: str,
    include_waivers: bool = True,
    max_snippets: int = 2,
) -> List[MentionSummary]:
    text = fetch_article_text(url)
    league = init_league(league_id, oauth_path, token_dir)
    available_players = fetch_yahoo_available_players(league, include_waivers=include_waivers)
    available_by_name = index_players_by_normalized_name(available_players)
    enrich_available_by_name_for_names(
        league,
        extract_candidate_player_names(text),
        available_by_name,
        include_waivers=include_waivers,
    )
    return summarize_available_player_mentions(
        text,
        available_by_name,
        max_snippets=max_snippets,
    )


def run_article_availability_summary_with_debug(
    *,
    url: str,
    league_id: int,
    oauth_path: str,
    token_dir: str,
    include_waivers: bool = True,
    max_snippets: int = 2,
) -> ArticleAnalysisResult:
    text = fetch_article_text(url)
    league = init_league(league_id, oauth_path, token_dir)
    available_players = fetch_yahoo_available_players(league, include_waivers=include_waivers)
    available_by_name = index_players_by_normalized_name(available_players)
    enrich_available_by_name_for_names(
        league,
        extract_candidate_player_names(text),
        available_by_name,
        include_waivers=include_waivers,
    )
    return analyze_article_against_availability(
        article_text=text,
        available_by_name=available_by_name,
        max_snippets=max_snippets,
    )
