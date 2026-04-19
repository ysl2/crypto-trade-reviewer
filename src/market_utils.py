from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from src.exchange_types import SymbolMeta


def build_market_key(base_asset: str, quote_asset: str) -> str:
    return f"{str(base_asset).upper()}/{str(quote_asset).upper()}"


def normalize_lookup_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def parse_manual_symbols(value: str) -> list[str]:
    return [token for token in re.split(r"[\s,;]+", value.upper().strip()) if token]


def match_symbol_metas(
    metas: Iterable[SymbolMeta],
    manual_symbols: str,
) -> tuple[list[SymbolMeta], list[str]]:
    items = list(metas)
    token_index: dict[str, SymbolMeta] = {}

    for meta in items:
        aliases = {
            normalize_lookup_key(meta.symbol),
            normalize_lookup_key(build_market_key(meta.base_asset, meta.quote_asset)),
            normalize_lookup_key(f"{meta.base_asset}{meta.quote_asset}"),
        }
        for alias in aliases:
            token_index[alias] = meta

    selected: list[SymbolMeta] = []
    unresolved: list[str] = []
    for token in parse_manual_symbols(manual_symbols):
        meta = token_index.get(normalize_lookup_key(token))
        if meta is None:
            unresolved.append(token)
            continue
        selected.append(meta)

    deduped: dict[str, SymbolMeta] = {}
    for meta in selected:
        deduped[meta.symbol] = meta
    return list(deduped.values()), unresolved


def list_market_keys(fills_df: pd.DataFrame) -> list[str]:
    if fills_df.empty:
        return []
    market_frame = (
        fills_df.loc[:, ["base_asset", "quote_asset"]]
        .dropna()
        .astype(str)
        .assign(
            market_key=lambda frame: frame.apply(
                lambda row: build_market_key(row["base_asset"], row["quote_asset"]),
                axis=1,
            )
        )
    )
    return sorted(market_frame["market_key"].unique().tolist())


def split_market_key(market_key: str) -> tuple[str, str]:
    if "/" not in market_key:
        raise ValueError(f"Invalid market key: {market_key}")
    base_asset, quote_asset = market_key.split("/", 1)
    return base_asset.upper(), quote_asset.upper()


def filter_fills_by_market(fills_df: pd.DataFrame, market_key: str) -> pd.DataFrame:
    if fills_df.empty:
        return fills_df.copy()
    base_asset, quote_asset = split_market_key(market_key)
    mask = (
        fills_df["base_asset"].fillna("").astype(str).str.upper().eq(base_asset)
        & fills_df["quote_asset"].fillna("").astype(str).str.upper().eq(quote_asset)
    )
    return fills_df.loc[mask].copy()


def market_key_to_binance_symbol(market_key: str) -> str:
    base_asset, quote_asset = split_market_key(market_key)
    return f"{base_asset}{quote_asset}"
