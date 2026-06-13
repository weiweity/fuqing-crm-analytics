"""
Sprint 15 Wave 3 治根测试: 验证 _mark_user_id_history_member (老客回购 per-user 标).

背景: Sprint 15 Wave 2 (B1+B2+D.1) 修了 mark 跟 orders.is_member 同步,
但前端 6/9 之后会员数据不显示. 真根因: 增量 ETL 走 per-order 标 (line 398
shop_df['is_member'] = order_id IN member_order_ids), 老客 (user_id 跟历史
is_member=TRUE 重叠) 但新单 order_id 不在历史 mark → 标 FALSE.

Sprint 15 Wave 3 治根: _mark_user_id_history_member helper 加 per-user 标,
老客 (is_member=FALSE) 但 user_id 跟历史 is_member=TRUE 重叠 → 标 TRUE.
6/9+ 64 订单 18 老客, 全标 TRUE 后前端会员数据回归.

测试覆盖 (跟 test_is_member_mark_sync.py 风格一致):
1. 老客回购标 TRUE (主治根)
2. 全新客不标 (边界)
3. user_id IS NULL 不报错 (NULL 守卫)
4. shop_df 空返 0 (early return)
5. 重复调 idempotent
6. 6/9+ 18 老客回归 (Sprint 15 真根因 18 老客)
"""
import pytest
import duckdb
import tempfile
import os
import pandas as pd

from scripts.etl.pipeline import _mark_user_id_history_member


