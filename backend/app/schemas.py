from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MarketItemConfig(BaseModel):
    key: str = Field(description="시뮬레이터에서 사용할 내부 키. 예: honor_shard")
    name: str = Field(description="표시용 아이템명")
    item_id: int = Field(description="로스트아크 마켓 아이템 ID")


class AuctionQueryConfig(BaseModel):
    key: str = Field(description="시뮬레이터에서 사용할 내부 키. 예: ability_stone, accessory_base")
    name: str = Field(description="표시용 이름")
    payload: Dict[str, Any] = Field(description="POST /auctions/items에 보낼 raw request body")
    price_mode: str = Field(default="min_buy_price", description="min_buy_price 또는 avg_top_n")
    save_as_latest: bool = Field(default=True, description="검색 결과 가격을 latest_prices.json에 저장할지 여부")


class AuctionSearchRequest(BaseModel):
    key: str = Field(default="custom_auction", description="저장할 내부 가격 키")
    name: str = Field(default="사용자 경매장 검색", description="표시용 이름")
    payload: Dict[str, Any] = Field(description="POST /auctions/items에 보낼 raw request body")
    price_mode: str = Field(default="min_buy_price")
    save_as_latest: bool = Field(default=False)
    top_n: int = Field(default=5, ge=1, le=50)


class CollectMarketRequest(BaseModel):
    items: List[MarketItemConfig]


class CollectAuctionRequest(BaseModel):
    queries: List[AuctionQueryConfig]


class PriceSnapshotItem(BaseModel):
    key: str
    name: str
    price_gold: Optional[float]
    source: str
    raw_path: str
    note: Optional[str] = None


class CollectResponse(BaseModel):
    saved_to: str
    items: List[PriceSnapshotItem]
    warning: Optional[str] = None


class AuctionItemView(BaseModel):
    item_name: Optional[str] = None
    grade: Optional[str] = None
    tier: Optional[int] = None
    quality: Optional[int] = None
    buy_price: Optional[float] = None
    bid_price: Optional[float] = None
    start_price: Optional[float] = None
    end_date: Optional[str] = None
    options: List[str] = []
    raw: Dict[str, Any] = {}


class AuctionSearchResponse(BaseModel):
    key: str
    name: str
    price_gold: Optional[float]
    price_mode: str
    total_count: Optional[int]
    raw_path: str
    saved_to: Optional[str]
    items: List[AuctionItemView]
    note: Optional[str] = None


class SimulationRequest(BaseModel):
    users: int = Field(default=1000, ge=100, le=200000)
    seed: int = Field(default=42)
    krw_per_gold: float = Field(default=0.4, gt=0)
    include_stone: bool = True
    include_accessory: bool = True
    stone_target_a: int = Field(default=7, ge=0, le=10)
    stone_target_b: int = Field(default=7, ge=0, le=10)
    stone_max_negative: int = Field(default=4, ge=0, le=10)
    stone_price_gold: Optional[int] = Field(default=None, ge=0)
    accessory_base_gold: Optional[int] = Field(default=None, ge=0)
    actual_user_gold: Optional[int] = Field(default=None, ge=0)
    save_parquet: bool = False
    use_latest_api_prices: bool = True


class HistogramBin(BaseModel):
    label: str
    count: int


class SummaryResponse(BaseModel):
    users: int
    avg_gold: float
    p50_gold: float
    p90_gold: float
    p99_gold: float
    avg_krw: float
    p50_krw: float
    p90_krw: float
    p99_krw: float
    bad_luck_tax_gold: float
    bad_luck_tax_krw: float
    honing_avg_gold: float
    stone_avg_gold: float
    accessory_avg_gold: float
    max_fail_streak_avg: float
    stone_attempts_avg: float
    histogram: List[HistogramBin]
    user_percentile: Optional[float] = None
    user_message: Optional[str] = None
    parquet_path: Optional[str] = None
    price_source: str
    assumptions: List[str]
