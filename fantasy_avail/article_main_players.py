from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Set

from bs4 import BeautifulSoup, Tag

from fantasy_avail.name_utils import normalize_name

_SPACE_RE = re.compile(r"\s+")
_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
_NUMBERED_NAME = re.compile(
    r"^\s*(?:\d+[\.)]|[#•*-])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
)
_BYLINE_RE = re.compile(r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", re.I)

_EXCLUDE_PHRASES = (
    "related stories",
    "latest news",
    "read more",
    "sign up",
    "newsletter",
    "all rights reserved",
    "terms of use",
    "privacy policy",
    "follow us",
    "advertisement",
    "sponsored",
)

_NOISE_NAMES = frozenset(
    normalize_name(n)
    for phrase in (
        "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
        "American League National League",
        "Major League Baseball",
        "Fantasy Baseball",
        "New York Los Angeles San Francisco",
    )
    for n in phrase.split()
)

_COMMON_SUFFIXES = ("Jr", "Sr", "II", "III", "IV")


@dataclass
class MainPlayerExtraction:
    main_players: List[str] = field(default_factory=list)
    also_named: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _clean_name(name: str) -> str:
    return _SPACE_RE.sub(" ", name.strip())


def _is_plausible_player_name(name: str) -> bool:
    cleaned = _clean_name(name)
    if not cleaned or len(cleaned) < 4:
        return False
    parts = cleaned.split()
    if len(parts) < 2 or len(parts) > 3:
        return False
    key = normalize_name(cleaned)
    if not key or key in _NOISE_NAMES:
        return False
    if parts[0].lower() in ("the", "and", "for", "with", "from", "your", "our", "by", "all"):
        return False
    if any(part.lower() in ("the", "and", "for", "with", "from", "your", "our") for part in parts):
        return False
    return True


def _dedupe_ordered(names: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for raw in names:
        cleaned = _clean_name(raw)
        if not _is_plausible_player_name(cleaned):
            continue
        key = normalize_name(cleaned)
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _names_from_text_block(text: str) -> List[str]:
    found: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _NUMBERED_NAME.match(line)
        if m:
            found.append(m.group(1))
            continue
        for match in _NAME_PATTERN.findall(line):
            found.append(match)
    return found


def _first_cell_player_name(row: Tag) -> Optional[str]:
    link = row.find("a", href=True)
    if link:
        text = _clean_name(link.get_text(" ", strip=True))
        if _is_plausible_player_name(text):
            return text
    cells = row.find_all(["td", "th"])
    if not cells:
        return None
    first = _clean_name(cells[0].get_text(" ", strip=True))
    if _is_plausible_player_name(first):
        return first
    for cell in cells[:3]:
        for match in _NAME_PATTERN.findall(cell.get_text(" ", strip=True)):
            if _is_plausible_player_name(match):
                return match
    return None


def _find_main_container(soup: BeautifulSoup) -> Tag:
    article = soup.find("article") or soup.find("main")
    return article if article is not None else soup.body or soup


def _container_text(container: Tag) -> str:
    chunks: List[str] = []
    for tag in container.find_all(["p", "li", "h2", "h3", "h4"]):
        parent_classes = " ".join(tag.get("class") or []).lower()
        if any(x in parent_classes for x in ("related", "sidebar", "comment", "newsletter")):
            continue
        txt = tag.get_text(" ", strip=True)
        if txt:
            chunks.append(txt)
    for table in container.find_all("table"):
        for row in table.find_all("tr"):
            name = _first_cell_player_name(row)
            if name:
                chunks.append(name)
            for cell in row.find_all(["td", "th"]):
                cell_text = cell.get_text(" ", strip=True)
                if cell_text:
                    chunks.append(cell_text)
    return "\n".join(chunks)


def extract_main_players_from_soup(soup: BeautifulSoup) -> MainPlayerExtraction:
    warnings: List[str] = []
    container = _find_main_container(soup)
    main_names: List[str] = []
    also_named: List[str] = []

    for table in container.find_all("table"):
        for row in table.find_all("tr"):
            name = _first_cell_player_name(row)
            if name:
                main_names.append(name)

    for tag in container.find_all(["li", "p", "h3", "h4"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        lower = text.lower()
        if any(phrase in lower for phrase in _EXCLUDE_PHRASES):
            continue
        if _BYLINE_RE.search(text) and len(text) < 80:
            continue
        numbered = _NUMBERED_NAME.match(text)
        if numbered:
            main_names.append(numbered.group(1))
            continue
        names = _NAME_PATTERN.findall(text)
        if not names:
            continue
        first_sentence = text.split(".")[0]
        for name in names:
            if name in first_sentence:
                main_names.append(name)
            else:
                also_named.append(name)

    if not main_names:
        warnings.append(
            "No table or list structure found; falling back to paragraph name scan."
        )
        body_text = _container_text(container)
        main_names.extend(_names_from_text_block(body_text))

    main_players = _dedupe_ordered(main_names)
    also = _dedupe_ordered(also_named)
    also = [n for n in also if normalize_name(n) not in {normalize_name(m) for m in main_players}]

    if not main_players:
        warnings.append("Could not identify main editorial players from article HTML.")

    return MainPlayerExtraction(
        main_players=main_players,
        also_named=also[:20],
        warnings=warnings,
    )


def extract_main_players_from_text(text: str) -> MainPlayerExtraction:
    warnings: List[str] = []
    lower = text.lower()
    if any(phrase in lower for phrase in _EXCLUDE_PHRASES):
        warnings.append("Article text may include sidebar or footer content.")

    main_names = _names_from_text_block(text)
    main_players = _dedupe_ordered(main_names)
    if not main_players:
        warnings.append("Could not identify main editorial players from article text.")

    return MainPlayerExtraction(
        main_players=main_players,
        also_named=[],
        warnings=warnings,
    )


def extract_main_players(
    *,
    html: Optional[BeautifulSoup] = None,
    text: Optional[str] = None,
) -> MainPlayerExtraction:
    if html is not None:
        return extract_main_players_from_soup(html)
    if text:
        return extract_main_players_from_text(text)
    return MainPlayerExtraction(warnings=["No article content provided."])
