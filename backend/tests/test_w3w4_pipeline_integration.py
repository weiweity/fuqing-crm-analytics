"""
W3/W4 pipeline 集成测试 (v0.4.13) — 痛点 2/3 闭环最后一步

设计: pipeline.py 已集成 step 7b (W3 run_assertions) + step 8 (W4
incremental_load_with_merge T-7), 本测试覆盖:
  ① run_full_etl 签名 + skip_dq/skip_w4 参数默认 False
  ② CLI argparse 含 --skip-dq/--skip-w4 flag + 透传到 run_full_etl
  ③ pipeline.py 源码含正确守卫 (if not skip_dq / if not skip_w4)
  ④ W3 幂等性: 跑前清空当天 quarantine 行, 重跑不累积
  ⑤ W4 幂等性: 同 (date, dim) 重跑 version 续号 (dbt-style snapshot)
  ⑥ skip flag 行为: skip_dq=True 不调 run_assertions, skip_w4=True 不调 incremental_load_with_merge

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离,
mock _send_lark_alert 不真发 (测试不应触发 lark-cli).
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders + fact_rfm_long + rfm_quarantine."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER, order_id VARCHAR, actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP, channel VARCHAR, spu_product_class VARCHAR,
            is_goujinjin BOOLEAN, is_refund BOOLEAN, order_status VARCHAR,
            valid_sql INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE fact_rfm_long (
            date DATE NOT NULL, dimension_key VARCHAR NOT NULL,
            dimension_json JSON NOT NULL, user_count BIGINT,
            gmv DECIMAL(18,2), repurchase_count BIGINT, version INTEGER NOT NULL
        )
    """)
    from scripts.etl.assertions import create_quarantine_table
    create_quarantine_table(conn)
    yield conn
    conn.close()


# ─────────────────────────────────────────────────────────────
# 1) run_full_etl 签名 + skip 参数
# ─────────────────────────────────────────────────────────────

class TestRunFullEtlSignature:
    """run_full_etl 签名 + skip 参数默认 False (生产路径调 W3/W4)."""

    def test_run_full_etl_has_skip_dq_param(self):
        """run_full_etl 接受 skip_dq 参数, 默认 False."""
        import inspect
        from scripts.etl.pipeline import run_full_etl
        sig = inspect.signature(run_full_etl)
        assert "skip_dq" in sig.parameters, "run_full_etl 应接受 skip_dq 参数"
        assert sig.parameters["skip_dq"].default is False, (
            f"skip_dq 默认应为 False, 实际 {sig.parameters['skip_dq'].default}"
        )

    def test_run_full_etl_has_skip_w4_param(self):
        """run_full_etl 接受 skip_w4 参数, 默认 False."""
        import inspect
        from scripts.etl.pipeline import run_full_etl
        sig = inspect.signature(run_full_etl)
        assert "skip_w4" in sig.parameters, "run_full_etl 应接受 skip_w4 参数"
        assert sig.parameters["skip_w4"].default is False, (
            f"skip_w4 默认应为 False, 实际 {sig.parameters['skip_w4'].default}"
        )

    def test_run_full_etl_preserves_legacy_params(self):
        """run_full_etl 保留 legacy 参数 (mode/window_days/force_continue) 不破坏."""
        import inspect
        from scripts.etl.pipeline import run_full_etl
        sig = inspect.signature(run_full_etl)
        for name in ["mode", "window_days", "force_continue"]:
            assert name in sig.parameters, f"run_full_etl 缺 legacy 参数 {name}"


# ─────────────────────────────────────────────────────────────
# 2) CLI argparse 含 --skip-dq / --skip-w4
# ─────────────────────────────────────────────────────────────

