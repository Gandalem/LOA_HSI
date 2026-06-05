from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from fastapi import HTTPException

from app.core.settings import get_settings


class LostArkClient:
    """LostArk Armory client.

    v8 방향:
    - 캐릭터 조회 안정성을 위해 개별 endpoint 방식을 기본으로 사용합니다.
    - pyLoa에서 참고한 total-info endpoint는 optional 보조 조회로만 사용합니다.
    - profile/equipment는 필수, engravings/arkpassive는 실패해도 조회 전체를 막지 않습니다.
    """

    TOTAL_INFO_FILTERS = ["profiles", "equipment", "engravings", "arkpassive"]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.lostark_api_base.rstrip("/")
        self.session = requests.Session()
        if self.settings.lostark_api_key:
            # 공식 예시는 bearer 소문자를 사용하지만 일부 프록시 환경을 고려해 값만 정확히 유지합니다.
            self.session.headers.update({"Authorization": f"bearer {self.settings.lostark_api_key}"})
        self.session.headers.update({"accept": "application/json"})

    def _get(self, path: str, params: dict[str, Any] | None = None, optional: bool = False) -> Any:
        if not self.settings.lostark_api_key:
            raise HTTPException(status_code=400, detail="LOSTARK_API_KEY가 비어 있습니다. .env에 JWT를 입력하세요.")
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, params=params, timeout=20)
        except requests.RequestException as exc:
            if optional:
                return None
            raise HTTPException(status_code=502, detail=f"로스트아크 API 요청 실패: {exc}") from exc

        if response.status_code in {204, 404} and optional:
            return None
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없거나 공개 정보가 없습니다.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="로스트아크 API 요청 제한에 도달했습니다. 잠시 후 다시 시도하세요.")
        if response.status_code >= 400:
            if optional:
                return None
            raise HTTPException(status_code=response.status_code, detail=f"로스트아크 API 오류: {response.text[:500]}")
        if not response.text:
            return None
        try:
            return response.json()
        except ValueError as exc:
            if optional:
                return None
            raise HTTPException(status_code=502, detail=f"로스트아크 API JSON 파싱 실패: {response.text[:300]}") from exc



    def _post(self, path: str, json_body: dict[str, Any] | None = None, optional: bool = False) -> Any:
        if not self.settings.lostark_api_key:
            raise HTTPException(status_code=400, detail="LOSTARK_API_KEY가 비어 있습니다. .env에 JWT를 입력하세요.")
        url = f"{self.base_url}{path}"
        try:
            response = self.session.post(url, json=json_body, timeout=20)
        except requests.RequestException as exc:
            if optional:
                return None
            raise HTTPException(status_code=502, detail=f"로스트아크 API 요청 실패: {exc}") from exc

        if response.status_code in {204, 404} and optional:
            return None
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="요청한 리소스를 찾을 수 없습니다.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="로스트아크 API 요청 제한에 도달했습니다. 잠시 후 다시 시도하세요.")
        if response.status_code >= 400:
            if optional:
                return None
            raise HTTPException(status_code=response.status_code, detail=f"로스트아크 API 오류: {response.text[:500]}")
        if not response.text:
            return None
        try:
            return response.json()
        except ValueError as exc:
            if optional:
                return None
            raise HTTPException(status_code=502, detail=f"로스트아크 API JSON 파싱 실패: {response.text[:300]}") from exc

    def get_market_item(self, item_id: int) -> Any:
        return self._get(f"/markets/items/{item_id}")

    def get_market_options(self) -> Any:
        return self._get("/markets/options")

    def search_market_items(self, params: dict[str, Any] | None = None) -> Any:
        # 로스트아크 거래소 검색은 GET query가 아니라 POST body 방식입니다.
        # pyLoa의 MarketsEndpoint.search_items도 POST /markets/items를 사용합니다.
        return self._post("/markets/items", json_body=params or {})

    def post_market_trades(self, payload: dict[str, Any]) -> Any:
        # 로스트아크 거래소 최근 거래 내역도 /markets 하위입니다.
        return self._post("/markets/trades", json_body=payload)

    def _cache_path(self, character_name: str) -> Path:
        safe = quote(character_name, safe="")
        return self.settings.data_dir / "cache" / f"character_{safe}_v8.json"

    def _raw_path(self, character_name: str) -> Path:
        safe = quote(character_name, safe="")
        ts = time.strftime("%Y%m%d_%H%M%S")
        p = self.settings.data_dir / "raw" / "characters"
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{safe}_{ts}_v8.json"

    def _normalize_total_info(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        profile = data.get("ArmoryProfile")
        equipment = data.get("ArmoryEquipment")
        if not profile or not equipment:
            return None
        return {
            "profile": profile,
            "equipment": equipment or [],
            "engravings": data.get("ArmoryEngraving"),
            "arkpassive": data.get("ArkPassive"),
            "_source": "armory_total_info",
            "rawTotal": data,
        }

    def _fetch_total_info_bundle_optional(self, encoded_name: str) -> dict[str, Any] | None:
        # pyLoa ArmoriesEndpoint.get_total_info와 같은 형태입니다.
        # 다만 환경에 따라 이 endpoint/filter가 실패하거나 빈 응답을 줄 수 있어 optional로만 사용합니다.
        data = self._get(
            f"/armories/characters/{encoded_name}",
            params={"filters": ",".join(self.TOTAL_INFO_FILTERS)},
            optional=True,
        )
        return self._normalize_total_info(data)

    def _fetch_separate_bundle(self, encoded_name: str) -> dict[str, Any]:
        # 안정적인 기본 조회 방식. profile/equipment만 필수입니다.
        profile = self._get(f"/armories/characters/{encoded_name}/profiles")
        equipment = self._get(f"/armories/characters/{encoded_name}/equipment")
        engravings = self._get(f"/armories/characters/{encoded_name}/engravings", optional=True)
        arkpassive = self._get(f"/armories/characters/{encoded_name}/arkpassive", optional=True)
        return {
            "profile": profile,
            "equipment": equipment or [],
            "engravings": engravings,
            "arkpassive": arkpassive,
            "_source": "separate_endpoints",
        }

    def get_character_bundle(self, character_name: str, use_cache: bool = True) -> tuple[dict[str, Any], str | None]:
        cache_path = self._cache_path(character_name)
        now = time.time()
        if use_cache and cache_path.exists():
            age = now - cache_path.stat().st_mtime
            if age <= self.settings.cache_ttl_seconds:
                return json.loads(cache_path.read_text(encoding="utf-8")), str(cache_path)

        encoded = quote(character_name, safe="")
        errors: dict[str, str] = {}

        # 1) 안정적인 개별 endpoint로 먼저 조회합니다.
        bundle = self._fetch_separate_bundle(encoded)

        # 2) pyLoa total-info는 추가 정보가 더 잘 오는 경우만 보조로 병합합니다.
        total_bundle = self._fetch_total_info_bundle_optional(encoded)
        if total_bundle:
            # profile/equipment는 개별 endpoint 값을 유지하고, 보조 섹션만 비어 있을 때 채웁니다.
            if not bundle.get("engravings") and total_bundle.get("engravings"):
                bundle["engravings"] = total_bundle.get("engravings")
            if not bundle.get("arkpassive") and total_bundle.get("arkpassive"):
                bundle["arkpassive"] = total_bundle.get("arkpassive")
            bundle["rawTotal"] = total_bundle.get("rawTotal")
            bundle["_source"] = "separate_endpoints_with_total_info_aux"
        else:
            errors["total_info_aux"] = "total-info 보조 조회는 실패하거나 빈 응답이어서 개별 endpoint 결과만 사용했습니다."

        bundle.setdefault("errors", {}).update(errors)
        bundle["fetchedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        cache_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_path = self._raw_path(character_name)
        raw_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        return bundle, str(raw_path)
