from src.i18n import LANGUAGE_OPTIONS, get_active_locale, interval_label, normalize_locale, resolve_ui_locale, t


def test_normalize_locale_maps_supported_variants() -> None:
    assert normalize_locale("zh") == "zh-CN"
    assert normalize_locale("zh-Hans-CN") == "zh-CN"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("en_GB") == "en"


def test_normalize_locale_falls_back_to_english() -> None:
    assert normalize_locale("ja-JP") == "en"
    assert normalize_locale(None) == "en"


def test_get_active_locale_prefers_session_selection() -> None:
    assert get_active_locale("zh-CN", "en-US") == "zh-CN"
    assert get_active_locale("en", "zh-CN") == "en"


def test_get_active_locale_uses_context_when_session_missing() -> None:
    assert get_active_locale(None, "zh-CN") == "zh-CN"
    assert get_active_locale(None, "fr-FR") == "en"


def test_resolve_ui_locale_prefers_query_params_first() -> None:
    assert resolve_ui_locale("en", "zh-CN", "zh-CN") == "en"
    assert resolve_ui_locale("zh-CN", "en", "en-US") == "zh-CN"


def test_resolve_ui_locale_falls_back_from_session_to_context() -> None:
    assert resolve_ui_locale(None, "zh-CN", "en-US") == "zh-CN"
    assert resolve_ui_locale(None, None, "zh-CN") == "zh-CN"
    assert resolve_ui_locale("en", None, "zh-CN") == "en"


def test_manual_selection_must_override_previous_query_param_after_init() -> None:
    initial_locale = resolve_ui_locale("en", None, "zh-CN")
    assert initial_locale == "en"

    selected_locale = "zh-CN"
    assert selected_locale != initial_locale


def test_language_options_show_english_first() -> None:
    assert LANGUAGE_OPTIONS == ("en", "zh-CN")


def test_translation_uses_requested_locale_and_falls_back() -> None:
    assert t("zh-CN", "app.title") == "成交复盘"
    assert t("en", "app.title") == "Trade Review"
    assert t("fr-FR", "app.title") == "Trade Review"
    assert t("zh-CN", "chart.xaxis.time", timezone_name="Asia/Shanghai") == "时间（Asia/Shanghai）"
    assert t("en", "chart.xaxis.time", timezone_name="Asia/Shanghai") == "Time (Asia/Shanghai)"


def test_interval_label_is_localized() -> None:
    assert interval_label("zh-CN", "1y") == "1年"
    assert interval_label("en", "1y") == "1Y"
