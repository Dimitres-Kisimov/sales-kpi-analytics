"""CLI — run the full analysis and write the deliverables.

    python -m saleskpi                 # print the KPI summary + decision cards
    python -m saleskpi --deliverables  # also write deliverables/ (Excel, QBR, chart...)
    python -m saleskpi --sql           # run the SQL cross-check queries

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import argparse
import sys

from .report import analyze, write_deliverables


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="saleskpi", description=__doc__)
    ap.add_argument("--deliverables", action="store_true", help="write deliverables/")
    ap.add_argument("--sql", action="store_true", help="run the SQL cross-check queries")
    a = ap.parse_args(argv)

    if a.sql:
        from .sqlq import connect, run_file
        con = connect()
        print("# revenue_by_region.sql")
        for r in run_file(con, "revenue_by_region.sql"):
            print(f"  {r['region']:12s} {r['revenue_eur']:>14,.0f} EUR  "
                  f"margin {r['margin_pct']:>5.1f}%  orders {r['orders']}")
        print("# otif_by_channel.sql")
        for r in run_file(con, "otif_by_channel.sql"):
            print(f"  {r['channel']:12s} OTIF {r['otif_pct']:>5.1f}%  "
                  f"on-time {r['on_time_pct']:>5.1f}%  fill {r['fill_rate_pct']:>5.1f}%")
        return 0

    analysis = analyze()
    k = analysis["kpi"]
    print("SALES & DEMAND ANALYTICS\n" + "=" * 60)
    print(f"Revenue {k['revenue_eur']:,.0f} EUR | margin {k['gross_margin_pct']:.1f}% | "
          f"AOV {k['aov_eur']:,.0f} EUR | OTIF {k['otif_pct']:.0f}% | "
          f"{k['active_customers']} customers")
    rf = analysis["revenue_forecast"]
    print(f"\nForecast (next 3 mo, model {rf['winner']}, CV-MASE {rf['cv_mase']:.2f}): "
          f"{', '.join(f'{v:,.0f}' for v in rf['forecast'])} EUR")
    print("\nDecision cards:")
    for c in analysis["decision_cards"]:
        print(f"  - {c}")
    print(f"\nReorder list: {len(analysis['reorder_list'])} cells below reorder point.")
    if a.deliverables:
        made = write_deliverables(analysis)
        print("\nDeliverables written to deliverables/: " + ", ".join(made))
    else:
        print("\n(run with --deliverables to write the Excel workbook, QBR report and chart)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
