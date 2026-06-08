from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.lostark_client import LostArkClient
from app.services.material_price_store import MaterialPriceStore, extract_market_price

router = APIRouter(prefix="/material-prices", tags=["material-prices"])


def _config_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "config"
    if path.exists():
        return path
    return Path("/app/backend/config")


class MaterialItemConfig(BaseModel):
    key: str
    name: str
    searchName: str | None = None
    itemId: int | None = None
    categoryCode: int | None = 50000
    divideByBundleCount: bool = True
    priceDivisor: float = Field(default=1.0, gt=0)
    enabled: bool = True


class CollectMaterialPricesRequest(BaseModel):
    items: list[MaterialItemConfig] | None = None
    useConfigFile: bool = True
    forceRefresh: bool = False
    ttlMinutes: int = Field(default=360, ge=0, le=1440)


class MaterialPriceRow(BaseModel):
    materialKey: str
    materialName: str
    searchName: str | None = None
    itemId: int | None = None
    rawPriceGold: float | None = None
    bundleCount: float | None = None
    unitPriceGold: float | None = None
    source: str
    rawPath: str | None = None
    note: str | None = None
    collectedAt: str | None = None


class MaterialPriceResponse(BaseModel):
    items: list[MaterialPriceRow]
    priceFingerprint: str
    cacheUsed: bool = False
    message: str | None = None


def _load_config_items() -> list[MaterialItemConfig]:
    path = _config_dir() / "material_items.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_items = data.get("items", data if isinstance(data, list) else [])
    return [MaterialItemConfig(**x) for x in raw_items]


def _row_from_db(raw: dict[str, Any]) -> MaterialPriceRow:
    collected_at = raw.get("collected_at")
    return MaterialPriceRow(
        materialKey=str(raw.get("material_key")),
        materialName=str(raw.get("material_name") or raw.get("material_key")),
        searchName=raw.get("search_name"),
        itemId=int(raw["item_id"]) if raw.get("item_id") is not None else None,
        rawPriceGold=float(raw["raw_price_gold"]) if raw.get("raw_price_gold") is not None else None,
        bundleCount=float(raw["bundle_count"]) if raw.get("bundle_count") is not None else None,
        unitPriceGold=float(raw["unit_price_gold"]) if raw.get("unit_price_gold") is not None else None,
        source=str(raw.get("source") or "DB"),
        rawPath=raw.get("raw_path"),
        note=raw.get("note"),
        collectedAt=str(collected_at) if collected_at is not None else None,
    )


@router.get("/auto-status")
def material_price_auto_status(request: Request) -> dict[str, Any]:
    return getattr(request.app.state, "material_price_auto_status", {"enabled": False, "message": "아직 자동 수집 상태가 없습니다."})


@router.get("/config", response_model=list[MaterialItemConfig])
def material_price_config() -> list[MaterialItemConfig]:
    return _load_config_items()


@router.get("/latest", response_model=MaterialPriceResponse)
def latest_material_prices() -> MaterialPriceResponse:
    try:
        store = MaterialPriceStore()
        return MaterialPriceResponse(items=[_row_from_db(x) for x in store.latest_rows()], priceFingerprint=store.latest_fingerprint())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"재료 시세 DB 조회 실패: {exc}") from exc


@router.post("/ensure", response_model=MaterialPriceResponse)
def ensure_material_prices(req: CollectMaterialPricesRequest | None = None) -> MaterialPriceResponse:
    """첫 화면용 시세 보장 엔드포인트.

    - 유효한 DB 시세가 있으면 그대로 반환합니다.
    - DB가 비어 있거나 TTL이 지난 경우에만 거래소 API를 호출합니다.
    - 프론트에서 'DB 시세 확인' 버튼을 누르지 않아도 첫 접속 시 자동으로 시세가 준비됩니다.
    """
    req = req or CollectMaterialPricesRequest(forceRefresh=False)
    req.forceRefresh = False
    if req.ttlMinutes <= 0:
        req.ttlMinutes = 360
    return collect_material_prices(req)


