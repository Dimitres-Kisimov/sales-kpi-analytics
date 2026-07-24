-- Revenue, gross margin % and orders by region (last-12-months view is done in
-- the app; this is the all-time rollup used for the Python<->SQL cross-check).
SELECT
    region,
    ROUND(SUM(revenue_eur), 2)                              AS revenue_eur,
    ROUND(100.0 * SUM(revenue_eur - cost_eur)
                / NULLIF(SUM(revenue_eur), 0), 2)           AS margin_pct,
    COUNT(*)                                                AS orders
FROM sales
GROUP BY region
ORDER BY revenue_eur DESC;
