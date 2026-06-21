-- Sprint 60.3+ C+: CI e2e schema-only fixture
-- 来源: 2026-06-21 从 production DuckDB `duckdb_tables()/duckdb_indexes()/duckdb_views()/duckdb_sequences()` 导出
-- 用途: CI runner 无 production DB 时，给 backend 提供空表结构，让 UI smoke e2e 拿到合法空响应而非 500
-- 维护: 若 production schema 新增表/视图/索引，需重新导出并更新本文件

CREATE SEQUENCE seq_rfm_quarantine INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START 23 NO CYCLE;

CREATE TABLE campaign_schedule(id INTEGER PRIMARY KEY, "year" INTEGER, campaign_name VARCHAR, conversion_start DATE, conversion_end DATE, lock_start DATE, lock_end DATE, "source" VARCHAR DEFAULT('auto'));
CREATE TABLE category_churn_cache(category_name VARCHAR, "month" VARCHAR, total_users INTEGER, churned_users INTEGER, inter_churn INTEGER, silent_churn INTEGER, retained_users INTEGER, retention_rate DOUBLE, "churn去向_json" VARCHAR, generated_at TIMESTAMP, PRIMARY KEY(category_name, "month"));
CREATE TABLE daily_metrics(d DATE, order_count BIGINT, user_count BIGINT, gsv DECIMAL(38,2), member_user_count BIGINT, member_gsv DECIMAL(38,2));
CREATE TABLE daily_visitors(date DATE PRIMARY KEY, visitors BIGINT, new_members BIGINT, member_join_rate DOUBLE);
CREATE TABLE fact_rfm_long(date DATE, dimension_key VARCHAR, dimension_json JSON NOT NULL, user_count BIGINT NOT NULL, gmv DECIMAL(18,2), repurchase_count BIGINT, segment_id INTEGER DEFAULT(0) NOT NULL, "version" INTEGER, created_at TIMESTAMP DEFAULT(now()), PRIMARY KEY(date, dimension_key, "version"));
CREATE TABLE membership_mark(order_id VARCHAR PRIMARY KEY, is_member BOOLEAN DEFAULT(CAST('t' AS BOOLEAN)), loaded_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP));
CREATE TABLE monthly_metrics("year" INTEGER, "month" INTEGER, gmv DECIMAL(12,2), gsv DECIMAL(12,2), order_count INTEGER, gsv_order_count INTEGER, new_user_count INTEGER, old_user_count INTEGER, member_gmv DECIMAL(12,2), member_gsv DECIMAL(12,2), avg_order_value DECIMAL(10,2), PRIMARY KEY("year", "month"));
CREATE TABLE order_status_override(order_id VARCHAR PRIMARY KEY, latest_order_status VARCHAR, latest_is_refund BOOLEAN, override_date DATE);
CREATE TABLE orders(order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR, user_nickname VARCHAR, order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP, order_type VARCHAR, order_status VARCHAR, product_id VARCHAR, merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR, sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER, amount DECIMAL(12,2), refund_status VARCHAR, refund_amount DECIMAL(12,2), actual_amount DECIMAL(12,2), province VARCHAR, city VARCHAR, influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR, video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR, seller_note VARCHAR, "year" INTEGER, "month" INTEGER, is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR, spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR, spu_cosmetic VARCHAR, spu_spec VARCHAR, spu_hash VARCHAR, channel VARCHAR, is_goujinjin BOOLEAN DEFAULT(CAST('f' AS BOOLEAN)), is_refund BOOLEAN DEFAULT(CAST('f' AS BOOLEAN)));
CREATE TABLE rfm_analysis_cache(cache_key VARCHAR PRIMARY KEY, period VARCHAR, start_date VARCHAR, end_date VARCHAR, channel VARCHAR, metric_type VARCHAR, ex_channels VARCHAR, result_json VARCHAR, mtime_at_write VARCHAR, orders_count_at_write BIGINT, computed_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP));
CREATE TABLE rfm_quarantine(id INTEGER DEFAULT(nextval('seq_rfm_quarantine')) PRIMARY KEY, date DATE NOT NULL, failed_assertion VARCHAR NOT NULL, reason VARCHAR NOT NULL, raw_data JSON, created_at TIMESTAMP DEFAULT(now()));
CREATE TABLE rfm_query_cache("key" VARCHAR PRIMARY KEY, endpoint VARCHAR NOT NULL, params_hash VARCHAR NOT NULL, "value" JSON NOT NULL, expire_at TIMESTAMP NOT NULL, created_at TIMESTAMP NOT NULL);
CREATE TABLE user_first_purchase(user_id VARCHAR, first_pay_date DATE);
CREATE TABLE user_recency(user_id VARCHAR, last_pay_time TIMESTAMP, is_member BOOLEAN, recency_days BIGINT, total_orders BIGINT, total_amount DECIMAL(38,2));
CREATE TABLE user_rfm(user_id VARCHAR, user_nickname VARCHAR, analysis_date DATE, metric_type VARCHAR, lookback_days INTEGER, channel VARCHAR, recency_days INTEGER, frequency INTEGER, monetary DECIMAL(12,2), r_score INTEGER, f_score INTEGER, m_score INTEGER, rfm_tier VARCHAR, rfm_tier_en VARCHAR, segment_id INTEGER, first_order_date DATE, last_order_date DATE, created_at TIMESTAMP, is_member BOOLEAN DEFAULT(CAST('f' AS BOOLEAN)), PRIMARY KEY(user_id, analysis_date, metric_type, lookback_days, channel));
CREATE TABLE user_rfm_clean(user_id VARCHAR, user_nickname VARCHAR, analysis_date DATE, metric_type VARCHAR, lookback_days INTEGER, recency_days INTEGER, frequency INTEGER, monetary DECIMAL(12,2), r_score INTEGER, f_score INTEGER, m_score INTEGER, rfm_tier VARCHAR, rfm_tier_en VARCHAR, segment_id INTEGER, first_order_date DATE, last_order_date DATE, created_at TIMESTAMP, PRIMARY KEY(user_id, analysis_date, metric_type, lookback_days));

