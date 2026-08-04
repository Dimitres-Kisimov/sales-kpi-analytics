# Questions this answers

Concrete questions a distributor's leadership actually asks, each mapped to the
**exact** metric (Python function and/or SQL view) that answers it, with a
one-line honest note on the assumptions behind the number.

All figures come from the **synthetic** 24-month dataset
(`data/sales_transactions.csv`, generated deterministically — see
[CREDITS.md](../CREDITS.md)); regenerate and every number below reconciles.

| # | Business question | Exact metric / view | Honest note on assumptions |
|---|---|---|---|
| 1 | How much did we sell, at what margin, and to how many customers? | `saleskpi.metrics.kpi_summary` → `revenue_eur`, `gross_margin_pct`, `active_customers` | Gross margin = revenue − cost; no allocation of overhead/opex (line-level P&L only). |
| 2 | Is revenue growing year-on-year, and month-on-month? | `saleskpi.metrics.growth` → `yoy_pct`, `mom_pct` | YoY needs 24 months of history; on a short series it is a single point-to-point comparison, not a trend model. |
| 3 | Which regions drive revenue and margin? | `saleskpi.metrics.by_dimension(rows, "region")` · SQL `revenue_by_region.sql` | All-time rollup; a live "last 12 months" cut is done in the app layer, not the reference view. |
| 4 | Did revenue grow by selling more, by price, or by mix shift? | `saleskpi.pvm.revenue_bridge` → `price_effect_eur`, `volume_effect_eur`, `mix_effect_eur` (`pvm_bridge.csv`, `pvm_waterfall.svg`) | Realised price = revenue ÷ units; volume is proportional growth and mix the residual reallocation, so the three sum exactly to the revenue change; needs 24 months (last-12 vs prior-12). |
| 4b | Did *margin* move on price, volume or mix? | `saleskpi.metrics.margin_bridge` → `price_effect_eur`, `volume_effect_eur`, `mix_effect_eur` | Same last-12 vs prior-12 window on gross margin; mix is the residual so the three sum exactly to the total margin change. |
| 5 | How much margin are we giving away versus list price (discount leakage)? | `saleskpi.spend.discount_leakage` / `spend_summary` → `discount_leakage_eur` · SQL `leakage_waterfall.sql` | Leakage = list value − revenue; a measured fact, independent of any policy assumption. |
| 6 | **Who** is leaking margin — which sales reps? | `saleskpi.spend.leakage_drilldown(...)["by_sales_rep"]` · SQL `leakage_by_rep.sql` | The within-policy vs excess split assumes a 10% sanctioned-discount ceiling (`POLICY_DISCOUNT_PCT`); the total per rep does not depend on it. |
| 7 | **Where** is margin leaking — which regions? | `saleskpi.spend.leakage_drilldown(...)["by_region"]` · SQL `leakage_by_region.sql` | Same policy assumption as #6; every euro of leakage is attributed to exactly one region (no orphans). |
| 8 | How does the leakage break down from gross list value to net revenue? | `saleskpi.spend.waterfall` → `steps` (rendered as `leakage_waterfall.svg` / `.png`) · SQL `leakage_waterfall.sql` | The waterfall reconciles by construction: gross − within − excess = net; the visual is asserted equal to the source numbers in tests. |
| 9 | What does each sales channel really cost to serve? | `saleskpi.spend.cost_to_serve_by_channel` → `cost_to_serve_eur` | Cost-to-serve = COGS + modeled returns cost + discount leakage; returns cost is a rate × avg-cost **model**, not measured restocking cost. |
| 10 | Which product categories are the core, and which tie up working capital? | `saleskpi.metrics.abc_xyz` → `class` (A/B/C × X/Y/Z) | ABC cutoffs (80% / 95%) and XYZ CV cutoffs (0.5 / 1.0) are tunable conventions, not laws. |
| 11 | Who are our best customers, and who is slipping away? | `saleskpi.metrics.rfm` → `segment` (Champions / At risk / …) | Scores are quintile ranks within *this* dataset; segment thresholds are the standard RFM convention. |
| 12 | How concentrated is revenue in our top customers? | `saleskpi.metrics.concentration` → `top_share_pct` | Default is the top 20% of customers by revenue (Pareto); the cut is a parameter. |
| 13 | What will revenue be over the next quarter, and can we trust it? | `saleskpi.forecast.select_and_forecast` → `values`, `cv_mase` | Model chosen by rolling-origin CV; on 24 months the CV-MASE sits above 1 (seasonal-naive is hard to beat) and the report says so rather than hiding it. |
| 14 | What should we reorder now, and how much? | `saleskpi.inventory.reorder_recommendation` → `recommended_order_qty` (`deliverables/reorder_list.csv`) | Assumes a flat ~1-month supplier lead time and per-ABC service levels; a real lead-time distribution would refine it. |
| 15 | Are we delivering on service (OTIF), and where are we failing? | `saleskpi.metrics.kpi_summary` → `otif_pct`, `on_time_pct`, `fill_rate_pct` · SQL `otif_by_channel.sql` | OTIF = on-time **and** in-full; both flags are modeled in the synthetic data, not drawn from a real WMS. |
