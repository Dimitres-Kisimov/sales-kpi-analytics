# DAX measures — Sales KPI Analytics

Paste these into Power BI Desktop (right-click any table → **New measure**)
after importing the star schema from `powerbi/data/`. They are written against
the model in `README.md`: a `fact_sales_monthly` fact (grain = month × region ×
category × channel) related to `dim_date`, `dim_region`, `dim_category`,
`dim_channel`, plus a disconnected `kpi_headline` (metric, value) table for
repo-level scalars.

Every measure mirrors a KPI the repo actually computes (`saleskpi/metrics.py`,
`saleskpi/spend.py`, `saleskpi/forecast.py`), so each one can be cross-checked
against `kpi_headline.csv` and `deliverables/management_report.md`. The ratio
measures return fractions — format them as **Percentage** in Power BI (e.g.
`OTIF %` shows 84.99% at the grand total, matching `otif_pct` in the headline
table). I group them into an empty `_Measures` table (Home → Enter Data) so
they are easy to find, but any home table works.

---

## 1. Total Revenue

```DAX
Total Revenue =
-- Net invoiced revenue (after discount), the engine's headline revenue_eur.
SUM ( fact_sales_monthly[revenue_eur] )
```

## 2. Gross Margin EUR

```DAX
Gross Margin EUR =
-- Revenue minus COGS, pre-aggregated per cell as margin_eur (metrics.kpi_summary).
SUM ( fact_sales_monthly[margin_eur] )
```

## 3. Gross Margin %

```DAX
Gross Margin % =
-- Margin over revenue; DIVIDE gives safe BLANK on empty filter contexts.
DIVIDE ( [Gross Margin EUR], [Total Revenue] )
```

## 4. Avg Order Value

```DAX
Avg Order Value =
-- Revenue per order line (aov_eur in the KPI engine).
DIVIDE ( [Total Revenue], SUM ( fact_sales_monthly[orders] ) )
```

## 5. Revenue YoY %

```DAX
Revenue YoY % =
-- Same-period-last-year growth; needs dim_date marked as a date table.
VAR _prior =
    CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -12, MONTH ) )
RETURN
    DIVIDE ( [Total Revenue] - _prior, _prior )
```

## 6. OTIF %

```DAX
OTIF % =
-- On-Time-In-Full: orders delivered on time AND complete, over all orders.
DIVIDE (
    SUM ( fact_sales_monthly[otif_orders] ),
    SUM ( fact_sales_monthly[orders] )
)
```

## 7. Discount Leakage %

```DAX
Discount Leakage % =
-- Money given away versus list price: (list value - revenue) / list value (spend.py).
VAR _list = SUM ( fact_sales_monthly[list_value_eur] )
RETURN
    DIVIDE ( _list - [Total Revenue], _list )
```

## 8. Returns Rate %

```DAX
Returns Rate % =
-- Share of orders that came back (returns_rate_pct in the KPI engine).
DIVIDE (
    SUM ( fact_sales_monthly[returned_orders] ),
    SUM ( fact_sales_monthly[orders] )
)
```

## 9. Forecast CV-MASE

```DAX
Forecast CV-MASE =
-- Rolling-origin CV error of the selected revenue model (forecast.py); < 1 beats seasonal-naive.
CALCULATE (
    SUM ( kpi_headline[value] ),
    kpi_headline[metric] = "forecast_cv_mase"
)
```

## 10. Forecast Beats Naive

```DAX
Forecast Beats Naive =
-- Honest model check: on the current seeded data the CV picks seasonal_naive itself, so this reads "No".
VAR _naive =
    CALCULATE (
        SUM ( kpi_headline[value] ),
        kpi_headline[metric] = "seasonal_naive_cv_mase"
    )
RETURN
    IF ( [Forecast CV-MASE] < _naive, "Yes", "No" )
```

## 11. Next-Quarter Forecast Revenue

```DAX
Next-Quarter Forecast Revenue =
-- Sum of the 3 forecast months written by select_and_forecast (horizon = 3).
CALCULATE (
    SUM ( kpi_headline[value] ),
    kpi_headline[metric]
        IN { "forecast_revenue_m1", "forecast_revenue_m2", "forecast_revenue_m3" }
)
```

## 12. Top-20% Customer Share

```DAX
Top-20% Customer Share =
-- Pareto concentration: revenue share of the top 20% of customers (metrics.concentration). Format as %.
DIVIDE (
    CALCULATE (
        SUM ( kpi_headline[value] ),
        kpi_headline[metric] = "top20_customer_share_pct"
    ),
    100
)
```

---

### Notes on correctness

- `DIVIDE` is used everywhere instead of `/` for safe BLANK handling on a zero
  denominator.
- `Revenue YoY %` requires **Mark as date table** on `dim_date[date]`
  (month-start dates, 24 actual months + 3 forecast months). At the all-time
  grand total the 24-month window reproduces the engine's `yoy_pct` shape only
  when sliced to the last 12 months — the exact 12m-vs-prior-12m figure
  (`6.84%`) is also available directly as `kpi_headline[yoy_pct]`.
- The margin-bridge scalars (`bridge_price_effect_eur`,
  `bridge_volume_effect_eur`, `bridge_mix_effect_eur`,
  `bridge_total_change_eur`) are read straight off `kpi_headline` with the same
  `CALCULATE` + metric-name filter pattern as measures 9-12 — used by the
  waterfall on report page 2.
- `kpi_headline` is intentionally disconnected (no relationship): it holds
  repo-level scalars that have no month/region/category/channel grain, so they
  must not be filtered by slicers.
