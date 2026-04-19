from __future__ import annotations

from src.exchange_importers import fetch_binance_fills


class FakeBinanceClient:
    def __init__(self, pages: dict[int, list[dict]]) -> None:
        self.pages = pages
        self.calls: list[dict] = []

    def get_exchange_info(self) -> dict:
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "permissions": ["SPOT"],
                }
            ]
        }

    def get_account_trades(
        self,
        symbol: str,
        *,
        limit: int = 1000,
        start_time: int | None = None,
        end_time: int | None = None,
        from_id: int | None = None,
    ) -> list[dict]:
        self.calls.append(
            {
                "symbol": symbol,
                "limit": limit,
                "start_time": start_time,
                "end_time": end_time,
                "from_id": from_id,
            }
        )
        return list(self.pages.get(end_time or 0, []))


def _trade(trade_id: int, trade_time: int) -> dict:
    return {
        "id": trade_id,
        "orderId": trade_id + 10_000,
        "time": trade_time,
        "isBuyer": trade_id % 2 == 0,
        "qty": "0.01",
        "price": "60000",
        "quoteQty": "600",
        "commission": "0.1",
        "commissionAsset": "USDT",
    }


def test_fetch_binance_fills_paginates_backwards_with_end_time_only() -> None:
    first_page = [_trade(trade_id, trade_time) for trade_id, trade_time in zip(range(3001, 4001), range(3001, 4001), strict=True)]
    second_page = [
        _trade(1000, 900),
        _trade(1001, 1500),
        _trade(1002, 2500),
        _trade(1002, 2500),
    ]
    client = FakeBinanceClient(
        {
            5000: first_page,
            3000: second_page,
        }
    )

    fills_df, unresolved, notices = fetch_binance_fills(
        client,
        account_label="binance-main",
        manual_symbols="BTCUSDT",
        start_ms=1000,
        end_ms=5000,
    )

    assert unresolved == []
    assert notices == []
    assert client.calls == [
        {
            "symbol": "BTCUSDT",
            "limit": 1000,
            "start_time": None,
            "end_time": 5000,
            "from_id": None,
        },
        {
            "symbol": "BTCUSDT",
            "limit": 1000,
            "start_time": None,
            "end_time": 3000,
            "from_id": None,
        },
    ]
    assert len(fills_df) == 1002
    assert fills_df["executed_at_ms"].min() == 1500
    assert fills_df["executed_at_ms"].max() == 4000
    assert fills_df["trade_id"].tolist()[:2] == ["1001", "1002"]
    assert fills_df["trade_id"].tolist()[-2:] == ["3999", "4000"]


def test_fetch_binance_fills_stops_after_short_page() -> None:
    client = FakeBinanceClient(
        {
            4500: [
                _trade(7, 4400),
                _trade(5, 4200),
                _trade(6, 4300),
            ]
        }
    )

    fills_df, unresolved, notices = fetch_binance_fills(
        client,
        account_label="binance-main",
        manual_symbols="BTCUSDT",
        start_ms=4100,
        end_ms=4500,
    )

    assert unresolved == []
    assert notices == []
    assert len(client.calls) == 1
    assert client.calls[0]["start_time"] is None
    assert client.calls[0]["from_id"] is None
    assert fills_df["trade_id"].tolist() == ["5", "6", "7"]
