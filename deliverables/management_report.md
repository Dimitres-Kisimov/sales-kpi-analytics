# Quarterly Business Review — Sales & Demand Analytics

*Auto-generated from 24 months of order data. Author: Dimitres Kisimov.*

## 1. Headline KPIs
- Revenue: **21,835,094 EUR** (+6.8% YoY)
- Gross margin: **22.0%** (4,800,417 EUR)
- Orders: 15,217 · AOV: 1,435 EUR · Active customers: 395
- Service: OTIF 85% · on-time 89% · fill rate 96% · returns 3.4%
- Discount leakage: 10.7% of list value

## 2. What the numbers say (decision cards)
- Pacing to plan (FY2025, as of 2025-09, 9/12 mo): projected 10,911,670 EUR = 96% of the 11,400,851 EUR plan (8% assumed) - behind plan — at risk; 80% interval 94-97% of plan (gap -489,181 EUR). Modelled projection, not a guarantee.
- KPI exception monitor: 6 out-of-control month(s) (6 unfavourable) on OTIF % vs robust 3.5-sigma control limits - worst OTIF % 79.04% at 2025-09 (modified z -6.1); 4 monitored KPIs in control.
- Revenue bridge (YoY): Revenue rose €722,407 year-on-year: price +€16,048, volume +€1,381,732, mix −€675,373. Volume was the biggest tailwind (+1,381,732 EUR); mix the biggest drag (-675,373 EUR).
- Discount drill-down: Berg (Nordics) leads the leakage table - 268,810 EUR vs list, 75,779 EUR of it above the 10% policy assumption - review discount authority there first.
- Revenue is up 6.8% YoY; gross margin sits at 22.0%.
- Margin bridge: volume added 178,052 EUR while mix cost 0 EUR - steer commercial focus accordingly.
- 158 customers are At-risk/Churned (of 395); hand the named list to sales for win-back.
- Top-20% of customers drive 56% of revenue - concentration risk to monitor.
- Next-quarter revenue forecast (model: seasonal_naive, CV-MASE 1.58): 585,564, 682,396, 987,495 EUR.
- OTIF is 85% (below the 90% service bar) - investigate peak-month delivery reliability.

## 3. Revenue bridge — why did revenue move? (YoY, price / volume / mix)
- Revenue rose €722,407 year-on-year: price +€16,048, volume +€1,381,732, mix −€675,373.
- Prior 12m revenue: 10,556,343 EUR (2024-01..2024-12) → current 11,278,750 EUR (2025-01..2025-12) (**+722,407 EUR**, +6.8%; units +13.1%)
- Price effect: +16,048 EUR · Volume: +1,381,732 EUR · Mix: -675,373 EUR — the three sum to the total change by construction (mix is the residual).

| Category | Prior rev | Current rev | Price | Volume | Mix |
|---|--:|--:|--:|--:|--:|
| power tools | 8,209,736 | 8,615,980 | +21,806 | +1,074,582 | -690,144 |
| hand tools | 1,316,286 | 1,456,599 | +449 | +172,290 | -32,427 |
| chemicals | 526,344 | 634,846 | -2,901 | +68,894 | +42,510 |
| ppe | 285,150 | 325,920 | -3,375 | +37,324 | +6,820 |
| fasteners | 125,287 | 139,498 | -610 | +16,399 | -1,578 |
| abrasives | 93,541 | 105,908 | +678 | +12,244 | -555 |

*Realised price = revenue ÷ units per category; volume is proportional growth at the prior blended price, mix the reallocation across categories. See `pvm_bridge.csv` and `pvm_waterfall.svg`.*

## 4. Margin bridge (YoY, price / volume / mix)
- Prior 12m margin: 2,304,396 EUR → current 2,496,021 EUR (**+191,624 EUR**)
- Price effect: +13,573 EUR · Volume: +178,052 EUR · Mix: -0 EUR

## 5. Portfolio (ABC × XYZ)
| Category | Revenue | Share | Class | CV |
|---|--:|--:|:--:|--:|
| power tools | 16,825,715 | 77.1% | AX | 0.225 |
| hand tools | 2,772,885 | 12.7% | BX | 0.284 |
| chemicals | 1,161,190 | 5.3% | CX | 0.186 |
| ppe | 611,070 | 2.8% | CX | 0.199 |
| fasteners | 264,785 | 1.2% | CX | 0.165 |
| abrasives | 199,448 | 0.9% | CX | 0.247 |

## 6. Revenue forecast (next 3 months)
- Model selected by rolling-origin cross-validation: **seasonal_naive** (CV-MASE 1.58; <1 beats the seasonal-naive baseline)
- Forecast: 585,564, 682,396, 987,495 EUR

## 7. Replenishment — reorder now
- 28 region×category cells are at/below their reorder point.
  See `reorder_list.csv` for quantities (safety stock at per-ABC service levels).

## 8. Expenditure & spend
- Total COGS: **17,034,677 EUR** on 24,449,996 EUR of list value.
- Discount leakage: **2,614,903 EUR** (10.7% of list) given away versus list price.
- Modeled returns cost: 585,473 EUR.

| Channel | COGS | Returns cost | Discount leakage | Cost-to-serve |
|---|--:|--:|--:|--:|
| e-shop | 7,020,517 | 244,100 | 1,044,013 | 8,308,631 |
| field-sales | 4,997,452 | 186,012 | 786,435 | 5,969,900 |
| branch | 3,276,233 | 105,171 | 523,318 | 3,904,722 |
| phone | 1,740,475 | 49,860 | 261,136 | 2,051,471 |

