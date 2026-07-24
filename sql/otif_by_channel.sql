-- Service quality by channel: OTIF (on-time AND in-full), on-time %, fill rate.
SELECT
    channel,
    COUNT(*)                                               AS orders,
    ROUND(100.0 * SUM(CASE WHEN on_time = 1 AND in_full = 1
                           THEN 1 ELSE 0 END) / COUNT(*), 1) AS otif_pct,
    ROUND(100.0 * SUM(on_time) / COUNT(*), 1)               AS on_time_pct,
    ROUND(100.0 * SUM(in_full) / COUNT(*), 1)               AS fill_rate_pct
FROM sales
GROUP BY channel
ORDER BY otif_pct DESC;
