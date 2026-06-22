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
    """LostArk Armory/Auction client with optional pacing and 429 retries."""

    TOTAL_INFO_FILTERS = ["profiles", "equipment", "engravings", "arkpassive"]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.lostark_api_base.rstrip("/")
        self.session = requests.Session()
        self._last_request_monotonic = 0.0
        if self.settings.lostark_api_key:
            self.session.headers.update({"Authorization": f"bearer {self.settings.lostark_api_key}"})
        self.session.headers.update({"accept": "application/json"})

    def _respect_rate_limit(self) -> None:
        interval_ms = int(self.settings.lostark_min_request_interval_ms or 0)
        if interval_ms <= 0:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        wait_seconds = max(0.0, (interval_ms / 1000.0) - elapsed)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> requests.Response | None:
        retry_count = max(0, int(self.settings.lostark_retry_429_count or 0))
        retry_sleep = max(0.0, float(self.settings.lostark_retry_429_sleep_seconds or 0.0))
        attempt = 0
        while True:
            self._respect_rate_limit()
            self._last_request_monotonic = time.monotonic()
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=20)
                else:
                    response = self.session.post(url, json=json_body, timeout=20)
            except requests.RequestException as exc:
                if optional:
                    return None
                raise HTTPException(status_code=502, detail=f"로스트아크 API 요청 실패: {exc}") from exc

            if response.status_code != 429 or attempt >= retry_count:
                return response

            attempt += 1
            if retry_sleep > 0:
                time.sleep(retry_sleep)

    def _get(self, path: str, params: dict[str, Any] | None = None, optional: bool = False) -> Any:
        if not self.settings.lostark_api_key:
            if optional:
                return None
            raise HTTPException(status_code=400, detail="LOSTARK_API_KEY가 비어 있습니다. .env에 JWT를 입력하세요.")
        url = f"{self.base_url}{path}"
        response = self._request_with_retry("GET", url, params=params, optional=optional)
        if response is None:
            return None

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
            if optional:
                return None
            raise HTTPException(status_code=400, detail="LOSTARK_API_KEY가 비어 있습니다. .env에 JWT를 입력하세요.")
        url = f"{self.base_url}{path}"
        response = self._request_with_retry("POST", url, json_body=json_body, optional=optional)
        if response is None:
            return None

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
        return self._post("/markets/items", json_body=params or {})

    def get_auction_options(self, optional: bool = True) -> Any:
        return self._get("/auctions/options", optional=optional)

    def search_auction_items(self, payload: dict[str, Any] | None = None, optional: bool = True) -> Any:
        return self._post("/auctions/items", json_body=payload or {}, optional=optional)

    def post_market_trades(self, payload: dict[str, Any]) -> Any:
        return self._post("/markets/trades", json_body=payload)

    def _cache_path(self, character_name: str) -> Path:
        safe = quote(character_name, safe="")
        return self.settings.data_dir / "cache" / f"character_{safe}_v8.json"

    def _raw_path(self, character_name: str) -> Path:
        safe = quote(character_name, safe="")
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = self.settings.data_dir / "raw" / "characters"
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{safe}_{ts}_v8.json"

    def _normalize_total_info(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        profile = data.get("ArmoryProfile")
        equipment = data.get("ArmoryEquipment")
        if not profile or not equipment:
            return None
        return {
            "profile": profile,
            "equipment": equipment,
            "engravings": data.get("ArmoryEngraving"),
            "arkpassive": data.get("ArkPassive"),
            "_source": "armory_total_info",
            "rawTotal": data,
        }

    def _fetch_total_info_bundle_optional(self, encoded_name: str) -> dict[str, Any] | None:
        data = self._get(
            f"/armories/characters/{encoded_name}",
            params={"filters": ",".join(self.TOTAL_INFO_FILTERS)},
            optional=True,
        )
        return self._normalize_total_info(data)

    def _fetch_separate_bundle(self, encoded_name: str) -> dict[str, Any]:
        profile = self._get(f"/armories/characters/{encoded_name}/profiles")
        equipment = self._get(f"/armories/characters/{encoded_name}/equipment")
        engravings = self._get(f"/armories/characters/{encoded_name}/engravings", optional=True)
        arkpassive = self._get(f"/armories/characters/{encoded_name}/arkpassive", optional=True)
        return {
            "profile": profile,
            "equipment": equipment,
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

        bundle = self._fetch_separate_bundle(encoded)
        total_bundle = self._fetch_total_info_bundle_optional(encoded)
        if total_bundle:
            if not bundle.get("engravings") and total_bundle.get("engravings"):
                bundle["engravings"] = total_bundle.get("engravings")
            if not bundle.get("arkpassive") and total_bundle.get("arkpassive"):
                bundle["arkpassive"] = total_bundle.get("arkpassive")
            bundle["rawTotal"] = total_bundle.get("rawTotal")
            bundle["_source"] = "separate_endpoints_with_total_info_aux"
        else:
            errors["total_info_aux"] = "total-info 보조 조회는 생략되었습니다."

        bundle.setdefault("errors", {}).update(errors)
        bundle["fetchedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        cache_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_path = self._raw_path(character_name)
        raw_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        return bundle, str(raw_path)