@router.post("/collect", response_model=MaterialPriceResponse)
def collect_material_prices(req: CollectMaterialPricesRequest | None = None) -> MaterialPriceResponse:
    req = req or CollectMaterialPricesRequest()
    items = req.items or []
    if req.useConfigFile:
        # 요청으로 items가 들어오면 그것만 쓰고, 비어 있으면 config/material_items.json 사용.
        if not items:
            items = _load_config_items()
    items = [x for x in items if x.enabled]
    if not items:
        raise HTTPException(status_code=400, detail="수집할 재료가 없습니다. config/material_items.json을 확인하세요.")

    store = MaterialPriceStore()
    latest_rows = store.latest_rows()
    valid_latest = [x for x in latest_rows if x.get("unit_price_gold") is not None]
    required_keys = {x.key for x in items}
    valid_latest_keys = {str(x.get("material_key")) for x in valid_latest}
    if not req.forceRefresh and latest_rows:
        latest_time = max((x.get("collected_at") for x in latest_rows if x.get("collected_at") is not None), default=None)
        if latest_time is not None:
            try:
                age_seconds = (datetime.now(timezone.utc).replace(tzinfo=None) - latest_time).total_seconds()
            except Exception:
                age_seconds = None
            has_all_requested = required_keys.issubset(valid_latest_keys)
            if age_seconds is not None and age_seconds <= req.ttlMinutes * 60 and has_all_requested:
                resp = latest_material_prices()
                resp.cacheUsed = True
                resp.message = f"최근 {req.ttlMinutes}분 이내 수집된 시세를 재사용했습니다. 로스트아크 API를 다시 호출하지 않았습니다."
                return resp

    client = LostArkClient()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for item in items:
        raw_data: Any = None
        source = ""
        note = None
        try:
            if item.itemId and item.itemId > 0:
                raw_data = client.get_market_item(item.itemId)
                source = "GET /markets/items/{itemId}"
            else:
                params: dict[str, Any] = {
                    "ItemName": item.searchName or item.name,
                    "PageNo": 1,
                    "Sort": "BUY_PRICE",
                    "SortCondition": "ASC",
                }
                if item.categoryCode:
                    params["CategoryCode"] = item.categoryCode
                raw_data = client.search_market_items(params)

                # 일부 재료는 카테고리 코드가 맞지 않거나 검색명이 애매하면 0건이 올 수 있어
                # 카테고리 없이 한 번 더 검색합니다.
                if not raw_data or not raw_data.get("Items"):
                    fallback_params = {
                        "ItemName": item.searchName or item.name,
                        "PageNo": 1,
                        "Sort": "BUY_PRICE",
                        "SortCondition": "ASC",
                    }
                    raw_data = client.search_market_items(fallback_params)
                source = "POST /markets/items"
            raw_path = store.save_raw(item.key, raw_data)
            raw_price, bundle_count, found_item_id, extract_note = extract_market_price(raw_data, preferred_names=[item.searchName or item.name, item.name])
            note = extract_note
            unit_price = None
            if raw_price is not None:
                denominator = item.priceDivisor
                if item.divideByBundleCount:
                    denominator *= max(float(bundle_count or 1.0), 1.0)
                unit_price = float(raw_price) / denominator
            store.upsert_price(
                {
                    "material_key": item.key,
                    "material_name": item.name,
                    "search_name": item.searchName or item.name,
                    "item_id": item.itemId or found_item_id,
                    "raw_price_gold": raw_price,
                    "bundle_count": bundle_count,
                    "unit_price_gold": unit_price,
                    "source": source,
                    "raw_path": raw_path,
                    "note": note,
                    "collected_at": now,
                }
            )
        except Exception as exc:
            # 한 재료 실패가 전체 수집을 막지 않도록 실패 row도 기록한다.
            store.upsert_price(
                {
                    "material_key": item.key,
                    "material_name": item.name,
                    "search_name": item.searchName or item.name,
                    "item_id": item.itemId,
                    "raw_price_gold": None,
                    "bundle_count": None,
                    "unit_price_gold": None,
                    "source": source or "market-api",
                    "raw_path": None,
                    "note": f"수집 실패: {exc}",
                    "collected_at": now,
                }
            )
        time.sleep(0.75)

    resp = latest_material_prices()
    resp.message = "거래소 시세를 새로 수집했습니다."
    return resp