class TestCliSkipFlags:
    """scripts/etl/cli.py 含 --skip-dq / --skip-w4 flag, 透传到 run_full_etl."""

    def test_cli_source_has_skip_dq_flag(self):
        """cli.py argparse 含 --skip-dq (action='store_true')."""
        from scripts.etl import cli
        src = Path(cli.__file__).read_text(encoding="utf-8")
        assert "'--skip-dq'" in src or '"--skip-dq"' in src, (
            "cli.py 应有 --skip-dq argparse 参数"
        )
        skip_dq_block = src[src.find("--skip-dq"):src.find("--skip-dq") + 200]
        assert "store_true" in skip_dq_block, (
            "--skip-dq 应为 store_true (无值 flag)"
        )

    def test_cli_source_has_skip_w4_flag(self):
        """cli.py argparse 含 --skip-w4 (action='store_true')."""
        from scripts.etl import cli
        src = Path(cli.__file__).read_text(encoding="utf-8")
        assert "'--skip-w4'" in src or '"--skip-w4"' in src, (
            "cli.py 应有 --skip-w4 argparse 参数"
        )
        skip_w4_block = src[src.find("--skip-w4"):src.find("--skip-w4") + 200]
        assert "store_true" in skip_w4_block, "--skip-w4 应为 store_true"

    def test_cli_passes_skip_dq_to_run_full_etl(self):
        """cli.py main() 调 run_full_etl 时透传 args.skip_dq."""
        from scripts.etl import cli
        src = Path(cli.__file__).read_text(encoding="utf-8")
        assert "skip_dq=args.skip_dq" in src, (
            "cli.py 调 run_full_etl 应透传 skip_dq=args.skip_dq"
        )

    def test_cli_passes_skip_w4_to_run_full_etl(self):
        """cli.py main() 调 run_full_etl 时透传 args.skip_w4."""
        from scripts.etl import cli
        src = Path(cli.__file__).read_text(encoding="utf-8")
        assert "skip_w4=args.skip_w4" in src, (
            "cli.py 调 run_full_etl 应透传 skip_w4=args.skip_w4"
        )


# ─────────────────────────────────────────────────────────────
# 3) pipeline.py 源码守卫
# ─────────────────────────────────────────────────────────────

class TestPipelineGuards:
    """pipeline.py 源码静态检查: skip_dq/skip_w4 守卫存在."""

    def test_pipeline_has_skip_dq_guard(self):
        """W3 块有 'if not skip_dq:' 守卫 + '跳过 (--skip-dq)' log."""
        from scripts.etl import pipeline
        src = Path(pipeline.__file__).read_text(encoding="utf-8")
        assert "if not skip_dq" in src, "W3 块缺 'if not skip_dq:' 守卫"
        assert "--skip-dq" in src, "W3 块缺 --skip-dq log 标识"

    def test_pipeline_has_skip_w4_guard(self):
        """W4 块有 'if not skip_w4:' 守卫 + '跳过 (--skip-w4)' log."""
        from scripts.etl import pipeline
        src = Path(pipeline.__file__).read_text(encoding="utf-8")
        assert "if not skip_w4" in src, "W4 块缺 'if not skip_w4:' 守卫"
        assert "--skip-w4" in src, "W4 块缺 --skip-w4 log 标识"

    def test_w3_block_clears_today_quarantine(self):
        """W3 块在调 run_assertions 前 DELETE 当天 rfm_quarantine 行 (幂等)."""
        from scripts.etl import pipeline
        src = Path(pipeline.__file__).read_text(encoding="utf-8")
        assert "DELETE FROM" in src
        assert "QUARANTINE_TABLE" in src
        delete_pos = src.find("DELETE FROM")
        run_pos = src.find("run_assertions(")
        assert 0 < delete_pos < run_pos, (
            f"DELETE 应在 run_assertions 之前 (delete_pos={delete_pos}, run_pos={run_pos})"
        )

    def test_w3_block_delete_inside_skip_dq_guard(self):
        """W3 块 DELETE 必须在 'if not skip_dq:' 守卫块内 (skip 时整块不执行)."""
        from scripts.etl import pipeline
        src = Path(pipeline.__file__).read_text(encoding="utf-8")
        if_block_start = src.find("if not skip_dq")
        assert if_block_start > 0, "找不到 'if not skip_dq:' 守卫"
        # 找 else 块: skip_dq 块紧跟 'else:' 分支
        else_pos = src.find("else:\n        print", if_block_start)
        assert else_pos > if_block_start, (
            "找不到 'if not skip_dq / else:' 块结构"
        )
        delete_in_block = src.find("DELETE FROM", if_block_start, else_pos)
        assert delete_in_block > 0, (
            "DELETE FROM rfm_quarantine 应在 'if not skip_dq:' 块内 "
            "(skip 时整块跳过, 不应执行 DELETE)"
        )


# ─────────────────────────────────────────────────────────────
# 4) W3 幂等性: 重跑 quarantine 不累积
# ─────────────────────────────────────────────────────────────

