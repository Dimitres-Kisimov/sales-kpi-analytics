-- Discount-leakage WATERFALL (one row): gross list value -> within-policy
-- discounts -> excess discounts -> net revenue.
-- Mirrors the top-level fields of saleskpi.spend.leakage_drilldown(...)
-- (and saleskpi.spend.waterfall(...)), which drive both the SVG and the PNG.
--
-- Parameterized view: :policy_pct is the assumed sanctioned-discount ceiling as a
-- fraction of list (default 0.10 = 10%). Total leakage is independent of it; only
-- the within/excess split depends on it. Run with a bound parameter, e.g.
--   run_file(con, "leakage_waterfall.sql", {"policy_pct": 0.10})
--
-- The bars reconcile by construction:
--   gross_list_value - within_policy_discount - excess_discount = net_revenue
--   within_policy_discount + excess_discount                    = total_leakage
--
-- Persistent-DB form (bakes in the 10% default, since SQLite cannot bind a
-- parameter into a stored VIEW):
--   CREATE VIEW leakage_waterfall AS SELECT ... (replace :policy_pct with 0.10) ...
SELECT
    ROUND(SUM(units * list_price_eur), 2)                                 AS gross_list_value_eur,
    ROUND(SUM(units * list_price_eur - revenue_eur)
          - SUM(CASE WHEN discount_pct > :policy_pct AND discount_pct > 0
                     THEN (units * list_price_eur - revenue_eur)
                          * (discount_pct - :policy_pct) / discount_pct
                     ELSE 0 END), 2)                                       AS within_policy_discount_eur,
    ROUND(SUM(CASE WHEN discount_pct > :policy_pct AND discount_pct > 0
                   THEN (units * list_price_eur - revenue_eur)
                        * (discount_pct - :policy_pct) / discount_pct
                   ELSE 0 END), 2)                                         AS excess_discount_eur,
    ROUND(SUM(revenue_eur), 2)                                            AS net_revenue_eur,
    ROUND(SUM(units * list_price_eur - revenue_eur), 2)                   AS total_leakage_eur
FROM sales;
