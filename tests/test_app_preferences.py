from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.storage import TradeRepository


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_saved_import_credentials_load_on_new_app_session(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "trades.sqlite3"
    monkeypatch.setenv("TRADE_REVIEW_DB_PATH", str(db_path))

    repository = TradeRepository(db_path)
    repository.save_app_state(
        "import_form:binance",
        {
            "api_key": "saved-binance-key",
            "api_secret": "saved-binance-secret",
            "passphrase": "",
            "base_url": "https://api.binance.com",
            "account_label": "Saved Binance",
            "market_pairs": "BTCUSDT ETHUSDT",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
    )

    app = AppTest.from_file(APP_PATH)
    app.run()

    assert app.session_state["binance_api_key"] == "saved-binance-key"
    assert app.session_state["binance_api_secret"] == "saved-binance-secret"
    assert app.session_state["binance_account_label"] == "Saved Binance"
    assert app.session_state["binance_market_pairs"] == "BTCUSDT ETHUSDT"

