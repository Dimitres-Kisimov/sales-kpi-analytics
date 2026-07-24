# Quarterly Business Review — Sales & Demand Analytics

*Auto-generated from 24 months of order data. Author: Dimitres Kisimov.*

## 1. Headline KPIs
- Revenue: **21,835,094 EUR** (+6.8% YoY)
- Gross margin: **22.0%** (4,800,417 EUR)
- Orders: 15,217 · AOV: 1,435 EUR · Active customers: 395
- Service: OTIF 85% · on-time 89% · fill rate 96% · returns 3.4%
- Discount leakage: 10.7% of list value

## 2. What the numbers say (decision cards)
- Revenue is up 6.8% YoY; gross margin sits at 22.0%.
- Margin bridge: volume added 178,052 EUR while mix cost 0 EUR - steer commercial focus accordingly.
- 158 customers are At-risk/Churned (of 395); hand the named list to sales for win-back.
- Top-20% of customers drive 56% of revenue - concentration risk to monitor.
- Next-quarter revenue forecast (model: seasonal_naive, CV-MASE 1.58): 585,564, 682,396, 987,495 EUR.
- OTIF is 85% (below the 90% service bar) - investigate peak-month delivery reliability.

## 3. Margin bridge (YoY, price / volume / mix)
- Prior 12m margin: 2,304,396 EUR → current 2,496,021 EUR (**+191,624 EUR**)
- Price effect: +13,573 EUR · Volume: +178,052 EUR · Mix: -0 EUR

## 4. Portfolio (ABC × XYZ)
| Category | Revenue | Share | Class | CV |
|---|--:|--:|:--:|--:|
| power tools | 16,825,715 | 77.1% | AX | 0.225 |
| hand tools | 2,772,885 | 12.7% | BX | 0.284 |
| chemicals | 1,161,190 | 5.3% | CX | 0.186 |
| ppe | 611,070 | 2.8% | CX | 0.199 |
| fasteners | 264,785 | 1.2% | CX | 0.165 |
| abrasives | 199,448 | 0.9% | CX | 0.247 |

## 5. Revenue forecast (next 3 months)
- Model selected by rolling-origin cross-validation: **seasonal_naive** (CV-MASE 1.58; <1 beats the seasonal-naive baseline)
- Forecast: 585,564, 682,396, 987,495 EUR

## 6. Replenishment — reorder now
- 28 region×category cells are at/below their reorder point.
  See `reorder_list.csv` for quantities (safety stock at per-ABC service levels).

## 7. Expenditure & spend
- Total COGS: **17,034,677 EUR** on 24,449,996 EUR of list value.
- Discount leakage: **2,614,903 EUR** (10.7% of list) given away versus list price.
- Modeled returns cost: 585,473 EUR.

| Channel | COGS | Returns cost | Discount leakage | Cost-to-serve |
|---|--:|--:|--:|--:|
| e-shop | 7,020,517 | 244,100 | 1,044,013 | 8,308,631 |
| field-sales | 4,997,452 | 186,012 | 786,435 | 5,969,900 |
| branch | 3,276,233 | 105,171 | 523,318 | 3,904,722 |
| phone | 1,740,475 | 49,860 | 261,136 | 2,051,471 |
