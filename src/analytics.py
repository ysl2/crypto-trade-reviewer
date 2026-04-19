from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd


APP_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc

STANDARD_COLUMNS = [
    "uid",
    "source_type",
    "source_name",
    "exchange",
    "account_label",
    "symbol",
    "order_id",
    "trade_id",
    "side",
    "base_asset",
    "quote_asset",
    "base_qty",
    "price",
    "quote_qty",
    "fee_amount",
    "fee_asset",
    "executed_at_ms",
    "notes",
]

TIME_BUCKETS = ("1h", "4h", "1d", "1w", "1M", "1y")


def beijing_date_bounds(start_date: date, end_date: date) -> tuple[int, int]:
    start_dt = datetime.combine(start_date, dt_time.min, tzinfo=APP_TIMEZONE)
    end_dt = datetime.combine(end_date + timedelta(days=1), dt_time.min, tzinfo=APP_TIMEZONE)
    end_dt -= timedelta(milliseconds=1)
    return (
        int(start_dt.astimezone(UTC).timestamp() * 1000),
        int(end_dt.astimezone(UTC).timestamp() * 1000),
    )


def ms_to_local_series(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, unit="ms", utc=True).dt.tz_convert(APP_TIMEZONE)


def format_time_for_display(value: pd.Timestamp | datetime | None) -> str:
    if value is None or pd.isna(value):
        return ""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(APP_TIMEZONE)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _build_order_ref_series(fills_df: pd.DataFrame) -> pd.Series:
    return (
        fills_df["order_id"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace({"": pd.NA})
        .fillna(fills_df["trade_id"].fillna("").astype(str).replace({"": pd.NA}))
        .fillna(fills_df["uid"])
        .astype(str)
    )


def with_display_columns(fills_df: pd.DataFrame) -> pd.DataFrame:
    if fills_df.empty:
        result = fills_df.copy()
        result["order_ref"] = pd.Series(dtype="object")
        result["executed_at_local"] = pd.Series(dtype="datetime64[ns, Asia/Shanghai]")
        result["executed_at_text"] = pd.Series(dtype="object")
        result["executed_at_plot"] = pd.Series(dtype="datetime64[ns]")
        return result

    result = fills_df.copy()
    result["order_ref"] = _build_order_ref_series(result)
    result["executed_at_local"] = ms_to_local_series(result["executed_at_ms"])
    result["executed_at_text"] = result["executed_at_local"].apply(format_time_for_display)
    result["executed_at_plot"] = result["executed_at_local"].dt.tz_localize(None)
    return result


def _with_inventory_columns(fills_df: pd.DataFrame) -> pd.DataFrame:
    frame = with_display_columns(fills_df).sort_values(["executed_at_ms", "uid"]).reset_index(drop=True)
    if frame.empty:
        frame["inventory_buy_qty"] = pd.Series(dtype="float64")
        frame["inventory_sell_qty"] = pd.Series(dtype="float64")
        frame["inventory_base_delta"] = pd.Series(dtype="float64")
        return frame

    fee_in_base = (
        frame["fee_asset"].fillna("").astype(str).str.upper()
        == frame["base_asset"].fillna("").astype(str).str.upper()
    )
    fee_amount = frame["fee_amount"].fillna(0.0).astype(float).where(fee_in_base, 0.0)
    is_buy = frame["side"].fillna("").astype(str).str.upper().eq("BUY")
    base_qty = frame["base_qty"].astype(float)

    frame["inventory_buy_qty"] = 0.0
    frame.loc[is_buy, "inventory_buy_qty"] = base_qty.loc[is_buy] - fee_amount.loc[is_buy]

    frame["inventory_sell_qty"] = 0.0
    frame.loc[~is_buy, "inventory_sell_qty"] = base_qty.loc[~is_buy] + fee_amount.loc[~is_buy]

    frame["inventory_base_delta"] = frame["inventory_buy_qty"] - frame["inventory_sell_qty"]
    return frame


def _build_exchange_summary(series: pd.Series) -> str:
    if series.empty:
        return ""
    counts = series.fillna("unknown").astype(str).str.lower().value_counts().sort_index()
    return ", ".join(f"{name}: {count}" for name, count in counts.items())


def build_trade_scatter_frame(fills_df: pd.DataFrame, *, interval: str) -> pd.DataFrame:
    if fills_df.empty:
        return pd.DataFrame(
            columns=[
                "bucket_start",
                "bucket_text",
                "price",
                "price_min",
                "price_max",
                "buy_base_qty",
                "sell_base_qty",
                "net_base_qty",
                "buy_quote_qty",
                "sell_quote_qty",
                "net_quote_qty",
                "trade_count",
                "executed_at_plot",
                "flow_state",
                "marker_size",
                "exchange_summary",
            ]
        )

    frame = with_display_columns(fills_df).sort_values(["executed_at_ms", "uid"]).reset_index(drop=True)
    frame["bucket_start"] = _bucket_local_timestamps(frame["executed_at_plot"], interval)

    rows: list[dict[str, object]] = []
    grouped = frame.groupby(["bucket_start"], sort=True, dropna=False)
    for (bucket_start,), group in grouped:
        buy_group = group.loc[group["side"] == "BUY"]
        sell_group = group.loc[group["side"] == "SELL"]
        buy_base_qty = float(buy_group["base_qty"].sum())
        sell_base_qty = float(sell_group["base_qty"].sum())
        buy_quote_qty = float(buy_group["quote_qty"].sum())
        sell_quote_qty = float(sell_group["quote_qty"].sum())
        gross_base_qty = float(group["base_qty"].sum())
        gross_quote_qty = float(group["quote_qty"].sum())
        price = gross_quote_qty / gross_base_qty if gross_base_qty else 0.0
        net_base_qty = buy_base_qty - sell_base_qty
        net_quote_qty = buy_quote_qty - sell_quote_qty
        if net_base_qty > 0:
            flow_state = "净流入"
        elif net_base_qty < 0:
            flow_state = "净流出"
        else:
            flow_state = "净零"
        rows.append(
            {
                "bucket_start": bucket_start,
                "bucket_text": format_time_for_display(pd.Timestamp(bucket_start).tz_localize(APP_TIMEZONE)),
                "price": price,
                "price_min": float(group["price"].min()),
                "price_max": float(group["price"].max()),
                "buy_base_qty": buy_base_qty,
                "sell_base_qty": sell_base_qty,
                "net_base_qty": net_base_qty,
                "buy_quote_qty": buy_quote_qty,
                "sell_quote_qty": sell_quote_qty,
                "net_quote_qty": net_quote_qty,
                "trade_count": int(len(group)),
                "executed_at_plot": bucket_start,
                "flow_state": flow_state,
                "exchange_summary": _build_exchange_summary(group["exchange"]),
            }
        )

    aggregated = pd.DataFrame(rows).sort_values(["bucket_start"]).reset_index(drop=True)
    qty = aggregated["net_base_qty"].abs().astype(float)
    scaled = qty.pow(0.5)
    min_scaled = float(scaled.min())
    max_scaled = float(scaled.max())
    if max_scaled == min_scaled:
        aggregated["marker_size"] = 18.0
    else:
        aggregated["marker_size"] = 10.0 + ((scaled - min_scaled) / (max_scaled - min_scaled)) * 22.0
    return aggregated


def build_cumulative_position_series(fills_df: pd.DataFrame, *, interval: str) -> pd.DataFrame:
    if fills_df.empty:
        return pd.DataFrame(
            columns=[
                "bucket_start",
                "bucket_text",
                "executed_at_plot",
                "trade_count",
                "net_base_qty",
                "cumulative_base_qty",
                "exchange_summary",
            ]
        )

    frame = _with_inventory_columns(fills_df)
    frame["cumulative_base_qty"] = frame["inventory_base_delta"].cumsum()
    frame["bucket_start"] = _bucket_local_timestamps(frame["executed_at_plot"], interval)

    summary = (
        frame.groupby("bucket_start", as_index=False)
        .agg(
            trade_count=("uid", "count"),
            net_base_qty=("inventory_base_delta", "sum"),
            cumulative_base_qty=("cumulative_base_qty", "last"),
            exchange_summary=("exchange", _build_exchange_summary),
        )
        .sort_values("bucket_start")
        .reset_index(drop=True)
    )
    summary["bucket_text"] = summary["bucket_start"].apply(
        lambda value: format_time_for_display(pd.Timestamp(value).tz_localize(APP_TIMEZONE))
    )
    summary["executed_at_plot"] = summary["bucket_start"]
    return summary


def _bucket_local_timestamps(series: pd.Series, interval: str) -> pd.Series:
    if interval not in TIME_BUCKETS:
        raise ValueError(f"Unsupported interval: {interval}")

    local = pd.to_datetime(series)
    if getattr(local.dt, "tz", None) is not None:
        local = local.dt.tz_localize(None)

    if interval == "1h":
        return local.dt.floor("1h")
    if interval == "4h":
        return local.dt.floor("4h")
    if interval == "1d":
        return local.dt.floor("1D")
    if interval == "1w":
        return local.dt.to_period("W-MON").apply(lambda period: period.start_time)
    if interval == "1M":
        return local.dt.to_period("M").apply(lambda period: period.start_time)
    return local.dt.to_period("Y").apply(lambda period: period.start_time)
