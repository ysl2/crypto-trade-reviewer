from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from plotly.subplots import make_subplots

from src.analytics import (
    TIME_BUCKETS,
    build_cumulative_position_series,
    build_trade_scatter_frame,
    current_local_date,
    display_timezone_name,
    local_date_bounds,
)
from src.binance_client import BinanceSpotReadOnlyClient
from src.bitget_client import BitgetSpotReadOnlyClient
from src.exchange_importers import (
    Notice,
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
from src.i18n import LANGUAGE_OPTIONS, get_language_name, interval_label, resolve_ui_locale, t
from src.okx_client import OKXSpotReadOnlyClient
from src.storage import TradeRepository


load_dotenv()

st.set_page_config(
    page_title="Trade Review",
    page_icon="📊",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("TRADE_REVIEW_DB_PATH", str(PROJECT_ROOT / ".data" / "trades.sqlite3"))).expanduser()
BUY_COLOR = "#0f766e"
SELL_COLOR = "#c2410c"
NEUTRAL_COLOR = "#7c3aed"
INK = "#102a43"
DEFAULT_MARKET_PAIRS = "BTCUSDT ETHUSDT SOLUSDT"

BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
OKX_BASE_URL = os.getenv("OKX_BASE_URL", "https://www.okx.com")
BITGET_BASE_URL = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
GATE_BASE_URL = os.getenv("GATE_BASE_URL", "https://api.gateio.ws/api/v4")
FLOW_STATES = (
    ("净流入", "chart.flow.net_in", BUY_COLOR),
    ("净流出", "chart.flow.net_out", SELL_COLOR),
    ("净零", "chart.flow.net_flat", NEUTRAL_COLOR),
)

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


def build_flash_message_text(locale: str, payload: object) -> str:
    if isinstance(payload, dict) and payload.get("kind") == "import_complete":
        return t(
            locale,
            "flash.import_complete",
            exchange=payload.get("exchange_label", ""),
            inserted=payload.get("inserted", 0),
            skipped=payload.get("skipped", 0),
        )
    if isinstance(payload, str):
        return payload
    return ""


def build_notice_text(locale: str, notice: object) -> str:
    if isinstance(notice, dict):
        kind = notice.get("kind")
        if kind == "retention_limit":
            return t(
                locale,
                "notice.retention_limit",
                exchange=notice.get("exchange_label", ""),
                days=notice.get("days", 0),
            )
        if kind == "unresolved_symbols":
            symbols = notice.get("symbols", [])
            rendered_symbols = ", ".join(str(symbol) for symbol in symbols)
            return t(locale, "notice.unresolved_symbols", symbols=rendered_symbols)
    if isinstance(notice, str):
        return notice
    return ""


def get_query_param_locale() -> str | None:
    locale = st.query_params.get("lang")
    if isinstance(locale, list):
        return locale[0] if locale else None
    if isinstance(locale, str) and locale.strip():
        return locale
    return None


def sync_query_param_locale(locale: str) -> None:
    if get_query_param_locale() != locale:
        st.query_params["lang"] = locale


def sync_browser_tab_title(locale: str) -> None:
    page_title = t(locale, "app.page_title")
    escaped_title = json.dumps(page_title)
    components.html(
        f"""
        <script>
        const nextTitle = {escaped_title};
        document.title = nextTitle;
        try {{
          window.parent.document.title = nextTitle;
        }} catch (error) {{
        }}
        </script>
        """,
        height=0,
        width=0,
    )


def get_browser_timezone_name() -> str | None:
    return getattr(st.context, "timezone", None)


def get_repository() -> TradeRepository:
    return TradeRepository(DB_PATH)


def load_state() -> pd.DataFrame:
    return get_repository().load_fills()


def refresh_state() -> None:
    st.session_state["fills_df"] = load_state()


def import_form_state_key(exchange_id: str) -> str:
    return f"import_form:{exchange_id}"


def parse_saved_date(value: object, fallback: date) -> date:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return fallback
    if isinstance(value, date):
        return value
    return fallback


def initialize_import_form_state(config: dict[str, Any], *, browser_timezone_name: str | None) -> None:
    key_prefix = config["id"]
    saved_state = get_repository().load_app_state(import_form_state_key(key_prefix)) or {}
    defaults: dict[str, object] = {
        f"{key_prefix}_api_key": saved_state.get("api_key", os.getenv(config["api_key_env"], "")),
        f"{key_prefix}_api_secret": saved_state.get("api_secret", os.getenv(config["api_secret_env"], "")),
        f"{key_prefix}_passphrase": saved_state.get("passphrase", os.getenv(config["passphrase_env"], "")),
        f"{key_prefix}_base_url": saved_state.get("base_url", os.getenv(config["base_url_env"], config["default_base_url"])),
        f"{key_prefix}_account_label": saved_state.get("account_label", config["default_account_label"]),
        f"{key_prefix}_market_pairs": saved_state.get("market_pairs", DEFAULT_MARKET_PAIRS),
        f"{key_prefix}_start_date": parse_saved_date(saved_state.get("start_date"), date(2017, 1, 1)),
        f"{key_prefix}_end_date": parse_saved_date(saved_state.get("end_date"), current_local_date(browser_timezone_name)),
    }
    for state_key, value in defaults.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = value


def persist_import_form_state(config: dict[str, Any]) -> None:
    key_prefix = config["id"]
    payload = {
        "api_key": str(st.session_state.get(f"{key_prefix}_api_key", "")),
        "api_secret": str(st.session_state.get(f"{key_prefix}_api_secret", "")),
        "passphrase": str(st.session_state.get(f"{key_prefix}_passphrase", "")),
        "base_url": str(st.session_state.get(f"{key_prefix}_base_url", "")),
        "account_label": str(st.session_state.get(f"{key_prefix}_account_label", "")),
        "market_pairs": str(st.session_state.get(f"{key_prefix}_market_pairs", "")),
        "start_date": parse_saved_date(st.session_state.get(f"{key_prefix}_start_date"), date(2017, 1, 1)).isoformat(),
        "end_date": parse_saved_date(
            st.session_state.get(f"{key_prefix}_end_date"),
            current_local_date(get_browser_timezone_name()),
        ).isoformat(),
    }
    get_repository().save_app_state(import_form_state_key(key_prefix), payload)


@st.cache_data(ttl=20, show_spinner=False)
def load_public_symbol_price(symbol: str, base_url: str) -> float:
    client = BinanceSpotReadOnlyClient(api_key="", api_secret="", base_url=base_url)
    payload = client.get_symbol_price(symbol)
    return float(payload["price"])


def load_live_price_status(locale: str, market_key: str) -> tuple[float | None, str]:
    current_price: float | None = None
    price_fetch_error = ""
    binance_symbol = market_key_to_binance_symbol(market_key)
    live_base_url = st.session_state.get("binance_base_url", BINANCE_BASE_URL)
    try:
        current_price = load_public_symbol_price(binance_symbol, live_base_url)
    except Exception as exc:  # pragma: no cover
        price_fetch_error = str(exc)

    live_status = (
        t(locale, "live_price.available", market_key=market_key, current_price=current_price)
        if current_price is not None
        else t(locale, "live_price.unavailable", market_key=market_key)
    )
    if price_fetch_error:
        live_status = f"{live_status} {t(locale, 'live_price.failure_reason', message=price_fetch_error)}"
    return current_price, live_status


def get_selected_interval() -> str:
    selected_interval = str(st.session_state.get("selected_interval", "1d"))
    if selected_interval not in TIME_BUCKETS:
        return "1d"
    return selected_interval


def build_trade_figure(
    scatter_df: pd.DataFrame,
    position_df: pd.DataFrame,
    *,
    market_key: str,
    base_asset: str,
    price_unit: str,
    locale: str,
    timezone_name: str | None,
    current_price: float | None = None,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.7, 0.3],
    )

    scatter_hover_template = (
        f"{t(locale, 'chart.hover.bucket')}: "
        "%{customdata[0]}<br>"
        f"{t(locale, 'chart.hover.price')}: "
        "%{customdata[1]:,.8f}<br>"
        f"{t(locale, 'chart.hover.price_range')}: "
        "%{customdata[2]:,.8f} - %{customdata[3]:,.8f}<br>"
        f"{t(locale, 'chart.hover.buy_qty')}: "
        "%{customdata[4]:.8f}<br>"
        f"{t(locale, 'chart.hover.sell_qty')}: "
        "%{customdata[5]:.8f}<br>"
        f"{t(locale, 'chart.hover.net_change')}: "
        "%{customdata[6]:.8f}<br>"
        f"{t(locale, 'chart.hover.trade_count')}: "
        "%{customdata[7]}<br>"
        f"{t(locale, 'chart.hover.exchange_sources')}: "
        "%{customdata[8]}<extra></extra>"
    )
    position_hover_template = (
        f"{t(locale, 'chart.hover.bucket')}: "
        "%{customdata[0]}<br>"
        f"{t(locale, 'chart.hover.trade_count')}: "
        "%{customdata[1]}<br>"
        f"{t(locale, 'chart.hover.net_change')}: "
        "%{customdata[2]:.8f}<br>"
        f"{t(locale, 'chart.hover.cumulative_qty')}: "
        "%{customdata[3]:.8f}<br>"
        f"{t(locale, 'chart.hover.exchange_sources')}: "
        "%{customdata[4]}<extra></extra>"
    )

    for flow_state, label_key, color in FLOW_STATES:
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
                name=t(locale, label_key),
                marker={
                    "size": flow_df["marker_size"],
                    "color": color,
                    "opacity": 0.84,
                    "line": {"width": 0},
                },
                customdata=customdata,
                hovertemplate=scatter_hover_template,
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
                name=t(locale, "chart.position_series", base_asset=base_asset),
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
                hovertemplate=position_hover_template,
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title={
            "text": t(locale, "chart.title", market_key=market_key),
            "x": 0.0,
            "xanchor": "left",
            "font": {"size": 16},
        },
        paper_bgcolor="rgba(255,255,255,0.55)",
        plot_bgcolor="rgba(255,255,255,0.55)",
        font_color=INK,
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.06,
            "x": 0,
            "font": {"size": 11},
        },
        margin=dict(l=20, r=20, t=96, b=20),
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
            annotation_text=t(
                locale,
                "chart.current_price_line",
                market_key=market_key,
                current_price=current_price,
            ),
            annotation_position="top left",
        )
    fig.update_xaxes(showgrid=False, row=1, col=1)
    fig.update_xaxes(
        showgrid=False,
        title_text=t(locale, "chart.xaxis.time", timezone_name=display_timezone_name(timezone_name)),
        row=2,
        col=1,
    )
    fig.update_yaxes(
        title_text=t(locale, "chart.yaxis.price", price_unit=price_unit),
        gridcolor="rgba(16,42,67,0.08)",
        zeroline=False,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text=t(locale, "chart.yaxis.cumulative", base_asset=base_asset),
        gridcolor="rgba(16,42,67,0.08)",
        zeroline=True,
        zerolinecolor="rgba(16,42,67,0.12)",
        row=2,
        col=1,
    )
    return fig


