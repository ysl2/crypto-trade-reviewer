from __future__ import annotations

import json
import time
from collections.abc import Callable

import pandas as pd

from src.analytics import STANDARD_COLUMNS
from src.binance_client import BinanceSpotReadOnlyClient
from src.bitget_client import BitgetSpotReadOnlyClient
from src.exchange_types import SymbolMeta
from src.gate_client import GateSpotReadOnlyClient
from src.market_utils import match_symbol_metas
from src.okx_client import OKXSpotReadOnlyClient


ProgressFn = Callable[[int, int, str], None]
Notice = dict[str, object]
NINETY_DAYS_MS = 90 * 24 * 60 * 60 * 1000
THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000


def _empty_fills_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=STANDARD_COLUMNS)


def _records_to_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return _empty_fills_frame()
    fills_df = pd.DataFrame(records)
    fills_df = fills_df.sort_values(["executed_at_ms", "trade_id"]).reset_index(drop=True)
    return fills_df[STANDARD_COLUMNS]


def _safe_float(value: object, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_ms(value: object) -> int:
    raw = _safe_float(value, 0.0)
    if raw <= 0:
        return 0
    if raw < 100_000_000_000:
        return int(raw * 1000)
    return int(raw)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _apply_retention_limit(
    start_ms: int,
    end_ms: int | None,
    *,
    retention_ms: int,
    label: str,
) -> tuple[int, int | None, list[Notice]]:
    notices: list[Notice] = []
    cutoff = _now_ms() - retention_ms
    effective_start = max(start_ms, cutoff)
    if effective_start > start_ms:
        notices.append(
            {
                "kind": "retention_limit",
                "exchange_label": label,
                "days": retention_ms // 86_400_000,
            }
        )
    return effective_start, end_ms, notices


def _binance_symbol_metas(exchange_info: dict) -> list[SymbolMeta]:
    return [
        SymbolMeta(
            symbol=item["symbol"],
            base_asset=item["baseAsset"],
            quote_asset=item["quoteAsset"],
            status=str(item.get("status", "")),
            permissions=tuple(item.get("permissions", [])),
        )
        for item in exchange_info.get("symbols", [])
    ]


def _okx_symbol_metas(items: list[dict]) -> list[SymbolMeta]:
    metas: list[SymbolMeta] = []
    for item in items:
        inst_id = str(item.get("instId", "")).upper()
        base_asset = str(item.get("baseCcy", "")).upper()
        quote_asset = str(item.get("quoteCcy", "")).upper()
        if (not base_asset or not quote_asset) and "-" in inst_id:
            base_asset, quote_asset = inst_id.split("-", 1)
        if not inst_id or not base_asset or not quote_asset:
            continue
        metas.append(
            SymbolMeta(
                symbol=inst_id,
                base_asset=base_asset,
                quote_asset=quote_asset,
                status=str(item.get("state", "")),
            )
        )
    return metas


def _bitget_symbol_metas(items: list[dict]) -> list[SymbolMeta]:
    metas: list[SymbolMeta] = []
    for item in items:
        symbol = str(item.get("symbol", "")).upper()
        base_asset = str(item.get("baseCoin", "")).upper()
        quote_asset = str(item.get("quoteCoin", "")).upper()
        if not symbol or not base_asset or not quote_asset:
            continue
        metas.append(
            SymbolMeta(
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                status=str(item.get("status") or item.get("symbolStatus") or ""),
            )
        )
    return metas


def _gate_symbol_metas(items: list[dict]) -> list[SymbolMeta]:
    metas: list[SymbolMeta] = []
    for item in items:
        symbol = str(item.get("id", "")).upper()
        base_asset = str(item.get("base", "")).upper()
        quote_asset = str(item.get("quote", "")).upper()
        if not symbol or not base_asset or not quote_asset:
            continue
        metas.append(
            SymbolMeta(
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                status=str(item.get("trade_status", "")),
            )
        )
    return metas


def _normalize_binance_trade(meta: SymbolMeta, trade: dict, *, account_label: str) -> dict:
    trade_id = int(trade["id"])
    order_id = int(trade["orderId"])
    executed_at_ms = int(trade["time"])
    uid = f"binance_api::{account_label}::{meta.symbol}::{trade_id}"
    return {
        "uid": uid,
        "source_type": "binance_api",
        "source_name": "Binance API",
        "exchange": "binance",
        "account_label": account_label,
        "symbol": meta.symbol,
        "order_id": str(order_id),
        "trade_id": str(trade_id),
        "side": "BUY" if trade.get("isBuyer") else "SELL",
        "base_asset": meta.base_asset,
        "quote_asset": meta.quote_asset,
        "base_qty": _safe_float(trade.get("qty")),
        "price": _safe_float(trade.get("price")),
        "quote_qty": _safe_float(trade.get("quoteQty")),
        "fee_amount": abs(_safe_float(trade.get("commission"))),
        "fee_asset": str(trade.get("commissionAsset", "") or "").upper(),
        "executed_at_ms": executed_at_ms,
        "notes": "",
    }


def _normalize_okx_fill(meta: SymbolMeta, fill: dict, *, account_label: str) -> dict:
    trade_id = str(fill.get("tradeId") or fill.get("billId") or "")
    bill_id = str(fill.get("billId") or trade_id)
    side = str(fill.get("side", "")).upper()
    base_qty = _safe_float(fill.get("fillSz"))
    price = _safe_float(fill.get("fillPx"))
    quote_qty = base_qty * price
    fee_amount = abs(_safe_float(fill.get("fee")))
    fee_asset = str(fill.get("feeCcy", "") or "").upper()
    return {
        "uid": f"okx_api::{account_label}::{meta.symbol}::{bill_id}",
        "source_type": "okx_api",
        "source_name": "OKX API",
        "exchange": "okx",
        "account_label": account_label,
        "symbol": meta.symbol,
        "order_id": str(fill.get("ordId", "") or ""),
        "trade_id": trade_id or bill_id,
        "side": side,
        "base_asset": meta.base_asset,
        "quote_asset": meta.quote_asset,
        "base_qty": base_qty,
        "price": price,
        "quote_qty": quote_qty,
        "fee_amount": fee_amount,
        "fee_asset": fee_asset,
        "executed_at_ms": _parse_ms(fill.get("fillTime") or fill.get("ts")),
        "notes": "",
    }


def _extract_bitget_fee(fee_detail: object) -> tuple[float, str]:
    payload = fee_detail
    if isinstance(payload, str):
        payload = payload.strip()
        if payload.startswith("{") or payload.startswith("["):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        payload = {}
    return abs(_safe_float(payload.get("totalFee"))), str(payload.get("feeCoin", "") or "").upper()


def _normalize_bitget_fill(meta: SymbolMeta, fill: dict, *, account_label: str) -> dict:
    fee_amount, fee_asset = _extract_bitget_fee(fill.get("feeDetail"))
    base_qty = _safe_float(fill.get("size"))
    quote_qty = _safe_float(fill.get("amount"))
    price = _safe_float(fill.get("priceAvg")) or (_safe_float(fill.get("price")) or (quote_qty / base_qty if base_qty else 0.0))
    executed_at_ms = _parse_ms(fill.get("uTime") or fill.get("cTime"))
    trade_id = str(fill.get("tradeId") or fill.get("fillId") or "")
    return {
        "uid": f"bitget_api::{account_label}::{meta.symbol}::{trade_id}",
        "source_type": "bitget_api",
        "source_name": "Bitget API",
        "exchange": "bitget",
        "account_label": account_label,
        "symbol": meta.symbol,
        "order_id": str(fill.get("orderId", "") or ""),
        "trade_id": trade_id,
        "side": str(fill.get("side", "")).upper(),
        "base_asset": meta.base_asset,
        "quote_asset": meta.quote_asset,
        "base_qty": base_qty,
        "price": price,
        "quote_qty": quote_qty or (base_qty * price),
        "fee_amount": fee_amount,
        "fee_asset": fee_asset,
        "executed_at_ms": executed_at_ms,
        "notes": "",
    }


def _normalize_gate_trade(meta: SymbolMeta, trade: dict, *, account_label: str) -> dict:
    base_qty = _safe_float(trade.get("amount"))
    price = _safe_float(trade.get("price"))
    quote_qty = _safe_float(trade.get("deal")) or (base_qty * price)
    trade_id = str(trade.get("id", "") or "")
    return {
        "uid": f"gate_api::{account_label}::{meta.symbol}::{trade_id}",
        "source_type": "gate_api",
        "source_name": "Gate API",
        "exchange": "gate",
        "account_label": account_label,
        "symbol": meta.symbol,
        "order_id": str(trade.get("order_id", "") or ""),
        "trade_id": trade_id,
        "side": str(trade.get("side", "")).upper(),
        "base_asset": meta.base_asset,
        "quote_asset": meta.quote_asset,
        "base_qty": base_qty,
        "price": price,
        "quote_qty": quote_qty,
        "fee_amount": abs(_safe_float(trade.get("fee"))),
        "fee_asset": str(trade.get("fee_currency", "") or "").upper(),
        "executed_at_ms": _parse_ms(trade.get("create_time_ms") or trade.get("create_time")),
        "notes": "",
    }


def fetch_binance_fills(
    client: BinanceSpotReadOnlyClient,
    *,
    account_label: str,
    manual_symbols: str,
    start_ms: int,
    end_ms: int | None,
    progress: ProgressFn | None = None,
) -> tuple[pd.DataFrame, list[str], list[Notice]]:
    metas = _binance_symbol_metas(client.get_exchange_info())
    selected, unresolved = match_symbol_metas(metas, manual_symbols)
    records: list[dict] = []
    total = len(selected)
    effective_end = end_ms if end_ms is not None else _now_ms()

    for index, meta in enumerate(selected, start=1):
        if progress:
            progress(index, total, f"抓取 Binance 成交 {meta.symbol} ({index}/{total})")
        seen_trade_ids: set[int] = set()
        cursor_end = effective_end

        while True:
            page = client.get_account_trades(meta.symbol, limit=1000, end_time=cursor_end)

            if not page:
                break

            ordered_page = sorted(page, key=lambda item: (int(item["time"]), int(item["id"])))
            for trade in ordered_page:
                trade_id = int(trade["id"])
                if trade_id in seen_trade_ids:
                    continue
                seen_trade_ids.add(trade_id)
                trade_time = int(trade["time"])
                if trade_time < start_ms or trade_time > effective_end:
                    continue
                records.append(_normalize_binance_trade(meta, trade, account_label=account_label))

            if len(ordered_page) < 1000:
                break
            earliest_trade_time = int(ordered_page[0]["time"])
            if earliest_trade_time <= start_ms:
                break
            next_cursor_end = earliest_trade_time - 1
            if next_cursor_end >= cursor_end:
                break
            cursor_end = next_cursor_end

    return _records_to_frame(records), unresolved, []


def fetch_okx_fills(
    client: OKXSpotReadOnlyClient,
    *,
    account_label: str,
    manual_symbols: str,
    start_ms: int,
    end_ms: int | None,
    progress: ProgressFn | None = None,
) -> tuple[pd.DataFrame, list[str], list[Notice]]:
    effective_start, effective_end, notices = _apply_retention_limit(
        start_ms,
        end_ms,
        retention_ms=NINETY_DAYS_MS,
        label="OKX",
    )
    metas = _okx_symbol_metas(client.get_instruments("SPOT"))
    selected, unresolved = match_symbol_metas(metas, manual_symbols)
    records: list[dict] = []
    total = len(selected)

    for index, meta in enumerate(selected, start=1):
        if progress:
            progress(index, total, f"抓取 OKX 成交 {meta.symbol} ({index}/{total})")
        seen_bill_ids: set[str] = set()
        after: str | None = None

        while True:
            page = client.get_fills_history(
                inst_type="SPOT",
                inst_id=meta.symbol,
                begin=effective_start,
                end=effective_end,
                after=after,
                limit=100,
            )
            if not page:
                break

            for fill in page:
                bill_id = str(fill.get("billId") or fill.get("tradeId") or "")
                if bill_id and bill_id in seen_bill_ids:
                    continue
                if bill_id:
                    seen_bill_ids.add(bill_id)
                executed_at_ms = _parse_ms(fill.get("fillTime") or fill.get("ts"))
                if executed_at_ms < effective_start or (effective_end is not None and executed_at_ms > effective_end):
                    continue
                records.append(_normalize_okx_fill(meta, fill, account_label=account_label))

            if len(page) < 100:
                break
            last_after = str(page[-1].get("billId") or "")
            if not last_after or last_after == after:
                break
            after = last_after

    return _records_to_frame(records), unresolved, notices


def fetch_bitget_fills(
    client: BitgetSpotReadOnlyClient,
    *,
    account_label: str,
    manual_symbols: str,
    start_ms: int,
    end_ms: int | None,
    progress: ProgressFn | None = None,
) -> tuple[pd.DataFrame, list[str], list[Notice]]:
    effective_start, effective_end, notices = _apply_retention_limit(
        start_ms,
        end_ms,
        retention_ms=NINETY_DAYS_MS,
        label="Bitget",
    )
    metas = _bitget_symbol_metas(client.get_symbols())
    selected, unresolved = match_symbol_metas(metas, manual_symbols)
    records: list[dict] = []
    total = len(selected)

    for index, meta in enumerate(selected, start=1):
        if progress:
            progress(index, total, f"抓取 Bitget 成交 {meta.symbol} ({index}/{total})")
        seen_trade_ids: set[str] = set()
        id_less_than: str | None = None

        while True:
            page = client.get_fills(
                symbol=meta.symbol,
                start_time=effective_start,
                end_time=effective_end,
                id_less_than=id_less_than,
                limit=100,
            )
            if not page:
                break

            for fill in page:
                trade_id = str(fill.get("tradeId") or fill.get("fillId") or "")
                if trade_id and trade_id in seen_trade_ids:
                    continue
                if trade_id:
                    seen_trade_ids.add(trade_id)
                executed_at_ms = _parse_ms(fill.get("uTime") or fill.get("cTime"))
                if executed_at_ms < effective_start or (effective_end is not None and executed_at_ms > effective_end):
                    continue
                records.append(_normalize_bitget_fill(meta, fill, account_label=account_label))

            if len(page) < 100:
                break
            last_id = str(page[-1].get("tradeId") or page[-1].get("fillId") or "")
            if not last_id or last_id == id_less_than:
                break
            id_less_than = last_id

    return _records_to_frame(records), unresolved, notices


def fetch_gate_fills(
    client: GateSpotReadOnlyClient,
    *,
    account_label: str,
    manual_symbols: str,
    start_ms: int,
    end_ms: int | None,
    progress: ProgressFn | None = None,
) -> tuple[pd.DataFrame, list[str], list[Notice]]:
    effective_end = end_ms if end_ms is not None else _now_ms()
    metas = _gate_symbol_metas(client.get_currency_pairs())
    selected, unresolved = match_symbol_metas(metas, manual_symbols)
    records: list[dict] = []
    total = len(selected)

    for index, meta in enumerate(selected, start=1):
        if progress:
            progress(index, total, f"抓取 Gate 成交 {meta.symbol} ({index}/{total})")
        window_start = start_ms
        seen_trade_ids: set[str] = set()

        while window_start <= effective_end:
            window_end = min(effective_end, window_start + THIRTY_DAYS_MS - 1)
            page = 1

            while True:
                batch = client.get_my_trades(
                    currency_pair=meta.symbol,
                    from_ts=window_start // 1000,
                    to_ts=window_end // 1000,
                    page=page,
                    limit=1000,
                )
                if not batch:
                    break

                for trade in batch:
                    trade_id = str(trade.get("id") or "")
                    if trade_id and trade_id in seen_trade_ids:
                        continue
                    if trade_id:
                        seen_trade_ids.add(trade_id)
                    executed_at_ms = _parse_ms(trade.get("create_time_ms") or trade.get("create_time"))
                    if executed_at_ms < start_ms or executed_at_ms > effective_end:
                        continue
                    records.append(_normalize_gate_trade(meta, trade, account_label=account_label))

                if len(batch) < 1000:
                    break
                page += 1

            window_start = window_end + 1

    return _records_to_frame(records), unresolved, []