@pytest.fixture
def temp_duckdb_with_history():
    """In-memory 临时 DuckDB fixture: 模拟历史 orders 表 (含 is_member=TRUE 历史会员 user_id)."""
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(path)  # DuckDB 拒绝连接空文件, 让 connect 自己建
    conn = duckdb.connect(path)
    try:
        # 建 orders 表 (跟 prod schema 一致)
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                is_member BOOLEAN
            )
        """)
        # 插入历史数据: 5 个历史会员 user_id, 各自 2 单 (10 个 is_member=TRUE 历史订单)
        historical_member_user_ids = [f"OLD_USER_{i:03d}" for i in range(5)]
        historical_orders = []
        for uid in historical_member_user_ids:
            historical_orders.append((f"HIST_{uid}_A", uid, True))
            historical_orders.append((f"HIST_{uid}_B", uid, True))
        for oid, uid, is_m in historical_orders:
            conn.execute(
                "INSERT INTO orders (order_id, user_id, is_member) VALUES (?, ?, ?)",
                [oid, uid, is_m],
            )
        # 插入 3 个非会员 user_id 历史订单 (老客回购场景无关, 只做隔离)
        non_member_orders = [
            (f"NONM_{i:03d}", f"NON_MEMBER_{i:03d}", False) for i in range(3)
        ]
        for oid, uid, is_m in non_member_orders:
            conn.execute(
                "INSERT INTO orders (order_id, user_id, is_member) VALUES (?, ?, ?)",
                [oid, uid, is_m],
            )
        yield conn, path, historical_member_user_ids
    finally:
        conn.close()
        os.unlink(path)


class TestUserIdHistoryMember:
    """Sprint 15 Wave 3: _mark_user_id_history_member (老客回购 per-user 标) 治根测试."""

    def test_old_user_repurchase_marked_true(self, temp_duckdb_with_history):
        """主治根: 老客 (历史 is_member=TRUE user_id) 回购新单 → is_member=TRUE."""
        conn, path, historical_uids = temp_duckdb_with_history
        # 新单: 3 个老客各自回购 1 单, 1 个新客新单
        shop_df = pd.DataFrame({
            "order_id": ["NEW_001", "NEW_002", "NEW_003", "NEW_BRAN_NEW"],
            "user_id": [historical_uids[0], historical_uids[1], historical_uids[2], "BRAND_NEW_USER"],
            "is_member": [False, False, False, False],  # per-order 标后全部 FALSE
        })

        n_old = _mark_user_id_history_member(shop_df, conn)

        # 3 个老客回购标 TRUE, 1 个新客保持 FALSE
        assert n_old == 3, f"应标 3 个老客, 实际 {n_old}"
        assert shop_df.loc[0, "is_member"] is True or shop_df.loc[0, "is_member"]
        assert shop_df.loc[1, "is_member"] is True or shop_df.loc[1, "is_member"]
        assert shop_df.loc[2, "is_member"] is True or shop_df.loc[2, "is_member"]
        assert shop_df.loc[3, "is_member"] is False or not shop_df.loc[3, "is_member"]

    def test_new_user_new_order_unchanged(self, temp_duckdb_with_history):
        """新客 (user_id 不在历史 is_member=TRUE) 新单 → is_member 保持 FALSE."""
        conn, path, _ = temp_duckdb_with_history
        shop_df = pd.DataFrame({
            "order_id": ["NEW_BRAN_NEW"],
            "user_id": ["BRAND_NEW_USER_001"],
            "is_member": [False],
        })

        n_old = _mark_user_id_history_member(shop_df, conn)

        assert n_old == 0, f"新客应标 0 个, 实际 {n_old}"
        assert shop_df.loc[0, "is_member"] is False or not shop_df.loc[0, "is_member"]

    def test_user_id_none_safely_handled(self, temp_duckdb_with_history):
        """user_id IS NULL 守卫: 不报错, 不标 (跟 DuckDB WHERE user_id IS NOT NULL 一致)."""
        conn, path, _ = temp_duckdb_with_history
        shop_df = pd.DataFrame({
            "order_id": ["NEW_NULL_USER"],
            "user_id": [None],
            "is_member": [False],
        })

        n_old = _mark_user_id_history_member(shop_df, conn)  # 不应抛异常

        assert n_old == 0, f"NULL user_id 应跳过, 实际 {n_old}"
        assert shop_df.loc[0, "is_member"] is False or not shop_df.loc[0, "is_member"]

    def test_empty_shop_df_returns_zero(self, temp_duckdb_with_history):
        """shop_df 空返 0 (early return, 避免无谓查询)."""
        conn, path, _ = temp_duckdb_with_history
        shop_df = pd.DataFrame(columns=["order_id", "user_id", "is_member"])

        n_old = _mark_user_id_history_member(shop_df, conn)

        assert n_old == 0

    def test_idempotent_on_rerun(self, temp_duckdb_with_history):
        """重复调 idempotent: 第二次标 0 个 (已 TRUE 不再被 mask 选中)."""
        conn, path, historical_uids = temp_duckdb_with_history
        shop_df = pd.DataFrame({
            "order_id": ["NEW_REPLAY"],
            "user_id": [historical_uids[0]],
            "is_member": [False],
        })

        n_first = _mark_user_id_history_member(shop_df, conn)
        n_second = _mark_user_id_history_member(shop_df, conn)  # 重复调

        assert n_first == 1, f"第一次应标 1 个, 实际 {n_first}"
        assert n_second == 0, f"第二次 idempotent 应 0, 实际 {n_second}"
        assert shop_df.loc[0, "is_member"] is True or shop_df.loc[0, "is_member"]

    def test_6_9_18_old_user_regression(self, temp_duckdb_with_history):
        """Sprint 15 真根因回归: 6/9+ 64 订单 18 老客 + 39 新客 + 7 单 → 18 老客标 TRUE.

        真实数据: 6/9 拉 64 个新订单, 57 个 user_id, 18 个跟 mark 表关联
        (历史 is_member=TRUE), 39 个全新客. 6/10 0 订单 (增量 ETL 没拉到).
        治根后: 18 老客 is_member=TRUE, 39 新客 FALSE.
        """
        conn, path, historical_uids = temp_duckdb_with_history
        # 模拟 6/9 拉批: 18 个老客 (跟 mark 表 user_id 重叠) + 39 个新客
        # 用 historical_uids 0-4 (5 个) + 额外 13 个 (5+13=18 老客) → 但 fixture 只有 5 个
        # 这里简化: 18 个老客, 全部用前 5 个 historical_uids 循环 + 13 个额外模拟
        # 用 5 个 historical 重复 (模拟同一老客多单回购) + 13 个新 historical
        old_user_repurchase = (
            [historical_uids[i % 5] for i in range(5)]  # 5 单 (5 老客)
            + [f"EXTRA_OLD_{i:03d}" for i in range(13)]  # 13 单 (13 老客, fixture 不知道)
        )
        # 把 13 个 EXTRA_OLD_* 注入 DuckDB 历史 is_member=TRUE 模拟 mark 表覆盖
        for i in range(13):
            conn.execute(
                "INSERT INTO orders (order_id, user_id, is_member) VALUES (?, ?, TRUE)",
                [f"EXTRA_HIST_{i:03d}", f"EXTRA_OLD_{i:03d}"],
            )
        # 18 个老客新单 + 39 个新客新单 (简化: 全部 per-order 标后 is_member=FALSE)
        old_orders = [{"order_id": f"NEW_OLD_{i:03d}", "user_id": uid, "is_member": False} for i, uid in enumerate(old_user_repurchase)]
        new_orders = [{"order_id": f"NEW_NEW_{i:03d}", "user_id": f"BRAND_NEW_{i:03d}", "is_member": False} for i in range(39)]
        shop_df = pd.DataFrame(old_orders + new_orders)

        assert len(shop_df) == 18 + 39  # 57 单 (简化, 跟 6/9 57 user 接近)

        n_old = _mark_user_id_history_member(shop_df, conn)

        # 18 个老客全标 TRUE
        assert n_old == 18, f"6/9+ 18 老客回归: 应标 18, 实际 {n_old}"
        n_true = int(shop_df["is_member"].sum())
        n_false = int((~shop_df["is_member"]).sum())
        assert n_true == 18, f"应有 18 单 is_member=TRUE, 实际 {n_true}"
        assert n_false == 39, f"应有 39 单 is_member=FALSE, 实际 {n_false}"
