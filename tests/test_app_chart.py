import json
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.storage import TradeRepository


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_live_price_line_switches_with_selected_market(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "trades.sqlite3"
    monkeypatch.setenv("TRADE_REVIEW_DB_PATH", str(db_path))

    repository = TradeRepository(db_path)
    repository.upsert_fills(
        pd.DataFrame(
            [
                {
                    "uid": "btc-1",
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
                    "base_qty": 0.1,
                    "price": 60000.0,
                    "quote_qty": 6000.0,
                    "fee_amount": 0.0,
                    "fee_asset": "USDT",
                    "executed_at_ms": 1_735_696_800_000,
                    "notes": "",
                },
                {
                    "uid": "eth-1",
                    "source_type": "binance_api",
                    "source_name": "Binance API",
                    "exchange": "binance",
                    "account_label": "main",
                    "symbol": "ETHUSDT",
                    "order_id": "2",
                    "trade_id": "2",
                    "side": "BUY",
                    "base_asset": "ETH",
                    "quote_asset": "USDT",
                    "base_qty": 1.0,
                    "price": 3000.0,
                    "quote_qty": 3000.0,
                    "fee_amount": 0.0,
                    "fee_asset": "USDT",
                    "executed_at_ms": 1_735_696_800_000,
                    "notes": "",
                },
            ]
        )
    )

    app = AppTest.from_file(APP_PATH)
    app.run()

    initial_spec = json.loads(app.main.children[6].children[1].proto.spec)
    assert initial_spec["layout"]["title"]["text"] == "BTC/USDT"
    assert "BTC/USDT" in initial_spec["layout"]["annotations"][0]["text"]

    app.selectbox[1].set_value("ETH/USDT").run()

    updated_spec = json.loads(app.main.children[6].children[1].proto.spec)
    assert updated_spec["layout"]["title"]["text"] == "ETH/USDT"
    assert "ETH/USDT" in updated_spec["layout"]["annotations"][0]["text"]