### 8.1 Discount-leakage drill-down — who, where
Waterfall: gross list value 24,449,996 EUR − within-policy discounts 1,934,178 EUR − excess discounts 680,725 EUR = net revenue 21,835,094 EUR. Both discount cuts together are the 2,614,903 EUR leakage.

*Policy threshold: 10% of list — assumed sanctioned-discount ceiling (no contract terms in the dataset); within-policy vs excess split depends on it, the total leakage does not.*

Top 5 reps by excess-over-policy (see `leakage_waterfall.png`):

| Rep | Region | Leakage | Excess >policy | % of own revenue | Orders >policy | Median / p90 discount |
|---|---|--:|--:|--:|--:|--:|
| Berg | Nordics | 268,810 | 75,779 | 12.5% | 36% | 7.7% / 16.2% |
| Nowak | East | 292,292 | 73,368 | 11.9% | 29% | 7.0% / 14.8% |
| Martin | West | 255,726 | 67,365 | 12.6% | 35% | 7.7% / 15.8% |
| Braun | DACH-North | 193,020 | 61,165 | 13.4% | 38% | 7.9% / 16.3% |
| Lindqvist | Nordics | 227,293 | 58,971 | 12.2% | 34% | 7.2% / 15.4% |

| Region | Leakage | Excess >policy | % of region revenue | Orders >policy |
|---|--:|--:|--:|--:|
| DACH-South | 615,918 | 155,208 | 11.5% | 30% |
| DACH-North | 514,756 | 142,571 | 12.4% | 36% |
| Nordics | 496,103 | 134,751 | 12.3% | 35% |
| East | 522,793 | 130,203 | 11.7% | 30% |
| West | 465,333 | 117,992 | 12.2% | 33% |

## 9. KPI exceptions — statistical control monitor
- KPI monitor: 6 exceptions in 24 months — 6 unfavourable, 0 favourable (OTIF %); worst OTIF % at 2025-09 (79.04%, z=-6.1). 4 KPIs in control.
- Method: robust control chart (median ± k·MAD/0.6745, Iglewicz–Hoaglin modified z), k = 3.5; period 2024-01..2025-12 (24 months).
- Scope note: the monitored KPIs are the quality/service/commercial ratios plus AOV, where a monthly control chart is trustworthy. The strongly-seasonal volume series (revenue, orders) are intentionally excluded from level-anomaly detection on 24 points — their movement is covered by the out-of-sample forecast CV and the revenue bridge.

| KPI | Month | Value | Centre | Nearest limit | Modified z | Direction | Read | Severity |
|---|---|--:|--:|--:|--:|:--:|:--:|:--:|
| OTIF % | 2025-09 | 79.04% | 86.46% | 82.18% | -6.07 | below | unfavourable | severe |
| OTIF % | 2024-09 | 80.30% | 86.46% | 82.18% | -5.04 | below | unfavourable | elevated |
| OTIF % | 2025-10 | 80.46% | 86.46% | 82.18% | -4.91 | below | unfavourable | elevated |
| OTIF % | 2024-05 | 81.01% | 86.46% | 82.18% | -4.46 | below | unfavourable | elevated |
| OTIF % | 2024-10 | 81.52% | 86.46% | 82.18% | -4.04 | below | unfavourable | elevated |
| OTIF % | 2025-05 | 81.78% | 86.46% | 82.18% | -3.83 | below | unfavourable | elevated |

*In control this period: Gross margin %, Returns rate %, Discount leakage %, Average order value (no month outside its robust control limits). See `kpi_control_chart.svg`.*

## 10. Target attainment & run-rate to plan
- As of 2025-09 (Q3, 9/12 months), FY2025 is projected to land at €10,911,670 — 95.7% of the €11,400,851 plan (−€489,181); status: behind plan — at risk.
- Standing at **2025-09** (9 of 12 months of FY2025): YTD revenue **8,252,457 EUR** vs a seasonally-paced plan-to-date of 8,528,901 EUR (pace index 0.97; behind the plan curve by 276,444 EUR).
- Plan: **11,400,851 EUR** — *assumed* prior-FY revenue (10,556,343 EUR) × (1 + 8%); the dataset carries no budget, so attainment moves with this rate.
- Projection (model **seasonal_naive**, remaining 3 mo): full year lands at **10,911,670 EUR** = **95.7%** of plan (gap **-489,181 EUR**). Simple annualise-the-YTD run-rate for comparison: 11,003,276 EUR.
- 80% prediction interval: **10,769,899 – 11,053,441 EUR** (94.5–97.0% of plan), from the model's 9-fold walk-forward errors (sigma 63,869 EUR/mo, aggregated over the remaining months). A modelled band, not a guarantee.
- **Back-check** (the fiscal year is closed in this synthetic history): the realised full year was **11,278,750 EUR** (98.9% of plan) — **outside** the projected 80% interval, as ~1 year in 5 is expected to be, and here because the final quarter ran materially hotter than the prior year the seasonal-naive model repeats. See `pacing_bullet.svg`.

*Pacing is out-of-sample and honest: the projection uses the same rolling-origin-CV-selected forecaster as the rest of the toolkit, the interval is empirical, and the plan is a stated assumption. Synthetic data.*
