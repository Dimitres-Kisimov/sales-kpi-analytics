# Methodology

Every formula the toolkit uses, and why it's the right one. Where a method has a
tunable cutoff, I say so and give the convention I picked — none of these are
laws of nature.

---

## Headline KPIs

Standard commercial definitions, computed straight from the order table:

- **Revenue** = Σ `revenue_eur`. **COGS** = Σ `cost_eur`. **Gross margin** =
  revenue − COGS; **margin %** = margin / revenue.
- **AOV** (average order value) = revenue / orders.
- **Discount leakage** = (Σ `units`·`list_price` − revenue) / (Σ `units`·`list_price`)
  — the share of list value given away in discounts. This is the single most
  actionable commercial-quality metric for a distributor.
- **OTIF** (on-time-in-full) = orders that are *both* on-time and in-full ÷ orders.
  On-time %, fill rate and returns rate are the same idea on their own flags.
- **Growth**: **YoY** compares the last 12 months to the prior 12; **MoM** is the
  latest month vs the one before. YoY needs 24 months of history to exist.

---

## ABC-XYZ portfolio classification

Two independent axes, combined into a 3×3 grid (AX … CZ).

- **ABC** — Pareto share of revenue. Rank entities by revenue, take the cumulative
  share, and cut: **A ≤ 80%**, **B ≤ 95%**, **C** the rest. These cuts (0.80 /
  0.95) are the textbook convention and are function arguments (`abc_cuts`), not
  hard-coded.
- **XYZ** — demand *variability*, measured by the coefficient of variation (CV =
  σ/μ) of the monthly demand series. **X < 0.5** (steady), **Y < 1.0**, **Z**
  erratic. Months with no demand count as zero so sparse items are penalised
  honestly. Cuts are the `xyz_cuts` argument.

Why it matters: an **AX** item (big, steady) deserves tight availability and
automated replenishment; a **CZ** item (small, erratic) ties up working capital
and belongs on make-to-order or min-stock.

---

## RFM customer segmentation

For each customer: **Recency** (days since last order — lower is better),
**Frequency** (order count), **Monetary** (total revenue). Each is scored **1–5**
by quintile rank, so scores are relative to *this* customer base. Segments are
rule-based on the R/F/M scores:

| Segment | Rule |
|---|---|
| Champions | R ≥ 4 and F ≥ 4 |
| Loyal / high-value | R ≥ 3 and M ≥ 4 |
| At risk | R ≤ 2 and F ≥ 3 (used to buy often, gone quiet) |
| Churned / dormant | R ≤ 2 |
| Developing | everyone else |

The quintile boundaries and the segment rules are conventions — plenty of teams
use a 1–4 scale or different thresholds. The *At risk* rule is the commercially
important one: previously-frequent buyers who've gone quiet are the win-back list.

---

## Margin bridge — price / volume / mix (PVM)

Decomposes the **YoY gross-margin change** into three effects, comparing the last
12 months to the prior 12, per category:

- **Price effect** = Σ (unit-margin_now − unit-margin_prior) · units_now — the
  change in per-unit margin, valued on current volume.
- **Volume effect** = Σ unit-margin_prior · (units_now − units_prior) — the volume
  change, valued at the old unit margin.
- **Mix effect** = total change − price − volume — the residual, i.e. the shift in
  *what* sold (toward higher- or lower-margin categories).

By construction **price + volume + mix = total margin change** exactly, which is
what the reconciliation test asserts. PVM is a standard FP&A/commercial bridge;
the exact split of "price vs mix" depends on the decomposition order, and this is
one common, defensible choice.

---

## Revenue bridge — price / volume / mix (PVM)

The margin bridge above answers *why did margin move*; the **revenue bridge**
(`saleskpi.pvm.revenue_bridge`) answers the sibling question every sales team
asks — *why did revenue move* — decomposing the **YoY revenue change** (last 12
months vs prior 12, per category) into three effects. Realised price per category
is `revenue ÷ units`; with `q` = units, `p` = realised price, subscript 0 = prior
and 1 = current, and **λ = total-units₁ / total-units₀** the overall volume-growth
factor:

- **Price effect** = Σ (p₁ − p₀) · q₁ — the change in realised price, valued on
  current volume.
- **Volume effect** = revenue₀ · (λ − 1) — *pure* proportional growth: what the top
  line would have done if every category had grown at the blended rate and prices
  and mix had held.
- **Mix effect** = total change − price − volume — the residual, which works out
  to exactly the textbook mix term Σ p₀ · (q₁ − λ·q₀): the reallocation of demand
  towards higher- or lower-priced categories.

The plain two-way "quantity effect", Σ (q₁ − q₀) · p₀, is here **split** into the
pure-volume and mix parts, so a shift in *what* sold (not just *how much*) is
visible on its own bar. By construction **price + volume + mix = current − prior
revenue** to the cent — a test asserts the identity exactly, and reads the euro
labels back off the rendered SVG to assert the picture equals the source. On this
synthetic data the walk is **+€722,407** (price +€16,048, volume +€1,381,732, mix
−€675,373): units grew 13% but the growth skewed toward lower-priced categories,
so mix is a genuine drag — precisely the kind of thing a two-way split hides.

*Caveat:* like every PVM decomposition, the split is sensitive to how categories
that appear in only one period are treated; here all six categories are present in
both periods, so that edge case doesn't arise. Deliverables: `pvm_bridge.csv`
(per-category, with a TOTAL row that ties out) and `pvm_waterfall.svg` / `.png`.

---

## Demand forecasting

### The models

`naive`, `seasonal_naive` (repeat last season), `moving_average`, `ses` (simple
exponential smoothing), `holt_winters` (additive triple ES), and `croston` /
`sba` for intermittent demand. Croston smooths demand *size* and *interval*
separately; **SBA** applies the Syntetos-Boylan bias correction (× (1 − α/2)).
None of these need a third-party library — they're a few lines of `statistics`
each.

### Why MASE

**MASE** (Mean Absolute Scaled Error) = MAE(model) ÷ in-sample MAE of the naive
baseline. It's the right accuracy metric here because it is:

- **Scale-free** — comparable across a €2M category and a 5-unit long-tail SKU.
- **Defined at zero demand** — MAPE divides by the actual and blows up on the
  zeros that dominate intermittent series; MASE doesn't.
- **Interpretable** — **MASE < 1 means you beat the naive baseline**, > 1 means you
  didn't. No ambiguity.

MAE, RMSE, MAPE and sMAPE are all implemented too, but MASE drives model
selection.

### Rolling-origin cross-validation

Models are *not* scored on the data they were fit on. `rolling_origin_cv` does an
expanding-window (walk-forward) backtest: fit on `y[:t]`, predict the next step,
roll `t` forward, average the errors across folds. This is the honest,
out-of-sample way to compare forecasters on a time series (Hyndman FPP3 §5.10) —
a single in-sample fit would just reward overfitting.

`select_and_forecast` backtests every candidate, ranks them by CV-MASE, and
forecasts the horizon with the winner refit on the full history. The leaderboard
is returned so you can see the margins, not just the winner.

### Demand classification

`demand_class` computes **ADI** (average inter-demand interval) and **CV²** of
non-zero demand sizes and routes each series to a Syntetos pattern — *smooth*,
*intermittent*, *erratic*, *lumpy* — using the standard cutoffs **ADI = 1.32** and
**CV² = 0.49**. That's what tells you a category should be on Croston/SBA rather
than exponential smoothing.

---

## Inventory — safety stock & reorder points

Classic statistical replenishment:

```
Safety stock (demand variability):     SS  = Z · σ_d · √L
Safety stock (demand + lead-time var): SS  = Z · √(L·σ_d² + d̄²·σ_L²)
Reorder point:                         ROP = d̄·L + SS
GMROI:                                 gross_margin_€ / avg_inventory_cost
```