def render_import_tab(config: dict[str, Any], *, locale: str) -> None:
    key_prefix = config["id"]
    label = config["label"]
    left, right = st.columns([1.25, 1.75])
    browser_timezone_name = get_browser_timezone_name()
    initialize_import_form_state(config, browser_timezone_name=browser_timezone_name)

    with left:
        api_key = st.text_input(
            f"{label} API Key",
            type="password",
            key=f"{key_prefix}_api_key",
        )
        api_secret = st.text_input(
            f"{label} API Secret",
            type="password",
            key=f"{key_prefix}_api_secret",
        )
        passphrase = ""
        if config["needs_passphrase"]:
            passphrase = st.text_input(
                f"{label} Passphrase",
                type="password",
                key=f"{key_prefix}_passphrase",
            )
        base_url = st.text_input(
            t(locale, "field.api_base_url"),
            key=f"{key_prefix}_base_url",
        )
        account_label = st.text_input(
            t(locale, "field.account_label"),
            key=f"{key_prefix}_account_label",
        )

    with right:
        market_pairs = st.text_area(
            t(locale, "field.market_pairs"),
            help=t(locale, "field.market_pairs.help"),
            key=f"{key_prefix}_market_pairs",
        )
        import_start_date = st.date_input(
            t(locale, "field.start_date"),
            key=f"{key_prefix}_start_date",
        )
        import_end_date = st.date_input(
            t(locale, "field.end_date"),
            key=f"{key_prefix}_end_date",
        )

    persist_import_form_state(config)

    if st.button(
        t(locale, "button.import_fills", exchange=label),
        type="primary",
        width="stretch",
        key=f"import_{key_prefix}",
    ):
        if not api_key or not api_secret:
            st.error(t(locale, "error.api_credentials_required", exchange=label))
            return
        if config["needs_passphrase"] and not passphrase:
            st.error(t(locale, "error.passphrase_required", exchange=label))
            return
        if not market_pairs.strip():
            st.error(t(locale, "error.market_pairs_required"))
            return
        if import_start_date > import_end_date:
            st.error(t(locale, "error.invalid_date_range"))
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
            start_ms, end_ms = local_date_bounds(
                import_start_date,
                import_end_date,
                timezone_name=browser_timezone_name,
            )
            progress_bar = st.progress(0, text=t(locale, "progress.preparing_import", exchange=label))

            def progress(current: int, total: int, message: str) -> None:
                del message
                progress_bar.progress(
                    int(100 * current / max(total, 1)),
                    text=t(locale, "progress.importing", exchange=label, current=current, total=total),
                )

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

            session_notices: list[Notice | dict[str, object]] = list(notices)
            if unresolved:
                session_notices.append({"kind": "unresolved_symbols", "symbols": unresolved})

            st.session_state["flash_message"] = {
                "kind": "import_complete",
                "exchange_label": label,
                "inserted": inserted,
                "skipped": skipped,
            }
            st.session_state["flash_notices"] = session_notices
            st.rerun()
        except ExchangeAPIError as exc:
            st.error(t(locale, "error.exchange_api", exchange=label, message=str(exc)))
        except Exception as exc:  # pragma: no cover
            st.exception(exc)


