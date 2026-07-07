from __future__ import annotations

from typing import Any, Dict, Optional

StatHighlight = Optional[str]  # None, "good", "warn", "bad"


def parse_innings_pitched(value: Any) -> Optional[float]:
    """Parse MLB IP (e.g. 72.1 = 72⅓ innings) to decimal innings."""
    if value is None or value == "—":
        return None
    text = str(value).strip()
    if not text or text == "—":
        return None
    try:
        if "." in text:
            whole, frac = text.split(".", 1)
            whole_i = int(whole)
            if len(frac) != 1 or frac not in "012":
                return float(text)
            return whole_i + int(frac) / 3.0
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_stat_float(value: Any) -> Optional[float]:
    if value is None or value == "—":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def era_highlight(era: Any) -> StatHighlight:
    value = parse_stat_float(era)
    if value is None:
        return None
    if value > 6:
        return "bad"
    if value > 5:
        return "warn"
    if value < 4:
        return "good"
    return None


def whip_highlight(whip: Any) -> StatHighlight:
    value = parse_stat_float(whip)
    if value is None:
        return None
    if value > 1.7:
        return "bad"
    if value > 1.5:
        return "warn"
    if value < 1.2:
        return "good"
    return None


def k_ip_highlight(strikeouts: Any, innings_pitched: Any) -> StatHighlight:
    ip = parse_innings_pitched(innings_pitched)
    if ip is None:
        return None
    try:
        ks = int(strikeouts)
    except (TypeError, ValueError):
        return None
    if ks > ip:
        return "good"
    return None


def stat_highlights_for(stats: Dict[str, Any]) -> Dict[str, StatHighlight]:
    return {
        "era": era_highlight(stats.get("era")),
        "whip": whip_highlight(stats.get("whip")),
        "k_ip": k_ip_highlight(stats.get("strikeouts"), stats.get("innings_pitched")),
    }