CREATE UNIQUE INDEX idx_fact_rfm_dkv ON fact_rfm_long(date, dimension_key, "version");
CREATE INDEX idx_orders_channel_member ON orders(channel, is_member);
CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time);
CREATE INDEX idx_orders_pay_channel_item ON orders(pay_time, channel, spu_product_class);
CREATE INDEX idx_orders_pay_time ON orders(pay_time);
CREATE INDEX idx_orders_product ON orders(product_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_year_month ON orders("year", "month");
CREATE INDEX idx_override_order_id ON order_status_override(order_id);
CREATE INDEX idx_rfm_analysis_cache_period ON rfm_analysis_cache(period, start_date, end_date, channel, metric_type);
CREATE INDEX idx_rfm_channel ON user_rfm(channel);
CREATE INDEX idx_rfm_date ON user_rfm(analysis_date, metric_type, lookback_days);
CREATE INDEX idx_rfm_tier ON user_rfm(rfm_tier);
CREATE INDEX idx_ur_recency ON user_recency(recency_days);

CREATE VIEW v_category_daily AS SELECT CAST(pay_time AS DATE) AS order_date, COALESCE(main."trim"(spu_product_subclass), '未知') AS category, count(DISTINCT user_id) AS user_count, count(DISTINCT order_id) AS order_count, sum(actual_amount) AS gsv, sum(CASE  WHEN (is_member) THEN (actual_amount) ELSE 0 END) AS member_gsv, count(DISTINCT CASE  WHEN (is_member) THEN (user_id) ELSE NULL END) AS member_count FROM orders WHERE ((is_goujinjin = CAST('f' AS BOOLEAN)) AND (order_status != '交易关闭') AND (is_refund = CAST('f' AS BOOLEAN))) GROUP BY CAST(pay_time AS DATE), COALESCE(main."trim"(spu_product_subclass), '未知');
CREATE VIEW v_order_with_user AS SELECT o.*, ufp.first_pay_date, CASE  WHEN ((ufp.first_pay_date IS NULL)) THEN (1) WHEN ((ufp.first_pay_date < CAST(o.pay_time AS DATE))) THEN (0) ELSE 1 END AS is_new_customer FROM orders AS o LEFT JOIN user_first_purchase AS ufp ON ((o.user_id = ufp.user_id));
CREATE VIEW v_valid_orders AS SELECT * FROM orders WHERE ((is_goujinjin = CAST('f' AS BOOLEAN)) AND (order_status != '交易关闭') AND (is_refund = CAST('f' AS BOOLEAN)));
