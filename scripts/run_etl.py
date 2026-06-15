"""
芙清 CRM - ETL 入口脚本（薄包装层）
实际实现已拆分到 scripts/etl/ 包中。

用法不变：
  python run_etl.py                    # 自动检测：数据库空则全量，有数据则增量
  python run_etl.py --full             # 强制全量重建
  python run_etl.py --inc              # 强制增量
  python run_etl.py --update           # 一键增量更新（ETL+淘客+状态刷新）
  python run_etl.py --rescan-spu --product-ids 1008376905465 --dry-run
  python run_etl.py --rescan-spu --product-ids 1008376905465 --apply
  python run_etl.py --rescan-channel --dry-run
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 向后兼容：从 scripts.etl 导入所有公共 API
# 其他脚本仍然可以 from scripts.run_etl import xxx

if __name__ == '__main__':
    from scripts.etl.cli import main
    from scripts.etl._timer import PerfTimer, save_baseline, gate_set
    from datetime import datetime
    import os

    # P0 修复: 之前 run_id 默认 '1/3' 写死 → _timer.py 的自增分支永远走不到 →
    # 同 baseline_date 多次跑批互相覆盖（task#59 P1 修复因此完全失效，证据：
    # baseline_2026_06_03.json 只有 1 条 run_id='1/3'）。改为默认 None，
    # 让 save_baseline() 走 _timer.py 内的自增逻辑（读 existing_runs 长度 +1）。
    # 如果用户显式传 ETL_RUN_ID 环境变量则尊重显式值（向后兼容）。
    run_id = os.environ.get("ETL_RUN_ID") or None
    _total_timer = PerfTimer("etl_total", run_id=run_id)
    _total_timer.__enter__()
    try:
        main()
    except Exception as exc:
        from scripts.etl._timer import gate_record_error
        gate_record_error("etl_total", exc)
        raise
    finally:
        # 6 道门禁：尝试写 date_sanity / business_smooth（其他门禁由各 step 写）
        try:
            from backend.config import DUCKDB_PATH
            import duckdb as _dd
            from backend.config import DUCKDB_MEMORY_LIMIT
            if DUCKDB_PATH.exists():
                _c = _dd.connect(str(DUCKDB_PATH), read_only=True, config={"memory_limit": DUCKDB_MEMORY_LIMIT})
                try:
                    row = _c.execute("""
                        SELECT
                            MIN(pay_time), MAX(pay_time),
                            AVG(CASE WHEN is_refund THEN 1.0 ELSE 0.0 END),
                            AVG(CASE WHEN is_goujinjin THEN 1.0 ELSE 0.0 END)
                        FROM orders
                    """).fetchone()
                    if row and row[0] is not None:
                        min_pt, max_pt, refund_rate, gj_rate = row
                        now = datetime.now()
                        future_days = (max_pt - now).days if max_pt else 0
                        past_years = (now - min_pt).days / 365.25 if min_pt else 0
                        gate_set(
                            "date_sanity", "pass",
                            checked=True,
                            min_pay_time=str(min_pt),
                            max_pay_time=str(max_pt),
                            future_days=future_days,
                            past_years=round(past_years, 2),
                        )
                        gate_set(
                            "business_smooth", "pass",
                            checked=True,
                            refund_rate=round(float(refund_rate or 0), 4),
                            goujinjin_rate=round(float(gj_rate or 0), 4),
                        )
                finally:
                    _c.close()
        except Exception:
            pass
        # 关闭 etl_total 计时（含失败时的 wall_time）
        _total_timer.__exit__(None, None, None)
        # 落盘
        save_baseline(run_id=run_id)
