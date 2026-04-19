from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics import STANDARD_COLUMNS


CREATE_FILLS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS fills (
    uid TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    account_label TEXT NOT NULL,
    symbol TEXT NOT NULL,
    order_id TEXT,
    trade_id TEXT,
    side TEXT NOT NULL,
    base_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    base_qty REAL NOT NULL,
    price REAL NOT NULL,
    quote_qty REAL NOT NULL,
    fee_amount REAL NOT NULL,
    fee_asset TEXT NOT NULL,
    executed_at_ms INTEGER NOT NULL,
    notes TEXT NOT NULL
);
"""

CREATE_APP_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_state (
    state_key TEXT PRIMARY KEY,
    state_json TEXT NOT NULL
);
"""


class TradeRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_FILLS_TABLE_SQL)
            conn.execute(CREATE_APP_STATE_TABLE_SQL)
            conn.commit()

    def upsert_fills(self, fills_df: pd.DataFrame) -> tuple[int, int]:
        if fills_df.empty:
            return 0, 0

        df = fills_df.copy()[STANDARD_COLUMNS]
        df = df.where(pd.notna(df), None)
        records = list(df.itertuples(index=False, name=None))

        inserted = 0
        skipped = 0
        sql = """
        INSERT OR IGNORE INTO fills (
            uid, source_type, source_name, exchange, account_label, symbol,
            order_id, trade_id, side, base_asset, quote_asset, base_qty, price,
            quote_qty, fee_amount, fee_asset, executed_at_ms, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            before = conn.total_changes
            conn.executemany(sql, records)
            conn.commit()
            inserted = conn.total_changes - before
        skipped = len(df) - inserted
        return inserted, skipped

    def load_fills(self) -> pd.DataFrame:
        with self._connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT
                    uid, source_type, source_name, exchange, account_label, symbol,
                    order_id, trade_id, side, base_asset, quote_asset, base_qty,
                    price, quote_qty, fee_amount, fee_asset, executed_at_ms, notes
                FROM fills
                ORDER BY executed_at_ms ASC, uid ASC
                """,
                conn,
            )
        if df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)
        return df

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM fills")
            conn.commit()

    def save_app_state(self, state_key: str, payload: dict[str, object]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state (state_key, state_json)
                VALUES (?, ?)
                ON CONFLICT(state_key) DO UPDATE SET state_json = excluded.state_json
                """,
                (state_key, json.dumps(payload)),
            )
            conn.commit()

    def load_app_state(self, state_key: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM app_state WHERE state_key = ?",
                (state_key,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict) else None
