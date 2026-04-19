from __future__ import annotations

from dataclasses import dataclass


class ExchangeAPIError(RuntimeError):
    """Raised when an exchange returns a handled API error."""


@dataclass(frozen=True)
class SymbolMeta:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    permissions: tuple[str, ...] = ()
