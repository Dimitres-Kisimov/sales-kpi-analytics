# Business case — Sales & Demand Analytics

*An enterprise-framed read of the same toolkit the rest of this repo builds. The
distributor below is an illustrative scenario; every headline metric is measured
by the pipeline on the generated dataset (`deliverables/analysis.json` /
`management_report.md`) and estimates are labelled where they are estimates.*

## Situation

**Meridian Handel GmbH** (fictional, but drawn to type) is a B2B wholesale / MRO
distributor: five regions, ~400 active customers, 24 months of order history,
power tools as the core range. On the modelled year it turns over **€21.8M**
revenue (**+6.8% YoY**) at a **22.0%** gross margin (**€4.8M**). Leadership meets
quarterly and asks the same thing every time: *what changed, and what do we do
about it* — not "show me another dashboard."

Today the answer takes a data analyst a week of spreadsheet work per quarter, and
still arrives as description rather than decisions: a revenue chart, a margin
number, a customer list. The questions that actually move money — is growth being
bought with discounts? where is capital tied up in slow, erratic stock? which
customers are quietly leaving? — get asked but rarely get answered with arithmetic
that ties out.

## Problem (quantified)

Four measurable gaps in the current, report-by-hand process.

**1. Discount leakage is unmanaged.** Measured leakage is **€2,614,903/year —
10.7% of the €24,449,996 list value** given away versus list price. It's real
money and nobody owns the number. *Illustrative recovery:* clawing back just **one
percentage point** of that 10.7% ≈ **€244,500/year** (1% × €24.45M list — a
scenario, not a measured result), which alone dwarfs the analyst-time cost below.

**2. "Is growth healthy?" is answered by opinion, not decomposition.** Revenue is
up 6.8% but margin % is flat, so the reflex worry is discounting. The measured
margin bridge settles it: of the **+€191,624** YoY margin change, **volume added
+€178,052**, **price +€13,573**, **mix ≈ €0** — growth came from genuinely selling
more at stable unit economics. Without the bridge, that's a quarter of anxious
guessing.

**3. Churn is reported as a count, not worked as a list.** **158 of 395**
customers are At-risk / Churned. At an average **€21.8M / 395 ≈ €55,000** revenue
per customer, winning back even **10** of them ≈ **€550,000/year** (illustrative,
assumes recovered accounts return to average spend). And the **top 20% of
customers drive 56% of revenue** — a concentration risk worth naming out loud.

**4. Analyst process cost (illustrative, assumptions stated).** Assume **1 analyst
× 5 days per quarter** assembling the QBR by hand = **~160 hours/year**; at a
fully-loaded **€70/hour** ≈ **€11,200/year** — spent producing description that
this toolkit produces in one command, freeing that time for the recovery levers
above. (Stated assumption for scale, not a measured figure.)

## Solution

`python -m saleskpi --deliverables` runs the whole pipeline on the order data and
emits a decision-ready pack. The analytics core is deliberately **pure Python
standard library** (MASE, Croston's, Holt-Winters written from scratch); `openpyxl`
and `matplotlib` are the only third-party packages, and only for the Excel/PDF
outputs. It produces:

- **KPI scorecard** — revenue, margin, OTIF/fill/returns, AOV, discount leakage.
- **Margin bridge** — price / volume / mix reconciled to the total to the cent (a
  test enforces `price + volume + mix == total`).
- **ABC-XYZ portfolio** — revenue concentration × demand steadiness, so the
  erratic long tail is separated from the steady core.
- **RFM segmentation** — Champions … At-risk / Churned, with the named win-back
  list.
- **Demand forecast** — chosen by rolling-origin cross-validation, scored with
  MASE, the CV-MASE printed next to every model.
- **Replenishment buy-list** — region × category cells below reorder point, with
  order quantities from safety stock at per-ABC service levels.
- **Decision cards** — the above reduced to a handful of actions for the quarter.

## Impact / ROI (measured on the generated dataset)

The toolkit turns a week of spreadsheet work into one command and surfaces the
levers above with arithmetic that ties out:

| Signal | Measured value |
|---|--:|
| Revenue / YoY | €21.8M / +6.8% |
| Gross margin | 22.0% (€4.8M) |
| Discount leakage | €2,614,903 (10.7% of list) |
| Margin bridge (YoY) | +€191,624 (volume +€178,052, price +€13,573, mix ≈€0) |
| At-risk / churned customers | 158 of 395 |
| Customer concentration | top 20% → 56% of revenue |
| Reorder cells flagged | 28 region×category cells |
| Modelled returns cost | €585,473 |

Against ~€11,200/year of analyst time replaced (illustrative), the value is the
**decisions the pack enables** — the €244k/1-point leakage-recovery scenario and
the €550k/10-account win-back scenario above are illustrative, but they run off
**measured** leakage and churn numbers, and each dwarfs the process cost.

**On the forecast, honestly:** on only 24 monthly points the seasonal-naive
baseline is brutally strong, so the selected model's **CV-MASE is 1.58 — above 1**,
and the toolkit prints that next to the forecast rather than hiding it. The
deliverable here is the *honest, auditable* evaluation (rolling-origin CV,
scale-free scoring), not a hero number; more history or SKU-level series is where
the smarter forecasters would earn their keep.

## Stakeholders & use case

Run at the **quarterly business review (QBR)**:

1. **Data/BI analyst** regenerates the data (or loads the real ledger) and runs
   `python -m saleskpi --deliverables` and `python scripts/make_presentation.py`.
2. **Commercial lead** reads the margin bridge and confirms growth is volume-led,
   not discount-bought.
3. **Pricing / margin owner** takes the €2.6M discount-leakage figure and the
   cost-to-serve-by-channel split as the leakage-recovery target.
4. **Sales manager** gets the *named* At-risk / Churned list for a win-back
   campaign — not a count, a list.
5. **Supply/inventory planner** works `reorder_list.csv` — the region×category
   buy-list at per-ABC service levels.
6. **Leadership** approves the quarter's actions from the **Recommended actions**
   slide of `executive_review.pdf`.

## Deliverable

Everything below is **already produced** by the pipeline — this business case
points to it, it does not recreate it:

- **`deliverables/executive_review.pdf`** / **`.pptx`** — the 8-slide Executive
  Business Review (title, KPI scorecard, revenue+forecast, margin bridge, ABC-XYZ,
  expenditure, RFM + at-risk callout, recommended actions).
- **`deliverables/management_report.md`** — the same QBR as a written report.
- **`deliverables/kpi_workbook.xlsx`** — multi-sheet Excel (KPIs, mix, ABC-XYZ,
  RFM, forecasts, reorder list, spend).
- **`deliverables/reorder_list.csv`** — the region×category buy-list.
- **`deliverables/analysis.json`** — everything, machine-readable (feeds the
  offline `web/index.html` dashboard).

## Honest notes

- **The data is 100% synthetic**, generated deterministically by
  `scripts/generate_data.py` — no real company or customer (details in
  [CREDITS.md](../CREDITS.md)).
- **Headline metrics are measured on that generated dataset** and regenerate on
  every run; the leakage-recovery and win-back € figures, and the analyst-time
  cost, are **illustrative scenarios / assumptions**, labelled as such above.
- **The forecast CV-MASE is above 1 (1.58) and the report says so** — on 24 points
  seasonal-naive is hard to beat; the point is the honest evaluation, not the
  number.
- **Returns cost is a model, not a measurement** (`rate × avg cost`), because the
  synthetic data doesn't carry restocking cost — labelled everywhere it appears.