st.markdown(
    """
    <style>
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"] {
      display: none;
    }
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
      font-size: clamp(1.85rem, 2.8vw, 2.45rem);
      line-height: 1.0;
      margin-bottom: 0.4rem;
      letter-spacing: -0.03em;
      font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "fills_df" not in st.session_state:
    st.session_state["fills_df"] = load_state()
if "flash_message" not in st.session_state:
    st.session_state["flash_message"] = None
if "flash_notices" not in st.session_state:
    st.session_state["flash_notices"] = []

if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = resolve_ui_locale(
        get_query_param_locale(),
        None,
        st.context.locale,
    )
if "ui_language_selector" not in st.session_state:
    st.session_state["ui_language_selector"] = st.session_state["ui_language"]

active_locale = st.session_state["ui_language"]

title_col, language_col = st.columns([6.0, 1.4])
with title_col:
    st.markdown(f'<div class="page-title">{t(active_locale, "app.title")}</div>', unsafe_allow_html=True)
with language_col:
    st.selectbox(
        t(active_locale, "language.label"),
        options=list(LANGUAGE_OPTIONS),
        index=list(LANGUAGE_OPTIONS).index(st.session_state["ui_language_selector"]),
        format_func=get_language_name,
        key="ui_language_selector",
    )

selected_locale = st.session_state["ui_language_selector"]
if selected_locale != st.session_state["ui_language"]:
    st.session_state["ui_language"] = selected_locale
    sync_query_param_locale(selected_locale)
    st.rerun()

active_locale = st.session_state["ui_language"]
sync_query_param_locale(active_locale)
sync_browser_tab_title(active_locale)

fills_df = st.session_state["fills_df"]

with st.expander(t(active_locale, "section.import"), expanded=fills_df.empty):
    tabs = st.tabs([config["label"] for config in IMPORT_CONFIGS])
    for tab, config in zip(tabs, IMPORT_CONFIGS):
        with tab:
            render_import_tab(config, locale=active_locale)


flash_message = st.session_state.get("flash_message")
if flash_message:
    rendered_flash_message = build_flash_message_text(active_locale, flash_message)
    if rendered_flash_message:
        st.success(rendered_flash_message)
    st.session_state["flash_message"] = None

flash_notices = st.session_state.get("flash_notices", [])
if flash_notices:
    for notice in flash_notices:
        rendered_notice = build_notice_text(active_locale, notice)
        if rendered_notice:
            st.warning(rendered_notice)
    st.session_state["flash_notices"] = []


if fills_df.empty:
    st.info(t(active_locale, "info.no_fills"))
else:
    market_keys = list_market_keys(fills_df)
    selected_market_default = st.session_state.get("selected_market", market_keys[0])
    selected_market_index = market_keys.index(selected_market_default) if selected_market_default in market_keys else 0

    controls_left, controls_right = st.columns([1.5, 1.2])
    with controls_left:
        selected_market = st.selectbox(
            t(active_locale, "field.market"),
            options=market_keys,
            index=selected_market_index,
            key="selected_market",
        )
    with controls_right:
        selected_interval = st.select_slider(
            t(active_locale, "field.interval"),
            options=list(TIME_BUCKETS),
            value="1d",
            format_func=lambda value: interval_label(active_locale, value),
            key="selected_interval",
        )

    market_fills = filter_fills_by_market(fills_df, selected_market)
    if market_fills.empty:
        st.warning(t(active_locale, "warning.no_market_fills"))
    else:
        base_asset, quote_asset = split_market_key(selected_market)

        st.caption(
            t(
                active_locale,
                "caption.market_mix",
                market_key=selected_market,
                interval_label=interval_label(active_locale, selected_interval),
                base_asset=base_asset,
            )
        )

        browser_timezone_name = get_browser_timezone_name()

        @st.fragment(run_every="30s")
        def render_live_chart() -> None:
            current_market = str(st.session_state.get("selected_market", selected_market))
            current_interval = get_selected_interval()
            current_market_fills = filter_fills_by_market(fills_df, current_market)
            current_base_asset, current_quote_asset = split_market_key(current_market)
            current_scatter_df = build_trade_scatter_frame(
                current_market_fills,
                interval=current_interval,
                timezone_name=browser_timezone_name,
            )
            current_position_df = build_cumulative_position_series(
                current_market_fills,
                interval=current_interval,
                timezone_name=browser_timezone_name,
            )
            current_price, live_status = load_live_price_status(active_locale, current_market)
            st.caption(t(active_locale, "caption.live_price", live_status=live_status))
            fig = build_trade_figure(
                current_scatter_df,
                current_position_df,
                market_key=current_market,
                base_asset=current_base_asset,
                price_unit=current_quote_asset,
                locale=active_locale,
                timezone_name=browser_timezone_name,
                current_price=current_price,
            )
            st.plotly_chart(
                fig,
                width="stretch",
                key=f"trade-chart-{current_market}-{current_interval}",
            )

        render_live_chart()
