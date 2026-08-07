"""Tests for the end-to-end analysis pipeline and deliverable writers."""
from __future__ import annotations

import json
from importlib.util import find_spec

from saleskpi.report import analyze, write_deliverables

EXPECTED_KEYS = {
    "kpi", "growth", "regions", "categories", "channels", "reps", "abc_xyz",
    "rfm_segments", "rfm_top", "margin_bridge", "revenue_bridge", "concentration",
    "revenue_forecast", "series_forecasts", "reorder_list", "decision_cards",
    "expenditure", "kpi_alerts",
}


def test_analyze_returns_expected_keys(real_rows):
    a = analyze(real_rows)
    assert EXPECTED_KEYS <= set(a)
    assert a["kpi"]["orders"] == len(real_rows)
    assert a["decision_cards"], "expected at least one decision card"
    rf = a["revenue_forecast"]
    assert rf["winner"]
    assert len(rf["forecast"]) == 3


def test_write_deliverables_produces_core_files(real_rows, tmp_path):
    a = analyze(real_rows)
    made = write_deliverables(a, outdir=tmp_path)

    # always-present, stdlib-only deliverables
    assert (tmp_path / "analysis.json").exists()
    assert (tmp_path / "management_report.md").exists()
    assert (tmp_path / "reorder_list.csv").exists()
    assert {"analysis.json", "management_report.md", "reorder_list.csv"} <= set(made)

    # analysis.json must be valid JSON round-tripping the same keys
    loaded = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert EXPECTED_KEYS <= set(loaded)

    # the QBR report is non-trivial markdown
    md = (tmp_path / "management_report.md").read_text(encoding="utf-8")
    assert "Quarterly Business Review" in md


def test_optional_deliverables_when_libs_present(real_rows, tmp_path):
    a = analyze(real_rows)
    made = write_deliverables(a, outdir=tmp_path)
    if find_spec("openpyxl"):
        assert (tmp_path / "kpi_workbook.xlsx").exists()
        assert "kpi_workbook.xlsx" in made
    if find_spec("matplotlib"):
        assert (tmp_path / "forecast.png").exists()
        assert "forecast.png" in made
        # the leakage drill-down waterfall must be rebuilt and non-empty
        wf = tmp_path / "leakage_waterfall.png"
        assert wf.exists() and wf.stat().st_size > 0
        assert "leakage_waterfall.png" in made


def test_drilldown_reaches_report_and_json(real_rows, tmp_path):
    a = analyze(real_rows)
    dd = a["expenditure"]["leakage_drilldown"]
    assert dd["by_sales_rep"] and dd["by_region"]
    write_deliverables(a, outdir=tmp_path)
    loaded = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert "leakage_drilldown" in loaded["expenditure"]
    md = (tmp_path / "management_report.md").read_text(encoding="utf-8")
    assert "Discount-leakage drill-down" in md
    assert dd["by_sales_rep"][0]["sales_rep"] in md
