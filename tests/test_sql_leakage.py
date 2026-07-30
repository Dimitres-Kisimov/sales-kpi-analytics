"""SQL leakage-views layer — must agree with the Python engine to the cent.

The parameterized views in sql/ (leakage_by_rep, leakage_by_region,
leakage_waterfall) mirror saleskpi.spend.leakage_drilldown. If the two engines
ever drift, these fail. Also a smoke test that the files parse, run and are
documented in sql/README.md against the Python metric they mirror.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from saleskpi import spend
from saleskpi.sqlq import connect, run_file

POLICY = {"policy_pct": spend.POLICY_DISCOUNT_PCT}
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"

# each new view -> (Python callable it mirrors, columns it must return)
NEW_VIEWS = {
    "leakage_by_rep.sql": (
        "leakage_drilldown",
        ["sales_rep", "leakage_eur", "excess_eur", "within_policy_eur",
         "revenue_eur", "orders", "orders_above_policy_pct"]),
    "leakage_by_region.sql": (
        "leakage_drilldown",
        ["region", "leakage_eur", "excess_eur", "within_policy_eur",
         "revenue_eur", "orders", "orders_above_policy_pct"]),
    "leakage_waterfall.sql": (
        "waterfall",
        ["gross_list_value_eur", "within_policy_discount_eur", "excess_discount_eur",
         "net_revenue_eur", "total_leakage_eur"]),
}


def test_leakage_by_rep_sql_matches_python(real_rows):
    con = connect()
    sql_rows = run_file(con, "leakage_by_rep.sql", POLICY)
    py = spend.leakage_drilldown(real_rows)["by_sales_rep"]
    py_by = {r["sales_rep"]: r for r in py}
    assert {r["sales_rep"] for r in sql_rows} == set(py_by)
    for r in sql_rows:
        p = py_by[r["sales_rep"]]
        for col in ("leakage_eur", "excess_eur", "within_policy_eur", "revenue_eur",
                    "orders_above_policy_pct"):
            assert abs(r[col] - p[col]) < 0.01, (r["sales_rep"], col)
        assert r["orders"] == p["orders"]
    # both engines rank worst-offender-first by excess over policy
    assert [r["sales_rep"] for r in sql_rows] == [r["sales_rep"] for r in py]


def test_leakage_by_region_sql_matches_python(real_rows):
    con = connect()
    sql_rows = run_file(con, "leakage_by_region.sql", POLICY)
    py = spend.leakage_drilldown(real_rows)["by_region"]
    py_by = {r["region"]: r for r in py}
    assert {r["region"] for r in sql_rows} == set(py_by)
    for r in sql_rows:
        p = py_by[r["region"]]
        for col in ("leakage_eur", "excess_eur", "within_policy_eur", "revenue_eur"):
            assert abs(r[col] - p[col]) < 0.01, (r["region"], col)
        assert r["orders"] == p["orders"]


def test_leakage_waterfall_sql_matches_python(real_rows):
    con = connect()
    w = run_file(con, "leakage_waterfall.sql", POLICY)[0]
    dd = spend.leakage_drilldown(real_rows)
    for col in NEW_VIEWS["leakage_waterfall.sql"][1]:
        assert abs(w[col] - dd[col]) < 0.01, col
    # the SQL waterfall reconciles on its own numbers
    assert abs(w["gross_list_value_eur"] - w["within_policy_discount_eur"]
               - w["excess_discount_eur"] - w["net_revenue_eur"]) < 0.01
    assert abs(w["within_policy_discount_eur"] + w["excess_discount_eur"]
               - w["total_leakage_eur"]) < 0.01


def test_drilldown_sums_to_total_to_the_cent(real_rows):
    """Every euro of leakage is attributed to exactly one rep and one region, so
    both drill-downs reconcile to the headline total exactly (unrounded)."""
    total = spend.discount_leakage(real_rows)
    for dim in ("sales_rep", "region"):
        groups: dict[str, list] = defaultdict(list)
        for r in real_rows:
            groups[r[dim]].append(r)
        summed = sum(spend.discount_leakage(g) for g in groups.values())
        assert abs(summed - total) < 0.01, dim   # to the cent (in fact exact)

    # and the SQL views' displayed (cent-rounded) figures reconcile within the
    # unavoidable per-group rounding drift
    con = connect()
    for name, tol_groups in (("leakage_by_rep.sql", 12), ("leakage_by_region.sql", 5)):
        rows = run_file(con, name, POLICY)
        shown = round(sum(r["leakage_eur"] for r in rows), 2)
        assert abs(shown - round(total, 2)) <= 0.005 * tol_groups + 1e-9, name


def test_sql_leakage_files_parse_nonempty_and_views_documented(real_rows):
    con = connect()
    readme = (SQL_DIR / "README.md").read_text(encoding="utf-8")
    for fname, (py_callable, cols) in NEW_VIEWS.items():
        path = SQL_DIR / fname
        assert path.exists(), fname
        text = path.read_text(encoding="utf-8")
        assert text.strip(), f"{fname} is empty"
        assert ":policy_pct" in text, f"{fname} is not parameterized"
        # it parses and runs against the schema, returning the documented columns
        rows = run_file(con, fname, POLICY)
        assert rows, f"{fname} returned no rows"
        assert set(cols) <= set(rows[0]), f"{fname} missing columns"
        # the view is documented in sql/README.md, mapped to a real Python metric
        assert fname in readme, f"{fname} not documented in sql/README.md"
        assert py_callable in readme, f"{py_callable} mapping missing from sql/README.md"
        assert callable(getattr(spend, py_callable)), py_callable
