from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots

from src.analytics import (
    TIME_BUCKETS,
    beijing_date_bounds,
    build_cumulative_position_series,
    build_trade_scatter_frame,
)
from src.binance_client import BinanceSpotReadOnlyClient
from src.bitget_client import BitgetSpotReadOnlyClient
from src.exchange_importers import (
    fetch_binance_fills,
    fetch_bitget_fills,
    fetch_gate_fills,
    fetch_okx_fills,
)
from src.exchange_types import ExchangeAPIError
from src.gate_client import GateSpotReadOnlyClient
from src.market_utils import (
    filter_fills_by_market,
    list_market_keys,
    market_key_to_binance_symbol,
    split_market_key,
)
from src.okx_client import OKXSpotReadOnlyClient
from src.storage import TradeRepository


load_dotenv()

st.set_page_config(
    page_title="成交复盘",
    page_icon="📊",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / ".data" / "trades.sqlite3"
BUY_COLOR = "#0f766e"
SELL_COLOR = "#c2410c"
NEUTRAL_COLOR = "#7c3aed"
INK = "#102a43"

BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
OKX_BASE_URL = os.getenv("OKX_BASE_URL", "https://www.okx.com")
BITGET_BASE_URL = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
GATE_BASE_URL = os.getenv("GATE_BASE_URL", "https://api.gateio.ws/api/v4")

INTERVAL_LABELS = {
    "1h": "1小时",
    "4h": "4小时",
    "1d": "1天",
    "1w": "1周",
    "1M": "1月",
    "1y": "1年",
}

IMPORT_CONFIGS = [
    {
        "id": "binance",
        "label": "Binance",
        "api_key_env": "BINANCE_API_KEY",
        "api_secret_env": "BINANCE_API_SECRET",
        "passphrase_env": "",
        "base_url_env": "BINANCE_BASE_URL",
        "default_base_url": BINANCE_BASE_URL,
        "default_account_label": "Binance Main",
        "needs_passphrase": False,
        "client_class": BinanceSpotReadOnlyClient,
        "fetch_fn": fetch_binance_fills,
    },
    {
        "id": "okx",
        "label": "OKX",
        "api_key_env": "OKX_API_KEY",
        "api_secret_env": "OKX_API_SECRET",
        "passphrase_env": "OKX_API_PASSPHRASE",
        "base_url_env": "OKX_BASE_URL",
        "default_base_url": OKX_BASE_URL,
        "default_account_label": "OKX Main",
        "needs_passphrase": True,
        "client_class": OKXSpotReadOnlyClient,
        "fetch_fn": fetch_okx_fills,
    },
    {
        "id": "bitget",
        "label": "Bitget",
        "api_key_env": "BITGET_API_KEY",
        "api_secret_env": "BITGET_API_SECRET",
        "passphrase_env": "BITGET_API_PASSPHRASE",
        "base_url_env": "BITGET_BASE_URL",
        "default_base_url": BITGET_BASE_URL,
        "default_account_label": "Bitget Main",
        "needs_passphrase": True,
        "client_class": BitgetSpotReadOnlyClient,
        "fetch_fn": fetch_bitget_fills,
    },
    {
        "id": "gate",
        "label": "Gate",
        "api_key_env": "GATE_API_KEY",
        "api_secret_env": "GATE_API_SECRET",
        "passphrase_env": "",
        "base_url_env": "GATE_BASE_URL",
        "default_base_url": GATE_BASE_URL,
        "default_account_label": "Gate Main",
        "needs_passphrase": False,
        "client_class": GateSpotReadOnlyClient,
        "fetch_fn": fetch_gate_fills,
    },
]


def get_repository() -> TradeRepository:
    return TradeRepository(DB_PATH)


def load_state() -> pd.DataFrame:
    return get_repository().load_fills()


def refresh_state() -> None:
    st.session_state["fills_df"] = load_state()


@st.cache_data(ttl=20, show_spinner=False)
def load_public_symbol_price(symbol: str, base_url: str) -> float:
    client = BinanceSpotReadOnlyClient(api_key="", api_secret="", base_url=base_url)
    payload = client.get_symbol_price(symbol)
    return float(payload["price"])


def load_live_price_status(market_key: str) -> tuple[float | None, str]:
    current_price: float | None = None
    price_fetch_error = ""
    binance_symbol = market_key_to_binance_symbol(market_key)
    live_base_url = st.session_state.get("binance_base_url", BINANCE_BASE_URL)
    try:
        current_price = load_public_symbol_price(binance_symbol, live_base_url)
    except Exception as exc:  # pragma: no cover
        price_fetch_error = str(exc)

    live_status = (
        f"{market_key} Binance 参考价 {current_price:,.4f}。"
        if current_price is not None
        else f"{market_key} 当前价暂时不可用。"
    )
    if price_fetch_error:
        live_status = f"{live_status} 获取失败原因：{price_fetch_error}"
    return current_price, live_status


def build_trade_figure(
    scatter_df: pd.DataFrame,
    position_df: pd.DataFrame,
    *,
    market_key: str,
    base_asset: str,
    price_unit: str,
    current_price: float | None = None,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.7, 0.3],
    )

    for flow_state, color, label in (
        ("净流入", BUY_COLOR, "净流入"),
        ("净流出", SELL_COLOR, "净流出"),
        ("净零", NEUTRAL_COLOR, "净零"),
    ):
        flow_df = scatter_df.loc[scatter_df["flow_state"] == flow_state]
        if flow_df.empty:
            continue

        customdata = list(
            zip(
                flow_df["bucket_text"],
                flow_df["price"],
                flow_df["price_min"],
                flow_df["price_max"],
                flow_df["buy_base_qty"],
                flow_df["sell_base_qty"],
                flow_df["net_base_qty"],
                flow_df["trade_count"],
                flow_df["exchange_summary"],
            )
        )
        fig.add_trace(
            go.Scattergl(
                x=flow_df["executed_at_plot"],
                y=flow_df["price"],
                mode="markers",
                name=label,
                marker={
                    "size": flow_df["marker_size"],
                    "color": color,
                    "opacity": 0.84,
                    "line": {"width": 0},
                },
                customdata=customdata,
                hovertemplate=(
                    "时间桶: %{customdata[0]}<br>"
                    "价格: %{customdata[1]:,.8f}<br>"
                    "价格范围: %{customdata[2]:,.8f} - %{customdata[3]:,.8f}<br>"
                    "买入总量: %{customdata[4]:.8f}<br>"
                    "卖出总量: %{customdata[5]:.8f}<br>"
                    "净变化: %{customdata[6]:.8f}<br>"
                    "合并成交数: %{customdata[7]}<br>"
                    "交易所来源: %{customdata[8]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    if not position_df.empty:
        fig.add_trace(
            go.Scatter(
                x=position_df["executed_at_plot"],
                y=position_df["cumulative_base_qty"],
                mode="lines+markers",
                name=f"累计 {base_asset}",
                line={"color": "#1d4ed8", "width": 2.2},
                marker={"size": 7, "color": "#1d4ed8"},
                customdata=list(
                    zip(
                        position_df["bucket_text"],
                        position_df["trade_count"],
                        position_df["net_base_qty"],
                        position_df["cumulative_base_qty"],
                        position_df["exchange_summary"],
                    )
                ),
                hovertemplate=(
                    "时间桶: %{customdata[0]}<br>"
                    "合并成交数: %{customdata[1]}<br>"
                    "净变化: %{customdata[2]:.8f}<br>"
                    "累计数量: %{customdata[3]:.8f}<br>"
                    "交易所来源: %{customdata[4]}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=f"{market_key} 成交主图",
        paper_bgcolor="rgba(255,255,255,0.55)",
        plot_bgcolor="rgba(255,255,255,0.55)",
        font_color=INK,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin=dict(l=20, r=20, t=68, b=20),
        height=780,
    )
    if current_price is not None:
        fig.add_hline(
            y=current_price,
            row=1,
            col=1,
            line_dash="dash",
            line_color="#111827",
            line_width=1.8,
            annotation_text=f"Binance 参考价 {current_price:,.4f}",
            annotation_position="top left",
        )
    fig.update_xaxes(showgrid=False, row=1, col=1)
    fig.update_xaxes(showgrid=False, title_text="时间（北京时间）", row=2, col=1)
    fig.update_yaxes(
        title_text=f"价格 ({price_unit})",
        gridcolor="rgba(16,42,67,0.08)",
        zeroline=False,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text=f"累计 {base_asset}",
        gridcolor="rgba(16,42,67,0.08)",
        zeroline=True,
        zerolinecolor="rgba(16,42,67,0.12)",
        row=2,
        col=1,
    )
    return fig


def render_import_tab(config: dict[str, Any]) -> None:
    key_prefix = config["id"]
    label = config["label"]
    left, right = st.columns([1.25, 1.75])

    with left:
        api_key = st.text_input(
            f"{label} API Key",
            value=os.getenv(config["api_key_env"], ""),
            type="password",
            key=f"{key_prefix}_api_key",
        )
        api_secret = st.text_input(
            f"{label} API Secret",
            value=os.getenv(config["api_secret_env"], ""),
            type="password",
            key=f"{key_prefix}_api_secret",
        )
        passphrase = ""
        if config["needs_passphrase"]:
            passphrase = st.text_input(
                f"{label} Passphrase",
                value=os.getenv(config["passphrase_env"], ""),
                type="password",
                key=f"{key_prefix}_passphrase",
            )
        base_url = st.text_input(
            "API Base URL",
            value=os.getenv(config["base_url_env"], config["default_base_url"]),
            key=f"{key_prefix}_base_url",
        )
        account_label = st.text_input(
            "账户标签",
            value=config["default_account_label"],
            key=f"{key_prefix}_account_label",
        )

    with right:
        market_pairs = st.text_area(
            "交易对",
            value="BTCUSDT ETHUSDT SOLUSDT",
            help="支持 BTCUSDT、BTC/USDT、BTC-USDT、BTC_USDT 这几种写法；多个交易对用空格、逗号或换行分隔。",
            key=f"{key_prefix}_market_pairs",
        )
        import_start_date = st.date_input(
            "开始日期",
            value=date(2017, 1, 1),
            key=f"{key_prefix}_start_date",
        )
        import_end_date = st.date_input(
            "结束日期",
            value=date.today(),
            key=f"{key_prefix}_end_date",
        )

    if st.button(f"导入 {label} 实际成交", type="primary", width="stretch", key=f"import_{key_prefix}"):
        if not api_key or not api_secret:
            st.error(f"请提供 {label} API Key 和 Secret。")
            return
        if config["needs_passphrase"] and not passphrase:
            st.error(f"请提供 {label} Passphrase。")
            return
        if not market_pairs.strip():
            st.error("请至少输入一个交易对。")
            return
        if import_start_date > import_end_date:
            st.error("开始日期不能晚于结束日期。")
            return

        try:
            client_kwargs = {
                "api_key": api_key,
                "api_secret": api_secret,
                "base_url": base_url,
            }
            if config["needs_passphrase"]:
                client_kwargs["passphrase"] = passphrase
            client = config["client_class"](**client_kwargs)
            start_ms, end_ms = beijing_date_bounds(import_start_date, import_end_date)
            progress_bar = st.progress(0, text=f"准备抓取 {label} 实际成交")

            def progress(current: int, total: int, message: str) -> None:
                progress_bar.progress(int(100 * current / max(total, 1)), text=message)

            imported_fills, unresolved, notices = config["fetch_fn"](
                client,
                account_label=account_label.strip() or config["default_account_label"],
                manual_symbols=market_pairs,
                start_ms=start_ms,
                end_ms=end_ms,
                progress=progress,
            )
            progress_bar.empty()

            inserted, skipped = get_repository().upsert_fills(imported_fills)
            refresh_state()

            session_notices = list(notices)
            if unresolved:
                session_notices.append(f"这些交易对未识别：{', '.join(unresolved)}")

            st.session_state["flash_message"] = f"{label} 导入完成：新增 {inserted} 条，重复跳过 {skipped} 条。"
            st.session_state["flash_notices"] = session_notices
            st.rerun()
        except ExchangeAPIError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover
            st.exception(exc)


st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
      background:
        radial-gradient(circle at 10% 8%, rgba(15, 118, 110, 0.13), transparent 24%),
        radial-gradient(circle at 90% 4%, rgba(194, 65, 12, 0.12), transparent 22%),
        linear-gradient(180deg, #f8f2e8 0%, #f1e8d6 100%);
    }
    .block-container {
      padding-top: 2rem;
      padding-bottom: 2rem;
    }
    .page-title {
      color: #0b2239;
      font-size: 2.2rem;
      line-height: 1.0;
      margin-bottom: 1rem;
      letter-spacing: -0.03em;
      font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="page-title">成交复盘</div>', unsafe_allow_html=True)


if "fills_df" not in st.session_state:
    st.session_state["fills_df"] = load_state()
if "flash_message" not in st.session_state:
    st.session_state["flash_message"] = ""
if "flash_notices" not in st.session_state:
    st.session_state["flash_notices"] = []


fills_df = st.session_state["fills_df"]

with st.expander("交易所 API 导入", expanded=fills_df.empty):
    tabs = st.tabs([config["label"] for config in IMPORT_CONFIGS])
    for tab, config in zip(tabs, IMPORT_CONFIGS):
        with tab:
            render_import_tab(config)


flash_message = st.session_state.get("flash_message", "")
if flash_message:
    st.success(flash_message)
    st.session_state["flash_message"] = ""

flash_notices = st.session_state.get("flash_notices", [])
if flash_notices:
    for notice in flash_notices:
        st.warning(notice)
    st.session_state["flash_notices"] = []


if fills_df.empty:
    st.info("当前还没有实际成交数据。先在上方导入至少一个市场的历史成交。")
else:
    market_keys = list_market_keys(fills_df)
    selected_market_default = st.session_state.get("selected_market", market_keys[0])
    selected_market_index = market_keys.index(selected_market_default) if selected_market_default in market_keys else 0

    controls_left, controls_right = st.columns([1.5, 1.2])
    with controls_left:
        selected_market = st.selectbox(
            "市场",
            options=market_keys,
            index=selected_market_index,
            key="selected_market",
        )
    with controls_right:
        selected_interval = st.select_slider(
            "时间粒度",
            options=list(TIME_BUCKETS),
            value="1d",
            format_func=lambda value: INTERVAL_LABELS[value],
        )

    market_fills = filter_fills_by_market(fills_df, selected_market)
    if market_fills.empty:
        st.warning("当前市场还没有实际成交。")
    else:
        base_asset, quote_asset = split_market_key(selected_market)

        st.caption(
            f"这张图会把所有交易所里 `{selected_market}` 的真实成交混在一起。"
            f"上面的散点按 {INTERVAL_LABELS[selected_interval]} 聚成净流向点，下面的折线显示 `{base_asset}` 的累计数量变化。"
        )

        scatter_df = build_trade_scatter_frame(market_fills, interval=selected_interval)
        position_df = build_cumulative_position_series(market_fills, interval=selected_interval)

        @st.fragment(run_every="30s")
        def render_live_chart() -> None:
            current_price, live_status = load_live_price_status(selected_market)
            st.caption(f"当前价格线优先使用 Binance 现货参考价，每 30 秒自动更新一次。{live_status}")
            fig = build_trade_figure(
                scatter_df,
                position_df,
                market_key=selected_market,
                base_asset=base_asset,
                price_unit=quote_asset,
                current_price=current_price,
            )
            st.plotly_chart(
                fig,
                width="stretch",
                key=f"trade-chart-{selected_market}-{selected_interval}",
            )

        render_live_chart()
