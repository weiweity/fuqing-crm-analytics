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
from scripts.etl.config import (
    COLUMN_MAPPING, SPU_COLUMNS, TAOKE_COL,
    _ETL_SOURCE_STATS,
)
from scripts.etl.sources import (
    load_spu_mapping, load_channel_rules,
    load_taoke_order_ids, load_live_order_ids, load_taoke_product_rules,
)
from scripts.etl.ingest import (
    load_data_files, rename_columns, parse_date,
)
from scripts.etl.transform import match_channel, clean_data
from scripts.etl.load import (
    init_database, write_to_duckdb, upsert_to_duckdb,
    filter_rolling_window, get_db_max_pay_time,
    calculate_daily_metrics, ensure_database_schema,
)
from scripts.etl.pipeline import (
    run_full_etl, update_taoke_channel,
    refresh_visitor_data, refresh_campaign_schedule,
)
from scripts.etl.cli import (
    backup_and_update_orders, rescan_channel, rescan_spu_mapping,
)

if __name__ == '__main__':
    from scripts.etl.cli import main
    main()
