from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from src.exchange_types import ExchangeAPIError


DEFAULT_BASE_URL = "https://api.bitget.com"


class BitgetAPIError(ExchangeAPIError):
    """Raised when Bitget returns a handled API error."""


class BitgetSpotReadOnlyClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.passphrase = passphrase.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "locale": "en-US",
                "User-Agent": "crypto-trade-reviewer/1.0",
            }
        )

    def _timestamp(self) -> str:
        return str(int(time.time() * 1000))

    def _handle_response(self, response: requests.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise BitgetAPIError(
                f"Bitget returned non-JSON response with HTTP {response.status_code}."
            ) from exc

        if not isinstance(payload, dict):
            raise BitgetAPIError(f"HTTP {response.status_code}: {payload!r}")

        code = str(payload.get("code", ""))
        if response.ok and code in {"", "00000"}:
            return payload.get("data", [])

        raise BitgetAPIError(
            f"HTTP {response.status_code}, Bitget code {code or 'unknown'}: {payload.get('msg', 'Unknown Bitget error')}"
        )

    def _public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(
            f"{self.base_url}{path}",
            params={k: v for k, v in (params or {}).items() if v not in (None, "")},
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        cleaned = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        query_string = urlencode(cleaned, doseq=True)
        request_path = path if not query_string else f"{path}?{query_string}"
        timestamp = self._timestamp()
        prehash = f"{timestamp}GET{request_path}"
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
        }
        response = self.session.get(
            f"{self.base_url}{request_path}",
            headers=headers,
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def get_symbols(self) -> list[dict[str, Any]]:
        return self._public_get("/api/v2/spot/public/symbols")

    def get_fills(
        self,
        *,
        symbol: str,
        start_time: int | None = None,
        end_time: int | None = None,
        id_less_than: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._signed_get(
            "/api/v2/spot/trade/fills",
            {
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "idLessThan": id_less_than,
                "limit": limit,
            },
        )