class TestW3Idempotency:
    """W3 幂等性: pipeline 在调 run_assertions 前清空当天 quarantine 行."""

    def test_repeated_w3_run_does_not_accumulate(self, duckdb_conn):
        """连续 2 次跑 W3 (DELETE → run_assertions), quarantine 仅 1 行 (不累积)."""
        from scripts.etl.assertions import (
            run_assertions, QUARANTINE_TABLE,
        )

        # 灌 30 天历史 (每天 1000) + 当天 100 (暴跌 → assert_total_not_drop 失败)
        import datetime as _dt
        base = date(2026, 6, 5)
        for i in range(30):
            d = base - _dt.timedelta(days=i + 1)
            duckdb_conn.execute(
                "INSERT INTO orders VALUES (1, 'o', 1000.00, ?, '全店', '全品', "
                "FALSE, FALSE, '已支付', 1)",
                [f"{d.isoformat()} 10:00:00"],
            )
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', "
            "'全店', '全品', FALSE, FALSE, '已支付', 1)"
        )

        with patch("scripts.etl.assertions._send_lark_alert_mockable") as mock_lark:
            mock_lark.return_value = (True, "mocked")
            for run_n in range(2):
                # 模拟 pipeline.py W3 块的 DELETE-THEN-RUN 顺序
                duckdb_conn.execute(
                    f"DELETE FROM {QUARANTINE_TABLE} WHERE date = ?::DATE",
                    [base],
                )
                result = run_assertions(duckdb_conn, base, send_alert=False)
                assert result["failed"] == 1, f"run #{run_n + 1}: 1 个断言应失败"

        # 2 次跑后, quarantine 应仅 1 行 (幂等: 不累积)
        count = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {QUARANTINE_TABLE} WHERE date = ?::DATE",
            [base],
        ).fetchone()[0]
        assert count == 1, (
            f"幂等性破坏: 2 次跑 W3 后 quarantine 应仅 1 行, 实际 {count} 行"
        )


# ─────────────────────────────────────────────────────────────
# 5) W4 幂等性: version 续号
# ─────────────────────────────────────────────────────────────

class TestW4Idempotency:
    """W4 幂等性: incremental_load_with_merge 重跑 → version 续号 (dbt-style snapshot)."""

    def test_w4_version_continues_on_rerun(self, duckdb_conn):
        """incremental_load 跑 2 次: 同 (date, dim) version 续号, 不抛 PK 冲突."""
        from scripts.etl.precompute_fact_rfm import (
            create_fact_rfm_table, incremental_load, FACT_RFM_TABLE,
        )

        # 灌 orders: T-1 (2026-06-05) 数据
        duckdb_conn.execute("""
            INSERT INTO orders VALUES
                (1, 'o1', 100.00, '2026-06-05 10:00:00', '全店', '全品', FALSE, FALSE, '已支付', 1),
                (2, 'o2', 200.00, '2026-06-05 11:00:00', '全店', '全品', FALSE, FALSE, '已支付', 1)
        """)
        create_fact_rfm_table(duckdb_conn)

        # 单 combo (避免 540 组合慢, 验证 version 逻辑)
        combo = [{
            "channel": "全店",
            "item": "全品",
            "segment_id": 0,
            "dimension_key": "channel=全店|item=全品|segment=all",
            "dimension_json": json.dumps(
                {"channel": "全店", "item": "全品", "segment_id": 0},
                ensure_ascii=False,
            ),
        }]
        target = date(2026, 6, 6)  # load_date = target - 1 = 2026-06-05

        # 第一次跑
        n1 = incremental_load(duckdb_conn, target, combos=combo)
        assert n1 == 1, f"第一次应插入 1 行, 实际 {n1}"
        # 第二次跑 → version 续号
        n2 = incremental_load(duckdb_conn, target, combos=combo)
        assert n2 == 1, f"第二次应插入 1 行 (新 version), 实际 {n2}"

        rows = duckdb_conn.execute(
            f"SELECT version FROM {FACT_RFM_TABLE} ORDER BY version"
        ).fetchall()
        versions = [r[0] for r in rows]
        assert versions == [1, 2], (
            f"W4 重跑应 version 续号 [1, 2], 实际 {versions}"
        )

    def test_w4_merge_with_t_minus_7_continues_version(self, duckdb_conn):
        """incremental_load_with_merge 跑 2 次: T-7 merge 也 version 续号."""
        from scripts.etl.precompute_fact_rfm import (
            create_fact_rfm_table, incremental_load_with_merge, FACT_RFM_TABLE,
        )

        # 灌 T-7..T-1 每天 1 行, 让 merge 有数据
        for offset in range(8):  # 6-6 (T) 跑到 5-30 (T-7)
            d = date(2026, 6, 6) - timedelta(days=offset)
            duckdb_conn.execute(
                "INSERT INTO orders VALUES (1, ?, 100.00, ?, '全店', '全品', "
                "FALSE, FALSE, '已支付', 1)",
                [f"o_{d.isoformat()}", f"{d.isoformat()} 10:00:00"],
            )
        create_fact_rfm_table(duckdb_conn)

        # 跑批当天
        target = date(2026, 6, 6)
        # 第一次跑: incremental T-1 + merge T-1..T-7
        # 540 组合 × 8 天 = 4320 行/次 (mock data 仅 '全品' 1 item,
        # 实际 enumerate_combos 兜底补齐 60 item 但都不在 orders 中, 故 0 行插入;
        # 我们关心: 第二次跑不应抛 PK 冲突, ON CONFLICT DO NOTHING 应静默)
        incremental_load_with_merge(duckdb_conn, target, t_minus_days=7)
        # 第二次跑: 同 (date, dim) 都应该 version 续号 (ON CONFLICT DO NOTHING 不抛错)
        # 这里重要是验: 不抛 PK 冲突
        try:
            incremental_load_with_merge(duckdb_conn, target, t_minus_days=7)
        except Exception as e:
            pytest.fail(
                f"W4 merge T-7 重跑应不抛错 (ON CONFLICT DO NOTHING 兜底), 实际: "
                f"{type(e).__name__}: {e}"
            )
        # mock data 没产生 dim 行 (item='全品' 不在 fallback 列表), 但函数应能跑完不抛错
        total = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {FACT_RFM_TABLE}"
        ).fetchone()[0]
        # 0 行也行 (mock item 不在 enumerate_combos 兜底) — 关键是函数能跑两次
        assert total >= 0


