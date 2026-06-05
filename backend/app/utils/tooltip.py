from __future__ import annotations

import json
import re
from html import unescape
from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        raw = json.dumps(value, ensure_ascii=False)
    else:
        raw = str(value)
    raw = unescape(raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace("\\n", " ").replace("\n", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def parse_tooltip(tooltip: Any) -> tuple[dict[str, Any], str]:
    if isinstance(tooltip, str):
        try:
            obj = json.loads(tooltip)
            return obj, normalize_text(obj)
        except Exception:
            return {}, normalize_text(tooltip)
    if isinstance(tooltip, dict):
        return tooltip, normalize_text(tooltip)
    return {}, normalize_text(tooltip)


def first_int(patterns: list[str], text: str) -> int | None:
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except Exception:
                continue
    return None


def first_float(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                continue
    return None
