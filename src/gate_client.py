from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from src.exchange_types import ExchangeAPIError


DEFAULT_BASE_URL = "https://api.gateio.ws/api/v4"


class GateAPIError(ExchangeAPIError):
    """Raised when Gate.io returns a handled API error."""


class GateSpotReadOnlyClient:
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
        self.base_path = urlparse(self.base_url).path.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "crypto-trade-reviewer/1.0",
            }
        )

    def _handle_response(self, response: requests.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise GateAPIError(f"Gate.io returned non-JSON response with HTTP {response.status_code}.") from exc

        if response.ok:
            return payload

        if isinstance(payload, dict):
            label = payload.get("label", "unknown")
            message = payload.get("message", "Unknown Gate.io error")
            raise GateAPIError(f"HTTP {response.status_code}, Gate label {label}: {message}")

        raise GateAPIError(f"HTTP {response.status_code}: {payload!r}")

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
        body_hash = hashlib.sha512(b"").hexdigest()
        timestamp = str(int(time.time()))
        request_path = f"{self.base_path}{path}"
        sign_payload = "\n".join(["GET", request_path, query_string, body_hash, timestamp])
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        headers = {
            "KEY": self.api_key,
            "Timestamp": timestamp,
            "SIGN": signature,
        }
        url = f"{self.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        return self._handle_response(response)

    def get_currency_pairs(self) -> list[dict[str, Any]]:
        return self._public_get("/spot/currency_pairs")

    def get_my_trades(
        self,
        *,
        currency_pair: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        page: int = 1,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._signed_get(
            "/spot/my_trades",
            {
                "currency_pair": currency_pair,
                "from": from_ts,
                "to": to_ts,
                "page": page,
                "limit": limit,
            },
        )