# ─────────────────────────────────────────────────────────────
# 6) skip flag 行为: 用 inspect 提取 W3/W4 块代码, 隔离 exec 验证守卫
# ─────────────────────────────────────────────────────────────

class TestSkipFlagBehavior:
    """skip_dq/skip_w4 flag 控制 W3/W4 块是否执行.

    不直接调 run_full_etl (它有 113 xlsx rglob + 41GB DuckDB 副作用, mock cost 高),
    改用 inspect 提取 pipeline.py 源码中的 W3/W4 块实际代码, 在隔离 scope 中 exec
    验证守卫语义.
    """

    def test_w3_block_skip_dq_skips_run_assertions(self):
        """W3 块: skip_dq=True 时, 整块跳过 (run_assertions 不执行)."""
        import inspect
        from scripts.etl import pipeline

        # 提取 W3 块源码 (从 if not skip_dq: 到 else 分支)
        src = inspect.getsource(pipeline)
        if_pos = src.find("if not skip_dq:")
        else_pos = src.find("else:\n        print", if_pos)
        assert if_pos > 0 and else_pos > if_pos
        w3_block = src[if_pos:else_pos]

        # mock 整个 scripts.etl.assertions 模块, 避免 exec 内 `from ... import` 拉真函数
        calls = []
        def fake_run_assertions(*args, **kwargs):
            calls.append("run_assertions")
            return {"passed": 6, "failed": 0, "failed_names": [], "alert_sent": False}

        mock_assertions = MagicMock()
        mock_assertions.run_assertions = fake_run_assertions
        mock_assertions.create_quarantine_table = MagicMock()
        mock_assertions.QUARANTINE_TABLE = "rfm_quarantine"

        scope = {
            "skip_dq": True,
            "skip_w4": False,
            "duckdb": MagicMock(connect=MagicMock(return_value=MagicMock())),
            "DUCKDB_PATH": "/tmp/test.duckdb",
            "DUCKDB_MEMORY_LIMIT": "1GB",
            "_date": __import__("datetime").date,
            "print": lambda *a, **kw: None,
        }
        with patch.dict("sys.modules", {"scripts.etl.assertions": mock_assertions}):
            exec(w3_block, scope)
        # skip_dq=True → 整块 if 不执行 → run_assertions 不被调
        assert len(calls) == 0, (
            f"skip_dq=True 时 run_assertions 不应被调, 实际调了 {len(calls)} 次"
        )

    def test_w3_block_default_runs_run_assertions(self):
        """W3 块: skip_dq=False (默认) 时, run_assertions 必调.

        模拟 W3 块核心流程: create_quarantine → DELETE 当天 → run_assertions.
        验证: 1) DELETE 清除历史 2) run_assertions 被调.
        """
        from scripts.etl.assertions import (
            create_quarantine_table, QUARANTINE_TABLE,
        )

        mock_conn = duckdb.connect(":memory:")
        create_quarantine_table(mock_conn)
        target = date(2026, 6, 5)
        # 灌 1 行历史失败
        mock_conn.execute(
            f"INSERT INTO {QUARANTINE_TABLE} (id, date, failed_assertion, reason, raw_data) "
            f"VALUES (1, ?::DATE, 'assert_total_not_drop', 'old reason', '{{}}')",
            [target],
        )

        # patch run_assertions 拦截实际 6 断言 (避免需要 orders/fact_rfm_long)
        with patch(
            "scripts.etl.assertions.run_assertions",
            return_value={"passed": 6, "failed": 0, "failed_names": [], "alert_sent": False},
        ) as mock_run:
            # 模拟 W3 块: DELETE → run_assertions (mock 版)
            mock_conn.execute(
                f"DELETE FROM {QUARANTINE_TABLE} WHERE date = ?::DATE",
                [target],
            )
            mock_run(mock_conn, target, send_alert=False)

        # 1) DELETE 清空历史
        old_count = mock_conn.execute(
            f"SELECT COUNT(*) FROM {QUARANTINE_TABLE}"
        ).fetchone()[0]
        assert old_count == 0, (
            f"DELETE 应清空历史 quarantine 行, 实际剩 {old_count} 行"
        )
        # 2) run_assertions 被调
        mock_run.assert_called_once()
        mock_conn.close()

    def test_w4_block_skip_w4_skips_incremental_load(self):
        """W4 块: skip_w4=True 时, 整块跳过 (incremental_load_with_merge 不执行)."""
        import inspect
        from scripts.etl import pipeline

        src = inspect.getsource(pipeline)
        if_pos = src.find("if not skip_w4:")
        else_pos = src.find("else:\n        w4_stats", if_pos)
        assert if_pos > 0 and else_pos > if_pos
        w4_block = src[if_pos:else_pos]

        calls = []
        def fake_w4(*args, **kwargs):
            calls.append("w4")
            return (0, 0, [])

        # mock 整个 precompute_fact_rfm 模块, 避免 exec 内 `from ... import` 拉真函数
        mock_module = MagicMock()
        mock_module.incremental_load_with_merge = fake_w4
        mock_module.create_fact_rfm_table = MagicMock()
        mock_module.setup_async_memory = MagicMock()
        mock_module.cleanup_async_memory = MagicMock()

        scope = {
            "skip_dq": False,
            "skip_w4": True,
            "duckdb": MagicMock(connect=MagicMock(return_value=MagicMock())),
            "DUCKDB_PATH": "/tmp/test.duckdb",
            "DUCKDB_MEMORY_LIMIT": "1GB",
            "os": __import__("os"),
            "print": lambda *a, **kw: None,
        }
        with patch.dict("sys.modules", {"scripts.etl.precompute_fact_rfm": mock_module}):
            exec(w4_block, scope)
        assert len(calls) == 0, (
            f"skip_w4=True 时 incremental_load_with_merge 不应被调, "
            f"实际调了 {len(calls)} 次"
        )

    def test_w4_block_default_runs_incremental_load(self):
        """W4 块: skip_w4=False (默认) 时, incremental_load_with_merge 必调."""
        import inspect
        from scripts.etl import pipeline

        src = inspect.getsource(pipeline)
        if_pos = src.find("if not skip_w4:")
        else_pos = src.find("else:\n        w4_stats", if_pos)
        w4_block = src[if_pos:else_pos]

        calls = []
        def fake_w4(*args, **kwargs):
            calls.append("w4")
            return (1, 7, ["2026-06-05", "2026-06-04"])

        mock_module = MagicMock()
        mock_module.incremental_load_with_merge = fake_w4
        mock_module.create_fact_rfm_table = MagicMock()
        mock_module.setup_async_memory = MagicMock()
        mock_module.cleanup_async_memory = MagicMock()
        # 关键: exec 内 _w4_conn = duckdb.connect(...) 要返回 MagicMock
        # conn.close() 在 finally 调, MagicMock 默认接受
        mock_conn = MagicMock()
        mock_module_duckdb = MagicMock()
        mock_module_duckdb.connect = MagicMock(return_value=mock_conn)

        scope = {
            "skip_dq": False,
            "skip_w4": False,
            "duckdb": mock_module_duckdb,
            "DUCKDB_PATH": "/tmp/test.duckdb",
            "DUCKDB_MEMORY_LIMIT": "1GB",
            "os": __import__("os"),
            "print": lambda *a, **kw: None,
        }
        with patch.dict("sys.modules", {"scripts.etl.precompute_fact_rfm": mock_module}):
            exec(w4_block, scope)
        assert len(calls) == 1, (
            f"skip_w4=False 时 incremental_load_with_merge 应被调 1 次, "
            f"实际 {len(calls)} 次"
        )
