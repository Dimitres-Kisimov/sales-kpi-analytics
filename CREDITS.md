# Credits & data provenance

## Data is synthetic
The dataset in `data/sales_transactions.csv` is **100% synthetic**. It is
generated deterministically (fixed random seed) by `scripts/generate_data.py`.
No real company, customer, order, employee, or price is represented, and no
proprietary or confidential source was used. Regions, sales reps, customer IDs
and segments are fabricated.

The generator models a plausible B2B wholesale/MRO distributor: ~24 months of
orders with seasonality (spring/autumn peaks typical of construction supply), a
gentle upward trend, per-category margins, a stable customer base (so RFM and
retention are meaningful), discount leakage, delivery performance (OTIF) and
returns. It exists so the analytics can be demonstrated end-to-end without any
real, sensitive data.

## Methods & references
The forecasting and inventory methods are standard, published techniques:

- **MASE** — Hyndman & Koehler (2006), *Another look at measures of forecast
  accuracy*.
- **Rolling-origin / walk-forward evaluation** — Hyndman & Athanasopoulos,
  *Forecasting: Principles and Practice* (FPP3), §5.10.
- **Croston's method** — Croston (1972); **SBA bias correction** —
  Syntetos & Boylan (2005).
- **ADI / CV² demand classification** — Syntetos, Boylan & Croston (2005).
- **ABC-XYZ classification**, **RFM segmentation**, **price/volume/mix margin
  bridge**, and the **safety-stock / reorder-point** formulas are classic
  operations-management and commercial-analytics conventions.

## Author
Built by **Dimitres Kisimov** as a portfolio project. © 2026 Dimitres Kisimov,
all rights reserved (see [LICENSE](LICENSE)).
