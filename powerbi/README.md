# Power BI pack — Sales KPI Analytics

This folder is a **Power BI Desktop showcase** built from the repo's own KPI
engine. It needs no Power BI tenant, licence, or gateway to *produce* — the
CSVs and the DAX are generated and written out here so the dimensional model
can be imported and reviewed. Honest framing: I don't ship a `.pbix` (that
needs the Desktop app to author), I ship the **star schema + DAX + a build
spec** so the modelling work is fully reproducible by anyone with Power BI
Desktop. The underlying dataset is the repo's committed, seeded **synthetic**
distributor dataset (24 months, ~15.2k orders) — every number here ties back
to `deliverables/management_report.md`.

## What's here

```
powerbi/
  build_star.py        aggregates data/sales_transactions.csv via saleskpi.*
  data/
    fact_sales_monthly.csv  grain = month x region x category x channel (~2.7k rows)
    dim_date.csv            24 actual months + 3 forecast months
    dim_region.csv          region attributes (reps, customers)
    dim_category.csv        category attributes + the ABC-XYZ classification
    dim_channel.csv         channel attributes + the cost-to-serve model
    kpi_headline.csv        disconnected (metric, value) repo-level scalars
  DAX_measures.md      the KPIs as real, paste-ready DAX
  README.md            this file
```

Regenerate any time (deterministic — the generator is seeded):

```bash
python scripts/generate_data.py   # optional; data/sales_transactions.csv is committed
python powerbi/build_star.py      # writes powerbi/data/*.csv
```

## The model (star schema)

```
   +--------------+          +----------------+          +---------------+
   |  dim_region  |          |    dim_date    |          |  dim_channel  |
   | region (PK)  |          | date_key (PK)  |          | channel (PK)  |
   +------+-------+          +--------+-------+          +-------+-------+
          | 1                         | 1                        | 1
          | *                         | *                        | *
          |            +--------------v---------------+         |
          +------------>      fact_sales_monthly      <---------+
                       |  date_key / region /         |
                       |  product_category / channel  |
                       |  orders units revenue_eur    |
                       |  cost_eur margin_eur ...     |
                       +--------------^---------------+
                                      | *
                                      | 1
                          +-----------+------------+
                          |     dim_category       |
                          | product_category (PK)  |
                          | abc / xyz / class ...   |
                          +------------------------+

   kpi_headline  (disconnected — repo-level scalars, read by metric name)
```

## Import steps (Power BI Desktop)

1. **Get Data → Text/CSV** and load all six files from `powerbi/data/`.
   Accept the auto-detected types; set `date_key` to Whole Number and
   `dim_date[date]` to Date.
2. **Model view → create relationships** (all single-direction, one-to-many
   from the dim to the fact):
   - `dim_date[date_key]` 1 — * `fact_sales_monthly[date_key]`
   - `dim_region[region]` 1 — * `fact_sales_monthly[region]`
   - `dim_category[product_category]` 1 — * `fact_sales_monthly[product_category]`
   - `dim_channel[channel]` 1 — * `fact_sales_monthly[channel]`
   - leave `kpi_headline` disconnected (no relationship).
   - Mark `dim_date` as a date table (Table tools → Mark as date table →
     `dim_date[date]`) so `DATEADD` time intelligence works.
3. **Add the measures** from `DAX_measures.md` (create an empty `_Measures`
   table to home them, then paste each measure).

## Report pages to build

### Page 1 — Executive Overview
- KPI cards: **Total Revenue**, **Gross Margin %**, **Revenue YoY %**,
  **OTIF %**, **Next-Quarter Forecast Revenue**.
- **Revenue trend** (line/column): `Total Revenue` by `dim_date[date]` — the
  3 forecast months carry no fact rows, so the actual line simply stops; put
  the forecast in the card (or a small `kpi_headline` table visual of the
  `forecast_revenue_m1..m3` rows).
- **Region donut**: `Total Revenue` by `dim_region[region]`.
- **Concentration card**: `Top-20% Customer Share` (55.8% on the seeded data)
  as the risk callout.

### Page 2 — Commercial Mix & Margin
- **Matrix**: rows `dim_region[region]`, columns `dim_category[product_category]`,
  values `Total Revenue`, `Gross Margin %`.
- **Margin bridge waterfall**: build from the `kpi_headline` rows
  `bridge_price_effect_eur` / `bridge_volume_effect_eur` /
  `bridge_mix_effect_eur` (breakdown of `bridge_total_change_eur`, the
  price/volume/mix decomposition from `metrics.margin_bridge`).
- **Portfolio table**: `dim_category` with `abc_xyz_class`, `demand_cv`,
  `revenue_share_pct` — the ABC × XYZ classification, plus `Gross Margin %`.
- **Discount leakage bar**: `Discount Leakage %` by `dim_channel[channel]`
  (card: overall leakage vs list value).

### Page 3 — Service & Cost-to-Serve
- **OTIF trend** (line): `OTIF %` by `dim_date[date]` with a constant line at
  the 90% service bar (peak-season months dip — that is in the data).
- **Service by channel** (clustered bar): `OTIF %` and `Returns Rate %` by
  `dim_channel[channel]`.
- **Cost-to-serve stacked bar**: `dim_channel` columns `cogs_eur`,
  `returns_cost_eur`, `discount_leakage_eur` — the spend.py cost-to-serve
  model per channel.
- **Forecast cards**: `Forecast CV-MASE` and `Forecast Beats Naive` — honest
  readout: on the seeded data the cross-validation selects `seasonal_naive`
  itself (CV-MASE 1.578), so the check reads "No"; the point is the
  out-of-sample selection harness, not a leaderboard win.

## Why this demonstrates Power BI ability without a tenant

Everything a reviewer needs to judge dimensional-modelling and DAX skill is
here in text: a normalized star (one fact + four conformed dimensions + a
disconnected scalar table), single-direction relationships, a marked date
table, and measures that use `CALCULATE`, `DIVIDE`, variables, an `IN` set
filter, and a `DATEADD` time-intelligence pattern. Loading the six CSVs and
pasting the DAX reproduces the whole model in a few minutes — no licence
required.

Author: Dimitres Kisimov.
