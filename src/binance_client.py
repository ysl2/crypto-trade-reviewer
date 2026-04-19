from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from src.exchange_types import ExchangeAPIError, SymbolMeta


DEFAULT_BASE_URL = "https://api.binance.com"


class BinanceAPIError(ExchangeAPIError):
    """Raised when Binance returns a handled API error."""


class BinanceSpotReadOnlyClient:
    """Minimal Binance Spot client that only exposes read-only GET endpoints."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        headers = {
            "Accept": "application/json",
            "User-Agent": "crypto-trade-reviewer/1.0",
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        self.session.headers.update(headers)

    def _handle_response(self, response: requests.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceAPIError(
                f"Binance returned non-JSON response with HTTP {response.status_code}."
            ) from exc

        if response.ok:
            return payload

        if isinstance(payload, dict):
            code = payload.get("code", "unknown")
            message = payload.get("msg", "Unknown Binance error")
            raise BinanceAPIError(
                f"HTTP {response.status_code}, Binance code {code}: {message}"
            )

        raise BinanceAPIError(f"HTTP {response.status_code}: {payload!r}")

    def _public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(
            f"{self.base_url}{path}",
            params={k: v for k, v in (params or {}).items() if v is not None},
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        cleaned = {k: v for k, v in (params or {}).items() if v is not None}
        cleaned.setdefault("recvWindow", 60_000)
        cleaned["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(cleaned, doseq=True)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        url = f"{self.base_url}{path}?{query_string}&signature={signature}"
        response = self.session.get(url, timeout=self.timeout)
        return self._handle_response(response)

    def get_exchange_info(self, permissions: str = "SPOT") -> dict[str, Any]:
        return self._public_get("/api/v3/exchangeInfo", {"permissions": permissions})

    def get_symbol_price(self, symbol: str) -> dict[str, Any]:
        return self._public_get("/api/v3/ticker/price", {"symbol": symbol})

    def get_account_trades(
        self,
        symbol: str,
        *,
        limit: int = 1000,
        start_time: int | None = None,
        end_time: int | None = None,
        from_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._signed_get(
            "/api/v3/myTrades",
            {
                "symbol": symbol,
                "limit": limit,
                "startTime": start_time,
                "endTime": end_time,
                "fromId": from_id,
            },
        )
