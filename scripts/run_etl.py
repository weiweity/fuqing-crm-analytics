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
    main()
