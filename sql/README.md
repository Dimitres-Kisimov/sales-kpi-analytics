# SQL views layer

Reference SQL for the KPI engine. There is no external database: the queries run
against an **in-memory SQLite** table `sales`, loaded from the synthetic
`data/sales_transactions.csv` by `saleskpi.sqlq.connect()` (one row per order).
Each `.sql` file is the body of a view — a plain `SELECT` you can either run
directly (`saleskpi.sqlq.run_file`) or wrap in `CREATE VIEW name AS …` on a live
database. They exist to mirror the Python metrics in SQL and to serve as a
drift-guard: tests assert the SQL and Python engines agree to the cent.

## Table schema (`sales`)

One row per order line, typed by `saleskpi.sqlq`:

| column | type | notes |
|---|---|---|
| `order_id`, `date`, `region`, `sales_rep`, `customer_id`, `customer_segment`, `product_category`, `channel` | TEXT | dimensions; `date` is `YYYY-MM-DD` |
| `units` | INTEGER | quantity |
| `list_price_eur`, `discount_pct`, `revenue_eur`, `cost_eur` | REAL | `discount_pct` is a fraction (0.13 = 13%) |
| `promised_lead_days`, `actual_lead_days`, `on_time`, `in_full`, `returned` | INTEGER | service / returns flags (0/1) |

## Parameterized views

The leakage views take a named parameter **`:policy_pct`** — the assumed
sanctioned-discount ceiling as a fraction of list (default `0.10` = 10%). It is a
**stated modeling assumption, not a contract term in the data**: the *total*
leakage is independent of it; only the within-policy vs excess split moves. Bind
it when you run the file:

```python
from saleskpi.sqlq import connect, run_file
con = connect()
run_file(con, "leakage_by_rep.sql", {"policy_pct": 0.10})
```

SQLite cannot bind a parameter into a *stored* `VIEW`, so each leakage file also
documents a persistent-DB `CREATE VIEW` form that bakes in the 10% default.

## View → Python metric map

| View (`.sql`) | Mirrors (Python) | Notes |
|---|---|---|
| `revenue_by_region.sql` | `saleskpi.metrics.by_dimension(rows, "region")` | all-time revenue, margin %, orders by region |
| `otif_by_channel.sql` | `saleskpi.metrics.kpi_summary` (OTIF / on-time / fill) per channel | service quality, sorted by OTIF |
| `leakage_by_rep.sql` | `saleskpi.spend.leakage_drilldown(...)["by_sales_rep"]` | leakage, excess-over-policy, within-policy, orders>policy, by rep (parameterized) |
| `leakage_by_region.sql` | `saleskpi.spend.leakage_drilldown(...)["by_region"]` | same decomposition, by region (parameterized) |
| `leakage_waterfall.sql` | top-level fields of `saleskpi.spend.leakage_drilldown` / `saleskpi.spend.waterfall` | one-row waterfall: gross → within → excess → net + total (parameterized) |

## Honest notes

- **Reference SQL, live SQLite.** These run for real against the in-memory table,
  not just on paper — but the "database" is the synthetic CSV loaded per session,
  not a production warehouse.
- **Definitions match the Python engine to the cent.** Leakage is
  `SUM(units*list_price_eur − revenue_eur)`; the excess split is
  `leak * (discount_pct − :policy_pct) / discount_pct` on rows above the ceiling,
  the same formula `saleskpi.spend._split_leakage` uses. Cross-check tests fail if
  the two ever drift.
- **Rounding.** Each group's figures are rounded to the cent independently, so a
  sum of the *displayed* group values can differ from the total by a cent or two;
  the underlying (unrounded) decomposition reconciles exactly.
