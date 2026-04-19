from __future__ import annotations

SUPPORTED_LOCALES = ("en", "zh-CN")
DEFAULT_LOCALE = "en"
LANGUAGE_OPTIONS = ("en", "zh-CN")

LANGUAGE_NAMES = {
    "zh-CN": "中文",
    "en": "English",
}

TRANSLATIONS = {
    "zh-CN": {
        "app.title": "成交复盘",
        "app.page_title": "成交复盘",
        "language.label": "语言",
        "field.api_base_url": "API Base URL",
        "field.account_label": "账户标签",
        "field.market_pairs": "交易对",
        "field.market_pairs.help": "支持 BTCUSDT、BTC/USDT、BTC-USDT、BTC_USDT 这几种写法；多个交易对用空格、逗号或换行分隔。",
        "field.start_date": "开始日期",
        "field.end_date": "结束日期",
        "field.market": "市场",
        "field.interval": "时间粒度",
        "section.import": "交易所 API 导入",
        "button.import_fills": "导入 {exchange} 实际成交",
        "error.api_credentials_required": "请提供 {exchange} API Key 和 Secret。",
        "error.passphrase_required": "请提供 {exchange} Passphrase。",
        "error.market_pairs_required": "请至少输入一个交易对。",
        "error.invalid_date_range": "开始日期不能晚于结束日期。",
        "error.exchange_api": "{exchange} 导入失败：{message}",
        "progress.preparing_import": "准备抓取 {exchange} 实际成交",
        "progress.importing": "抓取 {exchange} 成交 ({current}/{total})",
        "flash.import_complete": "{exchange} 导入完成：新增 {inserted} 条，重复跳过 {skipped} 条。",
        "notice.unresolved_symbols": "这些交易对未识别：{symbols}",
        "notice.retention_limit": "{exchange} 只支持近 {days} 天成交，已自动截断更早时间。",
        "info.no_fills": "当前还没有实际成交数据。先在上方导入至少一个市场的历史成交。",
        "warning.no_market_fills": "当前市场还没有实际成交。",
        "caption.market_mix": "这张图会把所有交易所里 `{market_key}` 的真实成交混在一起。上面的散点按 {interval_label} 聚成净流向点，下面的折线显示 `{base_asset}` 的累计数量变化。",
        "caption.live_price": "当前价格线优先使用 Binance 现货参考价，每 30 秒自动更新一次。{live_status}",
        "live_price.available": "{market_key} Binance 参考价 {current_price:,.4f}。",
        "live_price.unavailable": "{market_key} 当前价暂时不可用。",
        "live_price.failure_reason": "获取失败原因：{message}",
        "chart.title": "{market_key}",
        "chart.flow.net_in": "净流入",
        "chart.flow.net_out": "净流出",
        "chart.flow.net_flat": "净零",
        "chart.position_series": "累计 {base_asset}",
        "chart.current_price_line": "Binance 参考价 {current_price:,.4f}",
        "chart.xaxis.time": "时间（{timezone_name}）",
        "chart.yaxis.price": "价格 ({price_unit})",
        "chart.yaxis.cumulative": "累计 {base_asset}",
        "chart.hover.bucket": "时间桶",
        "chart.hover.price": "价格",
        "chart.hover.price_range": "价格范围",
        "chart.hover.buy_qty": "买入总量",
        "chart.hover.sell_qty": "卖出总量",
        "chart.hover.net_change": "净变化",
        "chart.hover.trade_count": "合并成交数",
        "chart.hover.exchange_sources": "交易所来源",
        "chart.hover.cumulative_qty": "累计数量",
        "interval.1h": "1小时",
        "interval.4h": "4小时",
        "interval.1d": "1天",
        "interval.1w": "1周",
        "interval.1M": "1月",
        "interval.1y": "1年",
    },
    "en": {
        "app.title": "Trade Review",
        "app.page_title": "Trade Review",
        "language.label": "Language",
        "field.api_base_url": "API Base URL",
        "field.account_label": "Account Label",
        "field.market_pairs": "Markets",
        "field.market_pairs.help": "Supports BTCUSDT, BTC/USDT, BTC-USDT, and BTC_USDT. Separate multiple markets with spaces, commas, or new lines.",
        "field.start_date": "Start Date",
        "field.end_date": "End Date",
        "field.market": "Market",
        "field.interval": "Time Interval",
        "section.import": "Exchange API Import",
        "button.import_fills": "Import {exchange} Fills",
        "error.api_credentials_required": "Please provide the {exchange} API Key and Secret.",
        "error.passphrase_required": "Please provide the {exchange} passphrase.",
        "error.market_pairs_required": "Enter at least one market.",
        "error.invalid_date_range": "The start date cannot be later than the end date.",
        "error.exchange_api": "{exchange} import failed: {message}",
        "progress.preparing_import": "Preparing to fetch {exchange} fills",
        "progress.importing": "Fetching {exchange} fills ({current}/{total})",
        "flash.import_complete": "{exchange} import complete: {inserted} new fills, {skipped} duplicates skipped.",
        "notice.unresolved_symbols": "These markets were not recognized: {symbols}",
        "notice.retention_limit": "{exchange} only provides fills for the last {days} days. Earlier dates were truncated automatically.",
        "info.no_fills": "No executed fills have been imported yet. Import at least one market above to start reviewing.",
        "warning.no_market_fills": "There are no executed fills for this market yet.",
        "caption.market_mix": "This chart mixes real fills from every exchange that matches `{market_key}`. The top scatter aggregates net flow points by {interval_label}, and the bottom line shows the cumulative `{base_asset}` position.",
        "caption.live_price": "The price line uses the Binance spot reference price and refreshes automatically every 30 seconds. {live_status}",
        "live_price.available": "{market_key} Binance reference price {current_price:,.4f}.",
        "live_price.unavailable": "{market_key} live price is currently unavailable.",
        "live_price.failure_reason": "Failure reason: {message}",
        "chart.title": "{market_key}",
        "chart.flow.net_in": "Net Inflow",
        "chart.flow.net_out": "Net Outflow",
        "chart.flow.net_flat": "Net Flat",
        "chart.position_series": "Cumulative {base_asset}",
        "chart.current_price_line": "Binance reference {current_price:,.4f}",
        "chart.xaxis.time": "Time ({timezone_name})",
        "chart.yaxis.price": "Price ({price_unit})",
        "chart.yaxis.cumulative": "Cumulative {base_asset}",
        "chart.hover.bucket": "Time Bucket",
        "chart.hover.price": "Price",
        "chart.hover.price_range": "Price Range",
        "chart.hover.buy_qty": "Buy Qty",
        "chart.hover.sell_qty": "Sell Qty",
        "chart.hover.net_change": "Net Change",
        "chart.hover.trade_count": "Merged Fills",
        "chart.hover.exchange_sources": "Exchanges",
        "chart.hover.cumulative_qty": "Cumulative Qty",
        "interval.1h": "1H",
        "interval.4h": "4H",
        "interval.1d": "1D",
        "interval.1w": "1W",
        "interval.1M": "1M",
        "interval.1y": "1Y",
    },
}


