from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_language_switch_overrides_previous_query_param_and_updates_url() -> None:
    app = AppTest.from_file(APP_PATH)
    app.query_params["lang"] = "en"

    app.run()

    assert app.session_state["ui_language"] == "en"
    assert app.selectbox[0].value == "en"
    assert dict(app.query_params) == {"lang": ["en"]}

    app.selectbox[0].set_value("zh-CN").run()

    assert app.session_state["ui_language"] == "zh-CN"
    assert app.session_state["ui_language_selector"] == "zh-CN"
    assert app.selectbox[0].value == "zh-CN"
    assert dict(app.query_params) == {"lang": ["zh-CN"]}
