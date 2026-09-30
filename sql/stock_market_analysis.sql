-- Stock market analysis queries (SQLite); dates use ISO YYYY-MM-DD.

-- 1. Dataset coverage
SELECT company, COUNT(*) AS trading_days, MIN(date) AS first_date, MAX(date) AS last_date
FROM stock_prices GROUP BY company ORDER BY company;

-- 2. Return from first to last available observation
WITH ranked AS (
  SELECT company, date, close_price,
         ROW_NUMBER() OVER (PARTITION BY company ORDER BY date) AS first_row,
         ROW_NUMBER() OVER (PARTITION BY company ORDER BY date DESC) AS last_row
  FROM stock_prices
)
SELECT f.company, f.date AS first_date, f.close_price AS first_close,
       l.date AS last_date, l.close_price AS last_close,
       ROUND(100.0 * (l.close_price-f.close_price)/NULLIF(f.close_price,0),2) AS return_pct
FROM ranked f JOIN ranked l ON l.company=f.company
WHERE f.first_row=1 AND l.last_row=1 ORDER BY return_pct DESC;

-- 3. Trading activity
SELECT company, ROUND(AVG(turnover),2) AS avg_turnover,
       ROUND(AVG(shares_traded),2) AS avg_shares_traded
FROM stock_prices GROUP BY company ORDER BY avg_turnover DESC;

-- 4. Largest absolute daily price moves
SELECT company, date, open_price, close_price,
       ROUND(100.0*(close_price-open_price)/NULLIF(open_price,0),2) AS daily_move_pct
FROM stock_prices WHERE open_price IS NOT NULL AND close_price IS NOT NULL
ORDER BY ABS(daily_move_pct) DESC LIMIT 20;

-- 5. Monthly average close
SELECT company, substr(date,1,7) AS month, ROUND(AVG(close_price),2) AS avg_close
FROM stock_prices GROUP BY company, substr(date,1,7) ORDER BY company, month;

-- 6. Delivery ratio
SELECT company, ROUND(AVG(deliverable_pct),2) AS avg_delivery_pct,
       ROUND(AVG(trades),0) AS avg_daily_trades
FROM stock_prices GROUP BY company ORDER BY avg_delivery_pct DESC;
