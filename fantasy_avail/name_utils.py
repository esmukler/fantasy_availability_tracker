from __future__ import annotations

import re
import unicodedata

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?$", re.IGNORECASE)
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9 ]+")
_SPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """
    Normalize a player name for cross-source matching (MLB vs Yahoo).

    - Removes accents (e.g. José -> Jose)
    - Lowercases
    - Drops punctuation
    - Removes common suffixes (Jr., Sr., II, III, IV, V)
    """
    name = name.strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.lower()
    name = name.replace("’", "'")
    name = _NON_ALNUM_SPACE_RE.sub(" ", name)
    name = _SPACE_RE.sub(" ", name).strip()
    name = _SUFFIX_RE.sub("", name).strip()
    name = _SPACE_RE.sub(" ", name).strip()
    return name


def slug_to_display_name(slug: str) -> str:
    """Derive a display name from a Fantasy Pros player URL slug (e.g. chris-sale -> Chris Sale)."""
    return " ".join(part.title() for part in slug.strip().lower().split("-") if part)
