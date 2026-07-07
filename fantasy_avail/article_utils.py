from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

import requests
from bs4 import BeautifulSoup

from fantasy_avail.name_utils import normalize_name
from fantasy_avail.yahoo import AVAIL_SOURCE_FREE_AGENT, FANTASY_AVAIL_SOURCE_KEY

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

_ARTICLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class MentionSummary:
    player_name: str
    normalized_name: str
    availability: str
    yahoo_player: Dict[str, Any]
    snippets: List[str]


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
            row_text = " | ".join(
                c.get_text(" ", strip=True) for c in cells if c.get_text(strip=True)
            )
            if row_text:
                chunks.append(row_text)

    text = "\n".join(chunks)
    text = _SPACE_RE.sub(" ", text).strip()
    if not text:
        raise ValueError("Could not extract readable article text from URL.")
    return text


def fetch_article_text(url: str, timeout: int = 30) -> str:
    return article_text_from_soup(fetch_article_soup(url, timeout=timeout))


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
                availability=str(
                    player.get(FANTASY_AVAIL_SOURCE_KEY) or AVAIL_SOURCE_FREE_AGENT
                ),
                yahoo_player=player,
                snippets=unique,
            )
        )

    out.sort(key=lambda m: m.player_name.lower())
    return out
