from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Iterable


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = clean_text(value)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return value or "sin-categoria"


def normalize_for_compare(value: Any) -> Any:
    if isinstance(value, str):
        return clean_text(value).casefold()
    if isinstance(value, list):
        return [normalize_for_compare(v) for v in value]
    if isinstance(value, dict):
        return {k: normalize_for_compare(v) for k, v in sorted(value.items())}
    return value


def content_hash(value: Any) -> str:
    return hashlib.sha256(repr(normalize_for_compare(value)).encode("utf-8")).hexdigest()


def parse_price(text: str) -> float | None:
    text = clean_text(text).replace("$", "").replace("USD", "")
    match = re.search(r"-?\d[\d.,]*", text)
    if not match:
        return None
    raw = match.group(0)
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None