def normalize_locale(raw_locale: str | None) -> str:
    if not raw_locale:
        return DEFAULT_LOCALE
    locale = raw_locale.strip().replace("_", "-").lower()
    if locale.startswith("zh"):
        return "zh-CN"
    if locale.startswith("en"):
        return "en"
    return DEFAULT_LOCALE


def get_active_locale(session_locale: str | None, context_locale: str | None) -> str:
    if session_locale:
        return normalize_locale(session_locale)
    return normalize_locale(context_locale)


def resolve_ui_locale(
    query_locale: str | None,
    session_locale: str | None,
    context_locale: str | None,
) -> str:
    if query_locale:
        return normalize_locale(query_locale)
    if session_locale:
        return normalize_locale(session_locale)
    return normalize_locale(context_locale)


def get_language_name(locale_code: str) -> str:
    return LANGUAGE_NAMES.get(normalize_locale(locale_code), locale_code)


def interval_label(locale: str, interval: str) -> str:
    return t(locale, f"interval.{interval}")


def t(locale: str, key: str, **kwargs: object) -> str:
    normalized_locale = normalize_locale(locale)
    template = TRANSLATIONS.get(normalized_locale, TRANSLATIONS[DEFAULT_LOCALE]).get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LOCALE].get(key, key)
    return template.format(**kwargs)
