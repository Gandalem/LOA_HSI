from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from app.config import LOSTARK_API_BASE, LOSTARK_API_KEY


class LostArkApiError(RuntimeError):
    pass


@dataclass
class LostArkResponse:
    data: Any
    status_code: int
    rate_limit: Dict[str, str]


class LostArkClient:
    """작고 안전한 로스트아크 Open API 클라이언트.

    pyLoa를 직접 의존성으로 고정하지 않고 raw HTTP를 사용합니다. 이유는 과제용
    배포에서 외부 래퍼 버전 변화 때문에 Docker build가 깨지는 일을 피하기 위해서입니다.
    다만 메서드 이름과 payload 구조는 pyLoa README의 markets/auctions 사용법과
    거의 같은 방향으로 맞춰 두었습니다.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 20):
        self.api_key = (api_key or LOSTARK_API_KEY).strip()
        self.base_url = (base_url or LOSTARK_API_BASE).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise LostArkApiError("LOSTARK_API_KEY가 비어 있습니다. .env에 API 키를 넣어주세요.")

    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"bearer {self.api_key}",
        }

    def request(self, method: str, path: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None) -> LostArkResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=self._headers(),
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        rate_limit = {
            key: value
            for key, value in response.headers.items()
            if key.lower().startswith("x-ratelimit")
        }
        if response.status_code == 429:
            reset = rate_limit.get("X-RateLimit-Reset") or rate_limit.get("x-ratelimit-reset")
            raise LostArkApiError(f"요청 제한에 걸렸습니다. 잠시 후 다시 시도하세요. reset={reset}")
        if response.status_code >= 400:
            body = response.text[:800]
            raise LostArkApiError(f"LostArk API 오류: {response.status_code} {body}")
        if not response.text:
            data: Any = None
        else:
            data = response.json()
        return LostArkResponse(data=data, status_code=response.status_code, rate_limit=rate_limit)

    def get_market_item(self, item_id: int) -> LostArkResponse:
        return self.request("GET", f"markets/items/{item_id}")

    def get_market_items(self, params: Optional[dict] = None) -> LostArkResponse:
        return self.request("GET", "markets/items", params=params)

    def post_market_trades(self, payload: dict) -> LostArkResponse:
        return self.request("POST", "market/trades", json_body=payload)

    def get_market_options(self) -> LostArkResponse:
        return self.request("GET", "markets/options")

    def post_auction_items(self, payload: dict) -> LostArkResponse:
        return self.request("POST", "auctions/items", json_body=payload)

    def get_auction_options(self) -> LostArkResponse:
        return self.request("GET", "auctions/options")


def sleep_for_rate_limit(seconds: float = 0.75) -> None:
    """분당 100회 제한을 보수적으로 피하기 위한 기본 대기."""
    time.sleep(seconds)
