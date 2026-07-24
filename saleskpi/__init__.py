"""saleskpi — a distributor sales & demand analytics toolkit.

Turns 24 months of order data into management KPIs, an ABC-XYZ portfolio view,
RFM customer segments, a price/volume/mix margin bridge, and per-series demand
forecasts selected by rolling-origin cross-validation (MASE) — then writes the
deliverables (Excel workbook, QBR report, reorder list, forecast chart).

    from saleskpi.report import analyze, write_deliverables
    a = analyze()
    write_deliverables(a)

Author: Dimitres Kisimov · MIT.
"""
__version__ = "0.1.0"
