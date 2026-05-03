from __future__ import annotations

import re
from typing import Optional

from ..models import StudentGroup


_LOWER_WORDS = {"and", "of", "for", "in", "the", "to"}


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _smart_title_token(token: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        return ""
    if re.fullmatch(r"[A-Z0-9]{2,10}", cleaned):
        return cleaned
    if re.fullmatch(r"[A-Za-z]{2,10}[0-9]{1,4}", cleaned) and cleaned.upper() == cleaned:
        return cleaned
    lower = cleaned.lower()
    if lower in _LOWER_WORDS:
        return lower
    return lower[:1].upper() + lower[1:]


def _smart_title(text: str) -> str:
    parts = re.split(r"(\s+)", _normalize_whitespace(text))
    titled: list[str] = []
    for idx, part in enumerate(parts):
        if not part or part.isspace():
            titled.append(part)
            continue
        token = _smart_title_token(part)
        if idx == 0 and token in _LOWER_WORDS:
            token = token[:1].upper() + token[1:]
        titled.append(token)
    return "".join(titled).strip()


def format_department_name(name: Optional[str]) -> str:
    raw = _normalize_whitespace(name or "")
    if not raw:
        return ""
    raw = re.sub(r"[_-]+", " ", raw)
    return _smart_title(raw)


def format_person_name(name: Optional[str]) -> str:
    raw = _normalize_whitespace(name or "")
    if not raw:
        return ""
    raw = re.sub(r"\s+", " ", raw)
    return _smart_title(raw)


def format_room_name(name: Optional[str]) -> str:
    raw = _normalize_whitespace(name or "")
    if not raw:
        return ""
    if re.fullmatch(r"[A-Za-z]{1,6}[0-9]{0,4}", raw.replace("-", "")):
        return raw.upper()
    return _smart_title(raw.replace("_", " "))


def format_group_name(raw_name: Optional[str], display_code: Optional[str] = None) -> str:
    raw = _normalize_whitespace(raw_name or "")
    if not raw:
        return display_code or ""

    normalized = re.sub(r"[_]+", " ", raw)
    normalized = re.sub(r"\s*-\s*", "-", normalized)

    match = re.fullmatch(
        r"(?P<code>[A-Za-z]{2,10})[-\s]*(?:(?:yr|year|y)\s*)?(?P<level>[1-9])(?:[-\s]+(?P<tail>.+))?",
        normalized,
        flags=re.IGNORECASE,
    )
    if match:
        code = match.group("code").upper()
        level = match.group("level")
        tail = _smart_title(match.group("tail") or "")
        return f"{code} Year {level}" + (f" {tail}" if tail else "")

    suffix_match = re.fullmatch(
        r"(?P<prefix>.+?)\s+(?:yr|year|y)\s*(?P<level>[1-9])(?P<tail>\b.*)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if suffix_match:
        prefix = _smart_title(suffix_match.group("prefix"))
        level = suffix_match.group("level")
        tail = _smart_title(suffix_match.group("tail") or "")
        return f"{prefix} Year {level}" + (f" {tail}" if tail else "")

    return _smart_title(normalized.replace("-", " "))


def format_group_label(group: Optional[StudentGroup], *, prefer_code: bool = False) -> str:
    if not group:
        return ""
    display_code = _normalize_whitespace(getattr(group, "display_code", "") or "")
    if prefer_code and display_code:
        return display_code.upper()
    return format_group_name(getattr(group, "name", None), display_code=display_code) or (
        display_code.upper() if display_code else ""
    )
