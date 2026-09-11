"""GSV 口径谓词以 calculations.GSV_PREDICATE 为 SSOT；数字与手算一致。"""
from pathlib import Path

import duckdb

from backend.semantic.calculations import GSV_AMOUNT_COL, GSV_PREDICATE, gsv_amount_expr
from backend.semantic.filters import AmountExprBuilder, FilterBuilder, MetricType, OrderFilters
from backend.semantic.metrics import METRICS

ROOT = Path(__file__).resolve().parents[2]
NEEDLE = "is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE"


def test_gsv_predicate_is_defined_once_and_imported():
    calc = (ROOT / "backend/semantic/calculations.py").read_text(encoding="utf8")
    filters = (ROOT / "backend/semantic/filters.py").read_text(encoding="utf8")
    metrics = (ROOT / "backend/semantic/metrics.py").read_text(encoding="utf8")
    assert calc.count(NEEDLE) == 1
    assert NEEDLE not in filters
    assert NEEDLE not in metrics
    assert "from backend.semantic.calculations import" in filters
    assert "GSV_PREDICATE" in filters
    assert "GSV_AMOUNT_COL" in metrics
    assert "GSV_PREDICATE" in metrics


def test_gsv_amount_expr_matches_ssot_for_default_column():
    assert GSV_PREDICATE == NEEDLE
    assert gsv_amount_expr() == GSV_AMOUNT_COL
    assert gsv_amount_expr("actual_amount") == GSV_AMOUNT_COL
    assert "order_amount" in gsv_amount_expr("order_amount")


def test_filters_and_metrics_consume_ssot():
    assert OrderFilters.valid_order() == (GSV_PREDICATE, [])
    assert AmountExprBuilder.gsv() == GSV_AMOUNT_COL
    assert AmountExprBuilder.sum_gsv() == f"SUM({GSV_AMOUNT_COL})"
    builder = FilterBuilder().with_metric_type(MetricType.GSV)
    assert GSV_AMOUNT_COL in builder.build_amount_expr()
    assert GSV_PREDICATE in builder.build_count_expr()
    assert METRICS["gsv"].sql_expr == f"SUM({GSV_AMOUNT_COL})"
    assert GSV_PREDICATE in METRICS["member_gsv"].sql_expr
    assert GSV_PREDICATE in METRICS["gsv_order_count"].sql_expr


def test_gsv_ssot_and_builders_agree_on_in_memory_orders():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE orders (
            actual_amount DOUBLE,
            is_goujinjin BOOLEAN,
            order_status VARCHAR,
            is_refund BOOLEAN
        )
        """
    )
    conn.execute(
        """
        INSERT INTO orders VALUES
            (100, FALSE, '交易成功', FALSE),
            (50, TRUE, '交易成功', FALSE),
            (30, FALSE, '交易关闭', FALSE),
            (20, FALSE, '交易成功', TRUE)
        """
    )
    ssot = conn.execute(f"SELECT SUM({GSV_AMOUNT_COL}) FROM orders").fetchone()[0]
    builder = conn.execute(f"SELECT {AmountExprBuilder.sum_gsv()} FROM orders").fetchone()[0]
    metric = conn.execute(f"SELECT {METRICS['gsv'].sql_expr} FROM orders").fetchone()[0]
    conn.close()
    assert ssot == builder == metric == 100.0
