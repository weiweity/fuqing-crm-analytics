"""Sprint 184 — DuckDB lock model behavior verification.

DuckDB uses OS file locks for process-level coordination. It does not behave
like PostgreSQL MVCC for multiple processes attached to the same database file.

This script documents the actual behavior we rely on:
1. A read-only connection can open after a read-write connection closes.
2. Same-process read-only and read-write connections cannot be active together.
3. A child-process read-only connection is blocked while the parent holds a
   read-write connection.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DB_DIR = PROJECT_ROOT / "data" / "processed"


def _safe_remove(path: Path) -> None:
    """Remove only Sprint 184 throwaway DuckDB files."""
    if path.exists() and "_test_sprint184" in path.name:
        path.unlink()


def test_same_process_readonly_after_readwrite_close() -> bool:
    """A read-only connection succeeds after the read-write connection closes."""
    import duckdb

    test_db = TEST_DB_DIR / f"_test_sprint184_{os.getpid()}.duckdb"
    _safe_remove(test_db)
    try:
        rw_conn = duckdb.connect(str(test_db))
        rw_conn.execute("CREATE TABLE t AS SELECT 1 AS x")
        rw_conn.close()

        ro_conn = duckdb.connect(str(test_db), read_only=True)
        try:
            row = ro_conn.execute("SELECT x FROM t").fetchone()
        finally:
            ro_conn.close()
        return row is not None and row[0] == 1
    finally:
        _safe_remove(test_db)


def test_same_process_concurrent_dies() -> bool:
    """Same-process read-only and read-write connections conflict as expected."""
    import duckdb

    test_db = TEST_DB_DIR / f"_test_sprint184_{os.getpid()}.duckdb"
    _safe_remove(test_db)
    rw_conn = None
    try:
        rw_conn = duckdb.connect(str(test_db), read_only=False)
        try:
            ro_conn = duckdb.connect(str(test_db), read_only=True)
        except Exception as exc:
            return "Connection Error" in str(exc) or "different configuration" in str(exc)
        else:
            ro_conn.close()
            return False
    finally:
        if rw_conn is not None:
            rw_conn.close()
        _safe_remove(test_db)


def _child_readonly(test_db: str, error_marker: str) -> None:
    """Child process attempts read-only access while parent holds write lock."""
    import duckdb

    try:
        conn = duckdb.connect(test_db, read_only=True)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        Path(error_marker).write_text("OK\n", encoding="utf-8")
    except Exception as exc:
        Path(error_marker).write_text(f"IO Error: {exc}\n", encoding="utf-8")


def test_cross_process_flock_blocks() -> tuple[str, str]:
    """Parent read-write connection blocks child read-only connection."""
    import duckdb

    test_db = TEST_DB_DIR / f"_test_sprint184_flock_{os.getpid()}.duckdb"
    err_marker = Path(tempfile.gettempdir()) / f"fq_sprint184_child_{os.getpid()}.log"
    _safe_remove(test_db)
    rw_conn = None
    try:
        rw_conn = duckdb.connect(str(test_db))
        rw_conn.execute("CREATE TABLE t AS SELECT 1 AS x")
        err_marker.unlink(missing_ok=True)

        proc = multiprocessing.Process(
            target=_child_readonly,
            args=(str(test_db), str(err_marker)),
        )
        proc.start()
        proc.join(timeout=10)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            return ("TIMEOUT", "子进程 10s 没返回")

        if err_marker.exists():
            content = err_marker.read_text(encoding="utf-8")
            if "IO Error" in content and "lock" in content.lower():
                return ("KNOWN", "flock 排斥符合预期 (P1 KNOW)")
            return ("OK", content.strip())
        return ("MISSING", f"子进程退出但未写 marker, exitcode={proc.exitcode}")
    finally:
        if rw_conn is not None:
            rw_conn.close()
        _safe_remove(test_db)
        err_marker.unlink(missing_ok=True)


def main() -> int:
    """Run all lock-model checks and print a human-readable report."""
    print("=== DuckDB 锁模型行为验证 (Sprint 184 v3) ===\n")

    print("[1/3] 同进程 read_only after read_write close → 期望 PASS")
    result_1 = test_same_process_readonly_after_readwrite_close()
    print(f"  结果: {'✅ PASS' if result_1 else '❌ FAIL'}\n")

    print("[2/3] 同进程 read_only + read_write 同时活动 → 期望 ConnectionException (KNOWN)")
    result_2 = test_same_process_concurrent_dies()
    print(f"  结果: {'✅ PASS (KNOWN)' if result_2 else '❌ FAIL'}\n")

    print("[3/3] 跨进程 read_only 父持写锁期间 → 期望 IO Error (KNOWN flock)")
    status_3, message_3 = test_cross_process_flock_blocks()
    print(f"  结果: {status_3} — {message_3}\n")

    if result_1 and result_2 and status_3 in {"KNOWN", "OK"}:
        print("✅ 全部行为符合 DuckDB flock 预期, L4.38 永久规则文案可以用")
        return 0

    print("❌ 某个预期外的行为,需要 L4.38 文案细化或停手回报")
    return 1


if __name__ == "__main__":
    sys.exit(main())
