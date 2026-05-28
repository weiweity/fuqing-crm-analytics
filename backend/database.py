"""
芙清 CRM 客户分析系统 - 数据库初始化 v2
支持会员标签和SPU匹配
"""

import duckdb
from backend.config import DUCKDB_PATH, PROCESSED_DATA_DIR
from backend.db.connection import get_connection

def init_database():
    """初始化 DuckDB 数据库，创建必要的表结构"""

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    # 删除旧表
    conn.execute("DROP TABLE IF EXISTS orders")
    conn.execute("DROP TABLE IF EXISTS spu_mapping")
    conn.execute("DROP TABLE IF EXISTS daily_metrics")
    conn.execute("DROP TABLE IF EXISTS monthly_metrics")
    conn.execute("DROP TABLE IF EXISTS user_summary")
    conn.execute("DROP TABLE IF EXISTS user_rfm")

    # 创建订单主表（与 run_etl.py 保持一致）
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            user_nickname VARCHAR,
            order_time TIMESTAMP,
            pay_time TIMESTAMP,
            ship_time TIMESTAMP,
            order_type VARCHAR,
            order_status VARCHAR,
            product_id VARCHAR,
            merchant_code VARCHAR,
            product_title VARCHAR,
            sku_id VARCHAR,
            sku_code VARCHAR,
            sku_name VARCHAR,
            quantity INTEGER,
            amount DECIMAL(12,2),
            refund_status VARCHAR,
            refund_amount DECIMAL(12,2),
            actual_amount DECIMAL(12,2),
            province VARCHAR,
            city VARCHAR,
            influencer_name VARCHAR,
            influencer_id VARCHAR,
            live_room_id VARCHAR,
            video_id VARCHAR,
            traffic_source VARCHAR,
            traffic_type VARCHAR,
            seller_note VARCHAR,
            year INTEGER,
            month INTEGER,
            is_member BOOLEAN,
            -- SPU 匹配字段
            spu_category VARCHAR,
            spu_type VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_spec VARCHAR,
            spu_hash VARCHAR,
            -- 渠道字段
            channel VARCHAR,
            -- 人群看板清洗标记
            is_goujinjin BOOLEAN DEFAULT FALSE,
            is_refund BOOLEAN DEFAULT FALSE
        )
    """)

    # 创建 SPU 匹配表
    conn.execute("""
        CREATE TABLE spu_mapping (
            product_id VARCHAR PRIMARY KEY,
            category VARCHAR,        -- 品类销售
            product_type VARCHAR,  -- 正装/小样
            tier VARCHAR,           -- 商品梯队
            product_class VARCHAR,  -- 单品归类
            detail VARCHAR,         -- 单品细分
            cosmetic VARCHAR,       -- 妆/械
            spec VARCHAR,           -- 商品规格
            start_date DATE,
            end_date DATE
        )
    """)

    # 创建每日指标表
    conn.execute("""
        CREATE TABLE daily_metrics (
            date DATE PRIMARY KEY,
            gmv DECIMAL(14,2),
            gsv DECIMAL(14,2),
            order_count INTEGER,
            gsv_order_count INTEGER,
            new_user_count INTEGER,
            old_user_count INTEGER,
            member_gmv DECIMAL(14,2),
            member_gsv DECIMAL(14,2),
            member_count INTEGER,
            avg_order_value DECIMAL(10,2),
            new_user_gmv DECIMAL(14,2),
            old_user_gmv DECIMAL(14,2)
        )
    """)

    # 创建月度指标表
    conn.execute("""
        CREATE TABLE monthly_metrics (
            year INTEGER,
            month INTEGER,
            gmv DECIMAL(12,2),
            gsv DECIMAL(12,2),
            order_count INTEGER,
            gsv_order_count INTEGER,
            new_user_count INTEGER,
            old_user_count INTEGER,
            member_gmv DECIMAL(12,2),
            member_gsv DECIMAL(12,2),
            avg_order_value DECIMAL(10,2),
            PRIMARY KEY (year, month)
        )
    """)

    # 创建索引
    conn.execute("CREATE INDEX idx_orders_pay_time ON orders(pay_time)")
    conn.execute("CREATE INDEX idx_orders_user ON orders(user_id)")
    conn.execute("CREATE INDEX idx_orders_year_month ON orders(year, month)")
    conn.execute("CREATE INDEX idx_orders_product ON orders(product_id)")

    # 唯一索引：防止重复订单
    conn.execute("CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)")

    # 人群看板复合索引（渠道×付款时间 + 渠道×会员）
    conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
    conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")

    # 创建 RFM 表（Week 2）
    create_user_rfm_table(conn)

    conn.close()
    print(f"Database v2 initialized at: {DUCKDB_PATH}")


def create_user_rfm_table(conn=None):
    """创建 user_rfm 表（DuckDB）"""
    if conn is None:
        conn = get_connection()
        should_close = True
    else:
        should_close = False

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_rfm (
            user_id            VARCHAR,
            user_nickname      VARCHAR,
            analysis_date      DATE,
            metric_type        VARCHAR,
            lookback_days      INTEGER,
            channel            VARCHAR DEFAULT '全店',
            recency_days       INTEGER,
            frequency          INTEGER,
            monetary           DECIMAL(12,2),
            r_score            INTEGER,
            f_score            INTEGER,
            m_score            INTEGER,
            rfm_tier           VARCHAR,
            rfm_tier_en        VARCHAR,
            segment_id         INTEGER,
            first_order_date   DATE,
            last_order_date    DATE,
            is_member          BOOLEAN DEFAULT FALSE,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days, channel)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rfm_tier ON user_rfm(rfm_tier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rfm_date ON user_rfm(analysis_date, metric_type, lookback_days)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rfm_channel ON user_rfm(channel)")

    if should_close:
        conn.close()
    print("user_rfm table created successfully")


def drop_user_rfm_table(conn=None):
    """删除 user_rfm 表"""
    if conn is None:
        conn = get_connection()
        should_close = True
    else:
        should_close = False

    conn.execute("DROP TABLE IF EXISTS user_rfm")

    if should_close:
        conn.close()
    print("user_rfm table dropped")


if __name__ == "__main__":
    init_database()
