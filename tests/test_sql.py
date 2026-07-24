"""Integrity cross-check: the SQL engine and the Python engine must agree.

This is the key test — if the two implementations ever drift, this fails.
"""
from __future__ import annotations

from saleskpi import metrics
from saleskpi.sqlq import connect, run_file


def test_sql_revenue_by_region_matches_python(real_rows):
    con = connect()
    sql_rows = run_file(con, "revenue_by_region.sql")
    sql_by_region = {r["region"]: r for r in sql_rows}

    py_rows = metrics.by_dimension(real_rows, "region")
    py_by_region = {r["region"]: r for r in py_rows}

    assert set(sql_by_region) == set(py_by_region), "region sets differ"

    for region, py in py_by_region.items():
        sql = sql_by_region[region]
        # revenue must agree within rounding
        assert abs(sql["revenue_eur"] - py["revenue_eur"]) < 0.05, region
        # margin % must agree within rounding
        assert abs(sql["margin_pct"] - py["margin_pct"]) < 0.1, region
        # order counts must be identical
        assert sql["orders"] == py["orders"], region

    # and the grand totals reconcile
    assert abs(sum(r["revenue_eur"] for r in sql_rows)
               - sum(r["revenue_eur"] for r in py_rows)) < 1.0


def test_sql_otif_by_channel_runs(real_rows):
    con = connect()
    rows = run_file(con, "otif_by_channel.sql")
    assert rows
    for r in rows:
        assert 0 <= r["otif_pct"] <= 100
        assert 0 <= r["on_time_pct"] <= 100
        assert 0 <= r["fill_rate_pct"] <= 100
    # sorted by OTIF descending (as the query specifies)
    otifs = [r["otif_pct"] for r in rows]
    assert otifs == sorted(otifs, reverse=True)
