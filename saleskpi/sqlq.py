"""sqlq.py — load the transactions into in-memory SQLite and run KPI queries.

Demonstrates the SQL side of the role and doubles as a cross-check: a test
asserts the SQL revenue-by-region equals the Python metric, so the two engines
can't silently drift.

    from saleskpi.sqlq import connect, run_file
    con = connect()
    rows = run_file(con, "revenue_by_region.sql")

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .dataset import load

_SQL = Path(__file__).resolve().parents[1] / "sql"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    rows = load(path)
    cols = [c for c in rows[0] if c != "margin_eur"]
    con.execute(f"CREATE TABLE sales ({', '.join(c + ' ' + _sqltype(c) for c in cols)})")
    con.executemany(
        f"INSERT INTO sales ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [[r[c] for c in cols] for r in rows],
    )
    con.commit()
    return con


def _sqltype(col: str) -> str:
    if col in ("units", "promised_lead_days", "actual_lead_days", "on_time", "in_full", "returned"):
        return "INTEGER"
    if col in ("list_price_eur", "discount_pct", "revenue_eur", "cost_eur"):
        return "REAL"
    return "TEXT"


def run(con: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(r) for r in con.execute(sql).fetchall()]


def run_file(con: sqlite3.Connection, name: str) -> list[dict]:
    return run(con, (_SQL / name).read_text(encoding="utf-8"))
