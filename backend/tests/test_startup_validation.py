"""
Sprint 61 P2 治本 — startup validation 测试.

根因: uvicorn PID 29564 接错 798KB 空 schema DB, 健康检查绿 + 200 OK + 全 0 数据
("静默失真" 模式, 跟 Sprint 60+ 4 个 500 error 同类).

本测试覆盖 backend.main.validate_startup_db() 在 5 种场景的行为:
1. production 模式 + orders 0 行 → RuntimeError
2. production 模式 + orders.max(pay_time) < today-30d → RuntimeError
3. production 模式 + 100 row + today max(pay_time) → pass
4. schema_test 模式 + orders 0 行 → pass (只 WARN)
5. 未知 mode (FQ_DB_MODE=foo) → 默认 production 行为
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def fresh_db(tmp_path: Path):
    """创建一个临时 DuckDB 文件，path 返回给 test. 不建 orders 表 → 空库."""
    db_path = tmp_path / "test_startup.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.close()
    return db_path


def _create_orders_table(db_path: Path, rows: list[tuple]) -> None:
    """写入 orders 表 + pay_time 列 (跟生产契约一致)."""
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE orders (
                order_id VARCHAR,
                pay_time TIMESTAMP,
                gsv DOUBLE
            )
            """
        )
        if rows:
            conn.executemany(
                "INSERT INTO orders VALUES (?, ?, ?)",
                rows,
            )
    finally:
        conn.close()


def _set_db_mode(monkeypatch: pytest.MonkeyPatch, value):
    """设置 FQ_DB_MODE 环境变量 (None 表示 unset, 其他值都 str)."""
    if value is None:
        monkeypatch.delenv("FQ_DB_MODE", raising=False)
    else:
        monkeypatch.setenv("FQ_DB_MODE", str(value))


def _call_validate(monkeypatch: pytest.MonkeyPatch, db_path: Path):
    """调用 validate_startup_db, 临时把 DUCKDB_PATH 指到 tmp_path."""
    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    # 重新 import 防止 module-level DB_MODE / DUCKDB_PATH 缓存
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("backend.main", "backend.config"):
            del sys.modules[mod_name]
    from backend.main import validate_startup_db
    return validate_startup_db


def test_production_rejects_empty_orders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """production 模式 + orders 0 行 → RuntimeError."""
    db_path = tmp_path / "empty.duckdb"
    # 建空 orders 表 (跟"接错空 schema DB"语义一致)
    _create_orders_table(db_path, [])
    _set_db_mode(monkeypatch, None)  # 默认 production

    validate_startup_db = _call_validate(monkeypatch, db_path)
    with pytest.raises(RuntimeError, match="orders.*为空"):
        validate_startup_db()


def test_production_rejects_stale_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """production 模式 + orders.max(pay_time) < today-30d → RuntimeError."""
    db_path = tmp_path / "stale.duckdb"
    stale_pay_time = datetime.now() - timedelta(days=60)
    _create_orders_table(
        db_path,
        [
            (f"order_{i}", stale_pay_time, 100.0 * i)
            for i in range(10)
        ],
    )
    _set_db_mode(monkeypatch, None)  # 默认 production

    validate_startup_db = _call_validate(monkeypatch, db_path)
    with pytest.raises(RuntimeError, match="距今.*天.*阈值"):
        validate_startup_db()


def test_production_accepts_healthy_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """production 模式 + 100 row + today max(pay_time) → pass (不抛异常)."""
    db_path = tmp_path / "healthy.duckdb"
    now = datetime.now()
    _create_orders_table(
        db_path,
        [(f"order_{i}", now - timedelta(hours=i), 100.0 * i) for i in range(100)],
    )
    _set_db_mode(monkeypatch, None)

    validate_startup_db = _call_validate(monkeypatch, db_path)
    # 不抛异常即 pass
    validate_startup_db()


def test_schema_test_skips_data_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """schema_test 模式 + orders 0 行 → pass (只 WARN log, 不抛异常)."""
    db_path = tmp_path / "schema_test.duckdb"
    _create_orders_table(db_path, [])
    _set_db_mode(monkeypatch, "schema_test")

    validate_startup_db = _call_validate(monkeypatch, db_path)
    # schema_test 模式: 不抛异常, 跳过数据量/新鲜度校验
    validate_startup_db()


def test_unknown_mode_defaults_production(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """FQ_DB_MODE=foo (未知值) → 默认 production 行为, 0 行 → RuntimeError."""
    db_path = tmp_path / "unknown.duckdb"
    _create_orders_table(db_path, [])
    _set_db_mode(monkeypatch, "foo")

    validate_startup_db = _call_validate(monkeypatch, db_path)
    with pytest.raises(RuntimeError, match="orders.*为空"):
        validate_startup_db()
