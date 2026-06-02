from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AuctionSearchRequest,
    AuctionSearchResponse,
    CollectAuctionRequest,
    CollectMarketRequest,
    CollectResponse,
    PriceSnapshotItem,
    SimulationRequest,
    SummaryResponse,
)
from app.services.auction_tools import auction_price, get_total_count, summarize_auction_items
from app.services.lostark_client import LostArkApiError, LostArkClient, sleep_for_rate_limit
from app.services.option_parser import parse_auction_options
from app.services.price_store import (
    extract_market_price,
    load_latest_prices,
    merge_latest_prices,
    save_raw_json,
)
from app.services.simulator import run_simulation

app = FastAPI(title="LOA-HSI API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LostArkApiError)
def lostark_api_error_handler(request: Request, exc: LostArkApiError):
    return JSONResponse(
        status_code=502,
        content={
            "detail": str(exc),
            "hint": "API 키, payload 조건, CategoryCode, 옵션 코드를 확인하세요. 프론트의 옵션 조회 후 드롭다운으로 다시 검색하는 것을 권장합니다.",
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "loa-hsi-api"}


@app.get("/api/prices/latest")
def latest_prices():
    return load_latest_prices()


@app.get("/api/options/markets")
def market_options():
    client = LostArkClient()
    response = client.get_market_options()
    raw_path = save_raw_json("options", "markets", response.data)
    return {"raw_path": raw_path, "data": response.data}


@app.get("/api/options/auctions")
def auction_options():
    client = LostArkClient()
    response = client.get_auction_options()
    raw_path = save_raw_json("options", "auctions", response.data)
    return {"raw_path": raw_path, "data": response.data}




@app.get("/api/options/auctions/parsed")
def auction_options_parsed():
    client = LostArkClient()
    response = client.get_auction_options()
    raw_path = save_raw_json("options", "auctions", response.data)
    return {"raw_path": raw_path, "parsed": parse_auction_options(response.data)}


@app.post("/api/collect/markets", response_model=CollectResponse)
def collect_markets(req: CollectMarketRequest):
    client = LostArkClient()
    new_prices = {}
    results = []

    for item in req.items:
        response = client.get_market_item(item.item_id)
        raw_path = save_raw_json("markets", f"{item.key}_{item.item_id}", response.data)
        price = extract_market_price(response.data)
        new_prices[item.key] = {
            "key": item.key,
            "name": item.name,
            "price_gold": price,
            "source": "GET /markets/items/{itemId}",
            "raw_path": raw_path,
        }
        results.append(
            PriceSnapshotItem(
                key=item.key,
                name=item.name,
                price_gold=price,
                source="GET /markets/items/{itemId}",
                raw_path=raw_path,
                note=None if price is not None else "가격 필드 자동 추출 실패. raw JSON을 확인하세요.",
            )
        )
        sleep_for_rate_limit()

    saved_to = merge_latest_prices(new_prices)
    return CollectResponse(saved_to=saved_to, items=results)


@app.post("/api/collect/auctions", response_model=CollectResponse)
def collect_auctions(req: CollectAuctionRequest):
    client = LostArkClient()
    new_prices = {}
    results = []

    for query in req.queries:
        response = client.post_auction_items(query.payload)
        raw_path = save_raw_json("auctions", query.key, response.data)
        price = auction_price(response.data, mode=query.price_mode, top_n=5)
        if query.save_as_latest:
            new_prices[query.key] = {
                "key": query.key,
                "name": query.name,
                "price_gold": price,
                "source": "POST /auctions/items",
                "raw_path": raw_path,
                "payload": query.payload,
                "price_mode": query.price_mode,
            }
        results.append(
            PriceSnapshotItem(
                key=query.key,
                name=query.name,
                price_gold=price,
                source="POST /auctions/items",
                raw_path=raw_path,
                note=None if price is not None else "즉시 구매가 자동 추출 실패. payload 조건 또는 raw JSON을 확인하세요.",
            )
        )
        sleep_for_rate_limit()

    saved_to = merge_latest_prices(new_prices) if new_prices else "not_saved"
    return CollectResponse(saved_to=saved_to, items=results)


@app.post("/api/auctions/search", response_model=AuctionSearchResponse)
def search_auction(req: AuctionSearchRequest):
    client = LostArkClient()
    response = client.post_auction_items(req.payload)
    raw_path = save_raw_json("auctions", req.key, response.data)
    price = auction_price(response.data, mode=req.price_mode, top_n=req.top_n)
    items = summarize_auction_items(response.data, top_n=req.top_n)

    saved_to = None
    if req.save_as_latest:
        saved_to = merge_latest_prices(
            {
                req.key: {
                    "key": req.key,
                    "name": req.name,
                    "price_gold": price,
                    "source": "POST /auctions/items",
                    "raw_path": raw_path,
                    "payload": req.payload,
                    "price_mode": req.price_mode,
                }
            }
        )

    return AuctionSearchResponse(
        key=req.key,
        name=req.name,
        price_gold=price,
        price_mode=req.price_mode,
        total_count=get_total_count(response.data),
        raw_path=raw_path,
        saved_to=saved_to,
        items=items,
        note=None if price is not None else "검색 결과에서 가격을 찾지 못했습니다. payload 조건을 확인하세요.",
    )


@app.post("/api/simulations/run", response_model=SummaryResponse)
def run(req: SimulationRequest):
    return run_simulation(req)
