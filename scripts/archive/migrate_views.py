"""
芙清CRM - 逻辑视图迁移脚本

语义层收敛第1步：建统一视图，消除裸 SQL 重复。
所有视图定义由 backend.semantic.filters.OrderFilters 统一管理，
禁止任何 Service 或导出脚本绕过视图直接写 WHERE 条件。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import duckdb
from backend.config import DUCKDB_PATH
from backend.semantic.filters import OrderFilters

_valid_sql, _ = OrderFilters.valid_order()


def migrate(conn):
    """创建/替换所有逻辑视图"""

    # ── v_valid_orders: 有效订单（GSV口径，统一过滤入口）──
    print("创建 v_valid_orders ...")
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_valid_orders AS
        SELECT * FROM orders
        WHERE {_valid_sql}
    """)

    # ── v_order_with_user: 订单 + 新老客标记，预 JOIN ──
    print("创建 v_order_with_user ...")
    conn.execute("""
        CREATE OR REPLACE VIEW v_order_with_user AS
        SELECT
            o.*,
            ufp.first_pay_date,
            CASE
                WHEN ufp.first_pay_date IS NULL THEN 1
                WHEN ufp.first_pay_date < CAST(o.pay_time AS DATE) THEN 0
                ELSE 1
            END AS is_new_customer
        FROM orders o
        LEFT JOIN user_first_purchase ufp ON o.user_id = ufp.user_id
    """)

    # ── v_category_daily: 品类日粒度聚合视图 ──
    print("创建 v_category_daily ...")
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_category_daily AS
        SELECT
            CAST(pay_time AS DATE) AS order_date,
            COALESCE(TRIM(spu_product_subclass), '未知') AS category,
            COUNT(DISTINCT user_id) AS user_count,
            COUNT(DISTINCT order_id) AS order_count,
            SUM(actual_amount) AS gsv,
            SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv,
            COUNT(DISTINCT CASE WHEN is_member THEN user_id END) AS member_count
        FROM orders
        WHERE {_valid_sql}
        GROUP BY CAST(pay_time AS DATE), COALESCE(TRIM(spu_product_subclass), '未知')
    """)

    # 验证
    for view in ["v_valid_orders", "v_order_with_user", "v_category_daily"]:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        print(f"  ✅ {view}: {cnt:,} 行")

    print("\n视图迁移完成!")


if __name__ == "__main__":
    conn = duckdb.connect(str(DUCKDB_PATH))
    try:
        migrate(conn)
    finally:
        conn.close()
