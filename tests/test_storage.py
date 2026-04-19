from src.storage import TradeRepository


def test_trade_repository_persists_app_state(tmp_path) -> None:
    db_path = tmp_path / "trades.sqlite3"
    repository = TradeRepository(db_path)

    repository.save_app_state(
        "import_form:okx",
        {
            "api_key": "key-1",
            "api_secret": "secret-1",
            "market_pairs": "BTCUSDT",
        },
    )

    reloaded = TradeRepository(db_path)

    assert reloaded.load_app_state("import_form:okx") == {
        "api_key": "key-1",
        "api_secret": "secret-1",
        "market_pairs": "BTCUSDT",
    }
    assert reloaded.load_app_state("import_form:missing") is None
