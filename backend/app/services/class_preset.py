from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.schemas import CharacterSummary


def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


@lru_cache(maxsize=1)
def load_class_engraving_data() -> dict[str, Any]:
    path = _config_dir() / "class_engraving_options.json"
    if not path.exists():
        return {"metadata": {}, "records": [], "classes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _records_for_class(class_name: str | None) -> list[dict[str, Any]]:
    data = load_class_engraving_data()
    cname = _norm(class_name)
    out = []
    for rec in data.get("records", []):
        if _norm(rec.get("class_name")) == cname:
            out.append(dict(rec))
    return out


def _bundle_text(bundle: dict[str, Any] | None) -> str:
    if not isinstance(bundle, dict):
        return ""
    # 우선 각인/아크패시브 영역을 보고, 부족하면 전체 번들을 보조로 봅니다.
    parts = [bundle.get("engravings"), bundle.get("arkpassive"), bundle.get("rawTotal")]
    try:
        text = "\n".join(json.dumps(x, ensure_ascii=False) for x in parts if x is not None)
    except Exception:
        text = str(parts)
    if not text.strip():
        try:
            text = json.dumps(bundle, ensure_ascii=False)
        except Exception:
            text = str(bundle)
    return text


def _effect_lines(character: CharacterSummary) -> list[str]:
    lines: list[str] = []
    for acc in character.accessories or []:
        lines.extend([str(x) for x in (acc.accessory_effects or [])])
        lines.extend([str(x) for x in (acc.bracelet_effects or [])])
    return lines


def _contains_any(text: str, values: list[str]) -> bool:
    return any(v and v in text for v in values)


def _infer_role_from_character(character: CharacterSummary) -> str | None:
    text = "\n".join(_effect_lines(character))
    support_tokens = ["낙인", "아군 공격력", "아군 피해", "보호막", "회복", "치명타 저항", "비수", "약점 노출", "응원"]
    dealer_tokens = ["추가 피해", "적에게 주는 피해", "치명타 피해", "치명타 적중률", "피해 증가"]
    if _contains_any(text, support_tokens):
        return "서포터"
    if _contains_any(text, dealer_tokens):
        return "딜러"
    return None


def _current_stats(character: CharacterSummary) -> set[str]:
    found: set[str] = set()
    for line in _effect_lines(character):
        for stat in ["치명", "특화", "신속", "제압", "인내", "숙련"]:
            if stat in line:
                found.add(stat)
    return found


def _flat_polish_options(record: dict[str, Any]) -> list[str]:
    opts = record.get("polish_options") or {}
    out: list[str] = []
    if isinstance(opts, dict):
        for value in opts.values():
            if isinstance(value, list):
                out.extend(str(x) for x in value)
    return out


def _score_record(record: dict[str, Any], character: CharacterSummary, bundle_text: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    engraving = str(record.get("engraving_name") or "")
    if engraving and engraving in bundle_text:
        score += 1000
        reasons.append("API 응답에서 직업각인명 직접 감지")

    inferred_role = _infer_role_from_character(character)
    if inferred_role and inferred_role == record.get("role"):
        score += 40
        reasons.append(f"장신구/팔찌 효과 기준 역할 {inferred_role} 추정")

    stats = _current_stats(character)
    for stat in record.get("bracelet_stats") or []:
        if stat in stats:
            score += 6
            reasons.append(f"팔찌/효과 특성 {stat} 일치")

    effects = "\n".join(_effect_lines(character))
    for opt in record.get("bracelet_options") or []:
        if opt and opt in effects:
            score += 8
            reasons.append(f"팔찌 옵션 {opt} 일치")
    # 설명형 팔찌 효과를 직업각인 프리셋 키워드로 보정합니다.
    if record.get("role") == "서포터":
        if "아군 공격력 강화" in effects and "응원" in (record.get("bracelet_options") or []):
            score += 8
            reasons.append("응원 계열 설명형 효과 감지")
        if "치명타 저항" in effects and any(x in (record.get("bracelet_options") or []) for x in ["비수", "약점 노출"]):
            score += 8
            reasons.append("비수/약점 노출 계열 설명형 효과 감지")

    for opt in _flat_polish_options(record):
        if opt and opt in effects:
            score += 3

    # valid_stats는 '신특', '특치'처럼 붙어 있으므로 현재 팔찌/효과에서 보이는 특성과 비교합니다.
    abbrev = {"치": "치명", "특": "특화", "신": "신속"}
    for combo in record.get("valid_stats") or []:
        combo_stats = {full for short, full in abbrev.items() if short in str(combo)}
        if combo_stats and combo_stats.issubset(stats):
            score += 8
            reasons.append(f"대표 특성 조합 {combo} 일치")

    return score, reasons[:8]


def resolve_class_engraving_preset(character: CharacterSummary, bundle: dict[str, Any] | None = None) -> dict[str, Any] | None:
    records = _records_for_class(character.class_name)
    if not records:
        return None
    text = _bundle_text(bundle)
    scored = []
    for rec in records:
        score, reasons = _score_record(rec, character, text)
        scored.append((score, rec, reasons))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best, reasons = scored[0]

    # 감지 근거가 전혀 없고 후보가 2개 이상이면 첫 후보를 쓰되 낮은 신뢰도로 표시합니다.
    confidence = "high" if best_score >= 1000 else "medium" if best_score >= 35 else "low"
    method = "api_engraving_name" if best_score >= 1000 else "auto_inferred_from_current_options" if best_score >= 35 else "class_default_fallback"
    preset = {
        "classGroup": best.get("class_group"),
        "className": best.get("class_name"),
        "engravingName": best.get("engraving_name"),
        "role": best.get("role"),
        "validStats": best.get("valid_stats") or [],
        "braceletStats": best.get("bracelet_stats") or [],
        "braceletOptions": best.get("bracelet_options") or [],
        "polishType": best.get("polish_type"),
        "polishOptions": best.get("polish_options") or {},
        "notes": best.get("notes") or [],
        "confidence": confidence,
        "detectionMethod": method,
        "score": round(float(best_score), 2),
        "reasons": reasons,
        "candidateEngravings": [r.get("engraving_name") for r in records],
        "source": "backend/config/class_engraving_options.json",
    }
    return preset
