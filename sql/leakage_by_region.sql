-- Discount-leakage drill-down BY REGION.
-- Mirrors saleskpi.spend.leakage_drilldown(...)["by_region"].
--
-- Parameterized view: :policy_pct is the assumed sanctioned-discount ceiling as a
-- fraction of list (default 0.10 = 10%) — a stated modeling assumption, not a
-- contract term. Total leakage is independent of it; only the within/excess split
-- moves. Run with a bound parameter, e.g.
--   run_file(con, "leakage_by_region.sql", {"policy_pct": 0.10})
--
-- Definitions match the Python engine exactly (see leakage_by_rep.sql for the
-- leakage / excess / within formulas). Regions here reconcile to the same grand
-- total as the by-rep view and as the headline discount_leakage() figure.
--
-- Persistent-DB form (bakes in the 10% default, since SQLite cannot bind a
-- parameter into a stored VIEW):
--   CREATE VIEW leakage_by_region AS SELECT ... (replace :policy_pct with 0.10) ...
SELECT
    region,
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
GROUP BY region
ORDER BY excess_eur DESC, region;
