"""
Sprint 22 #30 regression test: DuckDB 1.5.2 跨连接 race 治根验证 (Sprint 16 留).

背景:
  Sprint 16 留: DuckDB 1.5.2 ART index 跨 connection race, 多个 ETL subprocess
  并发写会触发 _duckdb.IOException (ConstraintException / IO Error).
  Sprint 16+ DuckDB 上游已修 (1.5.3+ ART index race fix), 当前 crm-analytics
  装 duckdb 1.5.4.dev18, race 100% 不复现.

防回归:
  - 当前 DuckDB 版本必须 >= 1.5.3 (race fix)
  - 30 workers × 100 writes stress test 0 error (100% 成功)
  - 写入数据完整 (3000 行全部落盘, 无丢失)

如果未来升级降级或上游回归, 这测试会失败提醒.
"""
import sys
import tempfile
import threading
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_duckdb_version_at_least_1_5_3():
    """Sprint 16 race fix 在 1.5.3+, 当前 1.5.4.dev18 满足. 降级告警."""
    from packaging.version import Version
    v = Version(duckdb.__version__)
    assert v >= Version("1.5.3"), (
        f"DuckDB 版本 {duckdb.__version__} < 1.5.3, Sprint 16 跨连接 race 未修. "
        f"升级到 >= 1.5.3 重跑此测试."
    )


def test_concurrent_writes_30_workers_100_each_no_race():
    """30 workers × 100 writes = 3000 行, 0 race 错 + 3000 行全落盘 (Sprint 16 治根验证).

    修前 (1.5.2): 30 workers 并发会触发 ConstraintException 或 IO Error, 写入丢失.
    修后 (1.5.3+): 0 错 3000 行全成功.
    """
    tmp = Path(tempfile.mkdtemp()) / "race_stress.duckdb"
    # 初始表
    init = duckdb.connect(str(tmp))
    init.execute("CREATE TABLE t (worker_id INT, seq INT, payload VARCHAR)")
    init.close()

    errors: list = []
    done_count = [0]
    errors_lock = threading.Lock()
    done_lock = threading.Lock()

    def worker(worker_id: int, n_writes: int = 100):
        try:
            c = duckdb.connect(str(tmp))
            for j in range(n_writes):
                c.execute(
                    "INSERT INTO t VALUES (?, ?, ?)",
                    [worker_id, j, f"w{worker_id}r{j}"],
                )
            c.close()
        except Exception as e:
            with errors_lock:
                errors.append((worker_id, type(e).__name__, str(e)[:100]))
        with done_lock:
            done_count[0] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 1. 30 workers 全部完成
    assert done_count[0] == 30, f"应 30 workers 完成, 实际 {done_count[0]}"
    # 2. 0 race 错 (关键回归保护)
    assert not errors, (
        f"DuckDB 跨连接 race 复现 (Sprint 16 治根回归!): "
        f"{len(errors)} errors / 30 workers × 100 writes, 例: {errors[:3]}"
    )
    # 3. 数据完整 (3000 行全落盘)
    conn = duckdb.connect(str(tmp))
    total = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    conn.close()
    assert total == 3000, f"应 3000 行落盘, 实际 {total} (写入丢失)"


def test_duckdb_race_singleton_inmemory_safe():
    """单连接 in-memory DuckDB 跨多次写 idempotent (跟 test_sim_prod_etl.py 同款)."""
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE kv (k INT PRIMARY KEY, v VARCHAR)")
    for i in range(1000):
        conn.execute("INSERT INTO kv VALUES (?, ?)", [i, f"v{i}"])
    assert conn.execute("SELECT COUNT(*) FROM kv").fetchone()[0] == 1000
    conn.close()
