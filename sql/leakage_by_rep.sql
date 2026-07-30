-- Discount-leakage drill-down BY SALES REP.
-- Mirrors saleskpi.spend.leakage_drilldown(...)["by_sales_rep"].
--
-- Parameterized view: :policy_pct is the assumed sanctioned-discount ceiling as a
-- fraction of list (default 0.10 = 10%). It is a stated modeling assumption, not a
-- contract term in the data — the total leakage does NOT depend on it, only the
-- within-policy vs excess split does. Run with a bound parameter, e.g.
--   run_file(con, "leakage_by_rep.sql", {"policy_pct": 0.10})
--
-- Definitions match the Python engine exactly:
--   leakage    = SUM(units * list_price_eur - revenue_eur)         (list value vs revenue)
--   excess     = the part of each leaking row's discount above :policy_pct,
--                split proportionally: leak * (discount_pct - :policy_pct) / discount_pct
--   within     = leakage - excess
--
-- Persistent-DB form (bakes in the 10% default, since SQLite cannot bind a
-- parameter into a stored VIEW):
--   CREATE VIEW leakage_by_rep AS SELECT ... (replace :policy_pct with 0.10) ...
SELECT
    sales_rep,
    ROUND(SUM(units * list_price_eur - revenue_eur), 2)                    AS leakage_eur,
    ROUND(SUM(CASE WHEN discount_pct > :policy_pct AND discount_pct > 0
                   THEN (units * list_price_eur - revenue_eur)
                        * (discount_pct - :policy_pct) / discount_pct
                   ELSE 0 END), 2)                                         AS excess_eur,
    ROUND(SUM(units * list_price_eur - revenue_eur)
          - SUM(CASE WHEN discount_pct > :policy_pct AND discount_pct > 0
                     THEN (units * list_price_eur - revenue_eur)
                          * (discount_pct - :policy_pct) / discount_pct
                     ELSE 0 END), 2)                                       AS within_policy_eur,
    ROUND(SUM(revenue_eur), 2)                                            AS revenue_eur,
    COUNT(*)                                                              AS orders,
    ROUND(100.0 * SUM(CASE WHEN discount_pct > :policy_pct THEN 1 ELSE 0 END)
                / COUNT(*), 2)                                            AS orders_above_policy_pct
FROM sales
GROUP BY sales_rep
ORDER BY excess_eur DESC, sales_rep;
