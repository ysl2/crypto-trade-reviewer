from datetime import date

import pandas as pd

from src.analytics import (
    build_cumulative_position_series,
    build_trade_scatter_frame,
    display_timezone_name,
    local_date_bounds,
)
from src.exchange_importers import (
    _normalize_bitget_fill,
    _normalize_gate_trade,
    _normalize_okx_fill,
)
from src.exchange_types import SymbolMeta
from src.market_utils import (
    filter_fills_by_market,
    list_market_keys,
    market_key_to_binance_symbol,
    match_symbol_metas,
)


def sample_fills() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "uid": "b1",
                "source_type": "binance_api",
                "source_name": "Binance API",
                "exchange": "binance",
                "account_label": "binance-main",
                "symbol": "BTCUSDT",
                "order_id": "10",
                "trade_id": "100",
                "side": "BUY",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.10,
                "price": 60000.0,
                "quote_qty": 6000.0,
                "fee_amount": 2.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_696_800_000,
                "notes": "",
            },
            {
                "uid": "o1",
                "source_type": "okx_api",
                "source_name": "OKX API",
                "exchange": "okx",
                "account_label": "okx-main",
                "symbol": "BTC-USDT",
                "order_id": "11",
                "trade_id": "101",
                "side": "SELL",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.05,
                "price": 61000.0,
                "quote_qty": 3050.0,
                "fee_amount": 1.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_700_400_000,
                "notes": "",
            },
            {
                "uid": "g1",
                "source_type": "gate_api",
                "source_name": "Gate API",
                "exchange": "gate",
                "account_label": "gate-main",
                "symbol": "BTC_USDT",
                "order_id": "12",
                "trade_id": "102",
                "side": "SELL",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.20,
                "price": 62000.0,
                "quote_qty": 12400.0,
                "fee_amount": 2.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_783_200_000,
                "notes": "",
            },
            {
                "uid": "bg1",
                "source_type": "bitget_api",
                "source_name": "Bitget API",
                "exchange": "bitget",
                "account_label": "bitget-main",
                "symbol": "BTCUSDT",
                "order_id": "13",
                "trade_id": "103",
                "side": "BUY",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.10,
                "price": 63000.0,
                "quote_qty": 6300.0,
                "fee_amount": 1.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_786_800_000,
                "notes": "",
            },
            {
                "uid": "e1",
                "source_type": "binance_api",
                "source_name": "Binance API",
                "exchange": "binance",
                "account_label": "binance-main",
                "symbol": "ETHUSDT",
                "order_id": "14",
                "trade_id": "104",
                "side": "BUY",
                "base_asset": "ETH",
                "quote_asset": "USDT",
                "base_qty": 1.20,
                "price": 3000.0,
                "quote_qty": 3600.0,
                "fee_amount": 1.5,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_869_600_000,
                "notes": "",
            },
        ]
    )


def test_local_date_bounds_uses_requested_timezone() -> None:
    start_ms, end_ms = local_date_bounds(date(2025, 1, 1), date(2025, 1, 2), timezone_name="Asia/Shanghai")
    assert start_ms < end_ms
    assert end_ms - start_ms == 172_799_999

    new_york_start_ms, _ = local_date_bounds(date(2025, 1, 1), date(2025, 1, 2), timezone_name="America/New_York")
    assert new_york_start_ms != start_ms


def test_display_timezone_name_uses_effective_timezone() -> None:
    assert display_timezone_name("Asia/Shanghai") == "Asia/Shanghai"
    assert display_timezone_name(None) == "UTC"
    assert display_timezone_name("Not/A_Real_Timezone") == "UTC"


def test_list_market_keys_returns_normalized_pairs() -> None:
    assert list_market_keys(sample_fills()) == ["BTC/USDT", "ETH/USDT"]


def test_filter_fills_by_market_mixes_multiple_exchanges() -> None:
    filtered = filter_fills_by_market(sample_fills(), "BTC/USDT")

    assert len(filtered) == 4
    assert sorted(filtered["exchange"].unique().tolist()) == ["binance", "bitget", "gate", "okx"]


