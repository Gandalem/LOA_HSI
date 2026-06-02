from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _walk(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _first(obj: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


def _name(obj: Dict[str, Any]) -> Optional[str]:
    value = _first(obj, ["Text", "Name", "CodeName", "ValueName", "OptionName", "CategoryName", "ClassName", "Label"])
    if isinstance(value, str):
        return value
    return None


def _code(obj: Dict[str, Any]) -> Optional[int]:
    value = _first(obj, ["Value", "Code", "CategoryCode", "Id", "ID", "OptionCode", "Key"])
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _as_option(obj: Any) -> Optional[Dict[str, Any]]:
    if isinstance(obj, str):
        return {"code": obj, "name": obj}
    if not isinstance(obj, dict):
        return None
    name = _name(obj)
    code = _code(obj)
    if name is None and code is None:
        return None
    return {"code": code if code is not None else name, "name": name if name is not None else str(code)}


def _children(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for key in ["Subs", "SubOptions", "EtcSubs", "Options", "Items", "Children", "Values"]:
        value = obj.get(key)
        if isinstance(value, list):
            for item in value:
                opt = _as_option(item)
                if opt:
                    result.append(opt)
            if result:
                return result
    return result


def _find_list_by_key(data: Any, target_keys: List[str]) -> List[Any]:
    lowered = {x.lower() for x in target_keys}
    for obj in _walk(data):
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            if key.lower() in lowered and isinstance(value, list):
                return value
    return []


def _unique_options(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        name = str(item.get("name", "")).strip()
        code = item.get("code")
        if not name:
            continue
        dedupe_key = (name, str(code))
        if dedupe_key in seen:
            continue
        result.append(item)
        seen.add(dedupe_key)
    result.sort(key=lambda x: str(x.get("name", "")))
    return result


def parse_auction_options(data: Any) -> Dict[str, Any]:
    """로스트아크 auctions/options 응답을 프론트 드롭다운용으로 정리합니다.

    공식 응답 구조가 변경되거나 래퍼마다 key 이름이 조금 달라도 최대한 동작하게
    보수적으로 파싱합니다. 원본은 기존 /api/options/auctions로 확인할 수 있습니다.
    """
    categories: List[Dict[str, Any]] = []
    for obj in _find_list_by_key(data, ["Categories", "categories"]):
        if isinstance(obj, dict):
            opt = _as_option(obj)
            if opt:
                opt["children"] = _children(obj)
                categories.append(opt)

    classes: List[Dict[str, Any]] = []
    for item in _find_list_by_key(data, ["Classes", "CharacterClasses", "classes"]):
        opt = _as_option(item)
        if opt:
            classes.append(opt)

    grades: List[Dict[str, Any]] = []
    for item in _find_list_by_key(data, ["ItemGrades", "Grades", "itemGrades"]):
        opt = _as_option(item)
        if opt:
            grades.append(opt)

    tiers: List[Dict[str, Any]] = []
    for item in _find_list_by_key(data, ["ItemTiers", "Tiers", "itemTiers"]):
        opt = _as_option(item)
        if opt:
            tiers.append(opt)

    etc_options: List[Dict[str, Any]] = []
    for obj in _find_list_by_key(data, ["EtcOptions", "etcOptions"]):
        if isinstance(obj, dict):
            opt = _as_option(obj)
            if opt:
                opt["children"] = _children(obj)
                etc_options.append(opt)

    # 자주 쓰는 하위 옵션을 별도 목록으로 분류합니다.
    combat_stats_names = {"치명", "특화", "신속", "제압", "인내", "숙련"}
    combat_stats: List[Dict[str, Any]] = []
    engravings: List[Dict[str, Any]] = []

    for group in etc_options:
        group_name = str(group.get("name", ""))
        group_code = group.get("code")
        for child in group.get("children", []):
            child_name = str(child.get("name", ""))
            full = {
                "group_code": group_code,
                "group_name": group_name,
                "code": child.get("code"),
                "name": child_name,
            }
            if child_name in combat_stats_names or "특성" in group_name:
                combat_stats.append(full)
            if "각인" in group_name or child_name not in combat_stats_names:
                # 너무 넓게 잡되, 프론트에서 검색 가능한 후보로 둡니다.
                engravings.append(full)

    return {
        "categories": _unique_options(categories),
        "classes": _unique_options(classes),
        "grades": _unique_options(grades),
        "tiers": _unique_options(tiers),
        "etc_options": etc_options,
        "combat_stats": _unique_options(combat_stats),
        "engraving_options": _unique_options(engravings),
    }
