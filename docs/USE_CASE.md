# Use case — a quarterly business review, end to end

This walks through the story the toolkit tells on the generated data, the way I'd
present it in an actual QBR. Every number below comes straight out of
`deliverables/analysis.json` (and the figures land in `executive_review.pdf`), so
you can regenerate and check it.

The setup: a B2B wholesale/MRO distributor, five regions, ~400 active customers,
24 months of orders. Leadership wants to know *what changed and what to do about
it* — not another dashboard to admire.

---

## 1. Revenue is up, but margin is flat — why?

Revenue is **€21.8M**, up **+6.8% YoY**. Good. But gross margin is sitting at
**~22.0%**, roughly where it was. If revenue grew and margin % didn't move, the
obvious worry is that we "bought" the growth with discounts.

The **margin bridge** settles it. Decomposing the YoY margin change into price /
volume / mix:

- **Volume** added the lion's share (**+€178k**) — we genuinely sold more.
- **Price** was a small positive (**+€14k**) — no evidence of margin being
  discounted away.
- **Mix** was essentially flat.

So the margin story is healthy: growth came from volume at stable unit
economics, not from buying revenue. That's the first slide of the QBR, and it
turns a nagging worry into a clear "we're fine, here's the proof."

Where it *isn't* free: **discount leakage** is running at a few percent of list
value (see the expenditure section of the report), and that's the lever to watch
if volume growth ever starts leaning on price.

---

## 2. Where the money is — and where it's tied up

The **ABC-XYZ** grid splits the catalogue two ways at once — revenue
concentration (A/B/C) and demand steadiness (X/Y/Z):

- The **AX** categories (large, steady — power tools lead) are the core. They
  earn a high service level (98%) and automated replenishment.
- The **C** and **Z** tail ties up working capital for little return. The
  decision card spells it out: move erratic long-tail categories to min-stock or
  make-to-order rather than holding safety stock against noise.

The **reorder list** (`reorder_list.csv`) operationalises this: region × category
cells at or below their reorder point, with recommended order quantities computed
from safety stock at the per-ABC service level. It's a buy-list, not a chart.

---

## 3. Customers — protect the base, win back the quiet ones

**RFM** segments the ~400 customers. Two segments drive the QBR action:

- **Champions** and **Loyal / high-value** are the revenue engine — and the
  concentration metric shows the **top 20% of customers drive ~56% of revenue**.
  That's a concentration risk worth naming out loud: losing a handful of big
  accounts hurts disproportionately.
- **At risk + Churned/dormant** is the win-back list — customers who used to buy
  and have gone quiet. The exec review calls out the count directly and the intent
  is concrete: hand the *named* list to sales for a win-back campaign, don't just
  report a number.

---

## 4. Can we trust the forecast?

The revenue forecast is chosen by **rolling-origin cross-validation**, scored with
**MASE**, and the report states the CV-MASE next to the model name every time. On
this short 24-month series the seasonal-naive baseline is genuinely hard to beat,
so the reported CV-MASE sits **above 1** — and the toolkit says so rather than
hiding it. That honesty is the point: a forecast you can audit beats a
confident-looking line you can't. (More history, or SKU-level series, is where the
smarter models start to earn their MASE — see the README's "what I'd add next".)

---

## 5. What leadership walks away with

`python scripts/make_presentation.py` turns all of the above into
`deliverables/executive_review.pdf` (and a `.pptx` if `python-pptx` is installed):
a title slide, a KPI scorecard, the revenue + forecast trend, the margin bridge,
the ABC-XYZ portfolio, the expenditure breakdown, the RFM segments with the
at-risk callout, and a closing **Recommended actions** slide built from the
decision cards.

That last slide is the whole point of the exercise — raw order data reduced to a
handful of decisions someone can act on this quarter:

1. Growth is healthy (volume, not discounting) — keep pushing the AX core.
2. Trim working capital on the erratic long tail.
3. Work the named at-risk customer list before they're gone.
4. Watch customer concentration and discount leakage.
5. Treat the forecast as a validated estimate, and report its MASE honestly.