def test_match_symbol_metas_accepts_multiple_symbol_formats() -> None:
    metas = [
        SymbolMeta(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT", status="TRADING"),
        SymbolMeta(symbol="ETH-USDT", base_asset="ETH", quote_asset="USDT", status="live"),
        SymbolMeta(symbol="SOL_USDT", base_asset="SOL", quote_asset="USDT", status="tradable"),
    ]

    selected, unresolved = match_symbol_metas(metas, "BTC/USDT ETHUSDT SOL-USDT DOGEUSDT")

    assert [meta.symbol for meta in selected] == ["BTCUSDT", "ETH-USDT", "SOL_USDT"]
    assert unresolved == ["DOGEUSDT"]


def test_market_key_to_binance_symbol() -> None:
    assert market_key_to_binance_symbol("BTC/USDT") == "BTCUSDT"


def test_build_trade_scatter_frame_groups_net_flows_and_exchange_summary() -> None:
    fills_df = filter_fills_by_market(sample_fills(), "BTC/USDT")

    frame = build_trade_scatter_frame(fills_df, interval="1d", timezone_name="Asia/Shanghai")

    assert len(frame) == 2
    inflow_row = frame.loc[frame["flow_state"] == "净流入"].iloc[0]
    outflow_row = frame.loc[frame["flow_state"] == "净流出"].iloc[0]
    assert inflow_row["trade_count"] == 2
    assert round(inflow_row["buy_base_qty"], 8) == 0.10
    assert round(inflow_row["sell_base_qty"], 8) == 0.05
    assert round(inflow_row["net_base_qty"], 8) == 0.05
    assert inflow_row["exchange_summary"] == "binance: 1, okx: 1"
    assert outflow_row["trade_count"] == 2
    assert round(outflow_row["buy_base_qty"], 8) == 0.10
    assert round(outflow_row["sell_base_qty"], 8) == 0.20
    assert round(outflow_row["net_base_qty"], 8) == -0.10
    assert outflow_row["exchange_summary"] == "bitget: 1, gate: 1"
    assert outflow_row["marker_size"] > inflow_row["marker_size"]


def test_build_trade_scatter_frame_supports_hour_buckets() -> None:
    fills_df = filter_fills_by_market(sample_fills(), "BTC/USDT")

    one_hour_frame = build_trade_scatter_frame(fills_df, interval="1h", timezone_name="Asia/Shanghai")
    four_hour_frame = build_trade_scatter_frame(fills_df, interval="4h", timezone_name="Asia/Shanghai")
    one_year_frame = build_trade_scatter_frame(fills_df, interval="1y", timezone_name="Asia/Shanghai")

    assert len(one_hour_frame) == 4
    assert len(four_hour_frame) == 2
    assert len(one_year_frame) == 1


def test_build_trade_scatter_frame_respects_browser_timezone_for_day_buckets() -> None:
    fills_df = pd.DataFrame(
        [
            {
                "uid": "a",
                "source_type": "binance_api",
                "source_name": "Binance API",
                "exchange": "binance",
                "account_label": "main",
                "symbol": "BTCUSDT",
                "order_id": "1",
                "trade_id": "1",
                "side": "BUY",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.01,
                "price": 60000.0,
                "quote_qty": 600.0,
                "fee_amount": 0.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_743_600_000,  # 2025-01-01 15:00 UTC
                "notes": "",
            },
            {
                "uid": "b",
                "source_type": "binance_api",
                "source_name": "Binance API",
                "exchange": "binance",
                "account_label": "main",
                "symbol": "BTCUSDT",
                "order_id": "2",
                "trade_id": "2",
                "side": "BUY",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.01,
                "price": 61000.0,
                "quote_qty": 610.0,
                "fee_amount": 0.0,
                "fee_asset": "USDT",
                "executed_at_ms": 1_735_747_200_000,  # 2025-01-01 16:00 UTC
                "notes": "",
            },
        ]
    )

    shanghai_frame = build_trade_scatter_frame(fills_df, interval="1d", timezone_name="Asia/Shanghai")
    new_york_frame = build_trade_scatter_frame(fills_df, interval="1d", timezone_name="America/New_York")

    assert len(shanghai_frame) == 2
    assert len(new_york_frame) == 1


def test_build_cumulative_position_series_supports_year_buckets() -> None:
    fills_df = filter_fills_by_market(sample_fills(), "BTC/USDT")

    series = build_cumulative_position_series(fills_df, interval="1y", timezone_name="Asia/Shanghai")

    assert len(series) == 1
    assert list(series["trade_count"]) == [4]
    assert [round(value, 8) for value in series["net_base_qty"]] == [-0.05]
    assert [round(value, 8) for value in series["cumulative_base_qty"]] == [-0.05]


def test_build_cumulative_position_series_tracks_running_base_qty() -> None:
    fills_df = filter_fills_by_market(sample_fills(), "BTC/USDT")

    series = build_cumulative_position_series(fills_df, interval="1d", timezone_name="Asia/Shanghai")

    assert list(series["trade_count"]) == [2, 2]
    assert [round(value, 8) for value in series["net_base_qty"]] == [0.05, -0.10]
    assert [round(value, 8) for value in series["cumulative_base_qty"]] == [0.05, -0.05]
    assert list(series["exchange_summary"]) == ["binance: 1, okx: 1", "bitget: 1, gate: 1"]


def test_build_cumulative_position_series_accounts_for_base_asset_fees() -> None:
    fills_df = pd.DataFrame(
        [
            {
                "uid": "a",
                "source_type": "binance_api",
                "source_name": "Binance API",
                "exchange": "binance",
                "account_label": "main",
                "symbol": "BTCUSDT",
                "order_id": "10",
                "trade_id": "100",
                "side": "BUY",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 1.00,
                "price": 60000.0,
                "quote_qty": 60000.0,
                "fee_amount": 0.01,
                "fee_asset": "BTC",
                "executed_at_ms": 1_735_696_800_000,
                "notes": "",
            },
            {
                "uid": "b",
                "source_type": "okx_api",
                "source_name": "OKX API",
                "exchange": "okx",
                "account_label": "main",
                "symbol": "BTC-USDT",
                "order_id": "11",
                "trade_id": "101",
                "side": "SELL",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "base_qty": 0.40,
                "price": 61000.0,
                "quote_qty": 24400.0,
                "fee_amount": 0.01,
                "fee_asset": "BTC",
                "executed_at_ms": 1_735_783_200_000,
                "notes": "",
            },
        ]
    )

    series = build_cumulative_position_series(fills_df, interval="1d", timezone_name="Asia/Shanghai")

    assert [round(value, 8) for value in series["net_base_qty"]] == [0.99, -0.41]
    assert [round(value, 8) for value in series["cumulative_base_qty"]] == [0.99, 0.58]


def test_normalize_okx_fill() -> None:
    meta = SymbolMeta(symbol="BTC-USDT", base_asset="BTC", quote_asset="USDT", status="live")
    fill = {
        "billId": "2001",
        "tradeId": "1001",
        "ordId": "3001",
        "side": "buy",
        "fillSz": "0.01",
        "fillPx": "65000",
        "fee": "-0.15",
        "feeCcy": "USDT",
        "fillTime": "1735696800000",
    }

    record = _normalize_okx_fill(meta, fill, account_label="okx-main")

    assert record["exchange"] == "okx"
    assert record["base_qty"] == 0.01
    assert record["quote_qty"] == 650.0
    assert record["fee_amount"] == 0.15
    assert record["fee_asset"] == "USDT"


def test_normalize_bitget_fill() -> None:
    meta = SymbolMeta(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT", status="online")
    fill = {
        "tradeId": "4001",
        "orderId": "5001",
        "side": "sell",
        "size": "0.02",
        "amount": "1320",
        "priceAvg": "66000",
        "feeDetail": {"feeCoin": "USDT", "totalFee": "-0.2"},
        "cTime": "1735696800000",
    }

    record = _normalize_bitget_fill(meta, fill, account_label="bitget-main")

    assert record["exchange"] == "bitget"
    assert record["base_qty"] == 0.02
    assert record["quote_qty"] == 1320.0
    assert record["price"] == 66000.0
    assert record["fee_amount"] == 0.2
    assert record["fee_asset"] == "USDT"


def test_normalize_gate_trade() -> None:
    meta = SymbolMeta(symbol="BTC_USDT", base_asset="BTC", quote_asset="USDT", status="tradable")
    trade = {
        "id": "6001",
        "order_id": "7001",
        "side": "buy",
        "amount": "0.03",
        "price": "67000",
        "deal": "2010",
        "fee": "0.3",
        "fee_currency": "USDT",
        "create_time_ms": "1735696800000.123",
    }

    record = _normalize_gate_trade(meta, trade, account_label="gate-main")

    assert record["exchange"] == "gate"
    assert record["base_qty"] == 0.03
    assert record["quote_qty"] == 2010.0
    assert record["price"] == 67000.0
    assert record["fee_amount"] == 0.3
    assert record["fee_asset"] == "USDT"