**Z** is the service-level multiplier from the inverse normal CDF
(`statistics.NormalDist().inv_cdf`) — exact, stdlib, no lookup table. Service
level is set **per ABC class** (A → 98%, B → 95%, C → 90%) so working capital
follows value: you protect availability hardest where the revenue is. `reorder_recommendation`
turns a demand history + on-hand into an order-up-to quantity, flagging a reorder
when on-hand ≤ ROP.

---

## Expenditure & cost-to-serve

The spend side mirrors the revenue side:

- **COGS** by category / region / channel (a straight Σ `cost_eur`).
- **Discount leakage** = Σ (`units`·`list_price` − `revenue`) — money handed back
  vs list.
- **Returns cost** — a *modeled* figure, `returns_rate · avg_order_cost · orders`,
  because the dataset doesn't carry restocking/handling cost. It's a proxy, and
  I label it as one.
- **Cost-to-serve by channel** = COGS + returns cost + discount leakage — a rough
  but useful view of which channels are genuinely expensive to run.

---

## KPI exception monitor — robust statistical process control

The exception layer (`saleskpi.anomaly`) is the "what should I look at?" filter over
the monthly KPI series. Each series gets a **robust control chart**:

- **centre** = the median of the monthly values (not the mean).
- **scale**  = `MAD / 0.6745`, where MAD is the median absolute deviation. The
  constant 0.6745 = Φ⁻¹(0.75) rescales the MAD into a normal-consistent estimate of
  σ. This is the **Iglewicz–Hoaglin** modified-z estimator.
- **modified z** = `0.6745·(x − median) / MAD`; a month is an **exception** when
  `|modified z| > k`, with `k = 3.5` (their recommended cut-off).
- **control limits** = `centre ± k·MAD/0.6745`, so "flagged" and "outside the
  limits" are the same statement — a test enforces that they never disagree.

Why robust estimators rather than the classic mean ± 3σ chart: with the mean and the
standard deviation, a single out-of-control month inflates *both*, widening the
limits so the month can hide inside them (masking). The median and MAD don't move
when one point blows out, so the exception stays visible. Nothing is tuned to the
data — the estimator and the 3.5 threshold are the standard ones.

Each exception carries a **polarity** — `higher_is_better` (margin, OTIF),
`lower_is_better` (returns, discount leakage) or `neutral` (AOV) — so the monitor
separates "problems to fix" from "wins to bank" instead of just flagging movement.

**Scope, stated honestly.** The monitored KPIs are the quality/service/commercial
*ratios* plus AOV. The strongly-seasonal *volume* series (revenue, orders) are
deliberately **excluded** from level-anomaly detection: 24 monthly points are two
seasonal cycles, too few to estimate a per-month seasonal profile well enough to
avoid false alarms (a classical centred-moving-average decomposition produces
edge artefacts here), so revenue movement is left to the out-of-sample forecast CV
and the price/volume/mix bridge. A robust multiplicative seasonal-adjustment path
(`anomaly.deseasonalize`, median detrended ratio per position-in-cycle) exists and
is unit-tested — it removes a pure seasonal pattern with no false alarms and still
catches an injected shock — but the shipped KPI set uses the raw chart where it is
sound.

On the synthetic data this surfaces one causal, recurring exception: **OTIF drops
below its 82.18% lower limit in all six peak-demand months (every May / September /
October)**, worst September 2025 at 79.04% (modified z −6.07); the other four KPIs
stay in control. The control chart is rendered as an offline SVG whose centre,
limits and flagged values are read back and asserted equal to the source, the same
screen-equals-source discipline the leakage and PVM waterfalls use.

---

## SQL ↔ Python cross-check

The same revenue-by-region rollup is computed two ways — in Python
(`metrics.by_dimension`) and in SQL (`sql/revenue_by_region.sql` over in-memory
SQLite) — and a test asserts they agree to the cent. It's a cheap integrity check
that catches drift between the two engines, which is exactly the kind of bug that
otherwise ships silently.
