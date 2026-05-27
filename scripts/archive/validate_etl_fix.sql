-- ETL 渠道错标修复验证 SQL
-- 跑完 --full 后执行，确认 U先/百补/赠品/达播 不再误入淘客

-- 1. 淘客订单中是否还有小样/U先/赠品/<¥4（应为0）
SELECT '淘客中含小样/U先/赠品/<¥4' AS check_item,
       COUNT(*) AS cnt
FROM orders
WHERE channel = '淘客'
  AND (
      spu_type LIKE '%小样%'
      OR product_title ILIKE '%u先%'
      OR product_title ILIKE '%赠品%'
      OR actual_amount < 4
  );

-- 2. 淘客订单中是否还有达播关键词（应为0或极少）
SELECT '淘客中含达播关键词' AS check_item,
       COUNT(*) AS cnt
FROM orders
WHERE channel = '淘客'
  AND (
      product_title ILIKE '%达人%'
      OR product_title ILIKE '%直播%'
      OR product_title ILIKE '%主播%'
  );

-- 3. 621593460622 的渠道分布（2025年9月前后应该不同）
SELECT channel,
       COUNT(*) AS cnt,
       MIN(pay_time) AS min_time,
       MAX(pay_time) AS max_time
FROM orders
WHERE product_id = '621593460622'
GROUP BY channel
ORDER BY cnt DESC;

-- 4. 各渠道订单数汇总
SELECT channel, COUNT(*) AS cnt
FROM orders
GROUP BY channel
ORDER BY cnt DESC;

-- 5. 2025年9月后 621593460622 是否标记为货架（正装→货架）
SELECT channel, COUNT(*) AS cnt
FROM orders
WHERE product_id = '621593460622'
  AND pay_time >= '2025-09-17'
GROUP BY channel;
