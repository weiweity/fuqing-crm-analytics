"""
芙清 CRM - 订单状态覆盖表（Status Override）

架构：原始 orders 表永远不变（append-only），每天从源文件刷新状态到 override 表。
GSV 计算时 JOIN override 表，使用 latest_is_refund。

原始数据完整性 vs 状态刷新 完全隔离。
"""

import pandas as pd
import duckdb
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config import DUCKDB_MEMORY_LIMIT

# 语义层统一口径：base有效条件不含 is_refund（由 override 表处理）
_VALID_BASE = "is_goujinjin = FALSE AND order_status != '交易关闭'"
_VALID_BASE_T = "o.is_goujinjin = FALSE AND o.order_status != '交易关闭'"
from pathlib import Path

# QW0 埋点：etl_status_override 是 hot spot #5（66 次 N+1 DELETE = 3min）
# 入口/出口各打一次 perf_counter
try:
    from scripts.etl._timer import PerfTimer  # noqa: F401
except ImportError:
    class PerfTimer:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None


# =============================================================================
# 1. 状态覆盖表 DDL
# =============================================================================

def create_override_table(conn):
    """创建状态覆盖表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_status_override (
            order_id           VARCHAR PRIMARY KEY,
            latest_order_status VARCHAR,
            latest_is_refund   BOOLEAN,
            override_date      DATE
        )
    """)
    # 索引加速 JOIN
    conn.execute("CREATE INDEX IF NOT EXISTS idx_override_order_id ON order_status_override(order_id)")


# =============================================================================
# 2. 从 CSV 源文件提取订单状态（每日手动放置近30天 CSV）
# =============================================================================

def _read_csv_robust(csv_path: Path, dtype_map: dict = None) -> pd.DataFrame:
    """尝试多种编码读取 CSV，天猫导出可能是 GBK 或 UTF-8"""
    for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig']:
        try:
            df = pd.read_csv(csv_path, dtype=dtype_map, encoding=encoding)
            print(f"    CSV 编码: {encoding}")
            return df
        except UnicodeDecodeError:
            continue
        except Exception:
            break
    raise ValueError(f"无法读取 CSV: {csv_path}")


def _read_source_file(file_path: Path) -> pd.DataFrame:
    """根据后缀自动选择 CSV 或 xlsx 读取"""
    suffix = file_path.suffix.lower()
    if suffix == '.csv':
        return _read_csv_robust(file_path, dtype_map={'订单编号': str})
    elif suffix in ('.xlsx', '.xls'):
        return pd.read_excel(file_path, engine='openpyxl', header=0, dtype={'订单编号': str})
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def _extract_from_source_paths(file_paths: list, cutoff, window_days: int) -> list:
    """从一组 CSV/xlsx 路径中提取订单状态，返回 DataFrame 列表"""
    all_status = []
    for file_path in file_paths:
        try:
            df = _read_source_file(file_path)
            df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

            # 过滤：只保留最近 window_days 的付款记录
            if '付款时间' in df.columns:
                df['pay_time'] = pd.to_datetime(df['付款时间'], errors='coerce')
                df = df[df['pay_time'] >= pd.Timestamp(cutoff)]
                if df.empty:
                    print(f"  ⚠️ 文件中无 {window_days} 天内数据")
                    continue

            if '订单编号' not in df.columns:
                print("  ⚠️ 文件缺少 '订单编号' 列")
                continue

            # 提取关键字段
            order_ids = df['订单编号'].astype(str).str.strip()
            order_ids = order_ids[order_ids.notna() & (order_ids != '') & (order_ids != 'nan')]

            # 原始订单状态
            raw_status = df['子订单状态'].astype(str) if '子订单状态' in df.columns else pd.Series(['未知'] * len(df))

            # 原始退款状态
            if '退款状态' in df.columns:
                refund_status = df['退款状态'].astype(str)
                has_refund = refund_status.notna() & (refund_status.str.strip() != '')
            else:
                has_refund = pd.Series([False] * len(df), index=df.index)

            # 退款金额 > 0
            if '退款金额' in df.columns:
                refund_amt = pd.to_numeric(df['退款金额'], errors='coerce').fillna(0)
                has_refund = has_refund | (refund_amt > 0)

            # 计算 is_refund
            status_str = raw_status
            is_refund = (
                status_str.str.contains('交易关闭', na=False) |
                status_str.str.contains('退款', na=False) |
                has_refund
            )

            # 同一 order_id 可能出现多次，取最新付款时间的那条
            temp = pd.DataFrame({
                'order_id': order_ids.values,
                'latest_order_status': raw_status.values,
                'latest_is_refund': is_refund.values,
                'pay_time': df['pay_time'].values
            })

            all_status.append(temp)
            print(f"    读取成功: {len(df):,} 行 → 过滤后 {len(temp):,} 行")

        except Exception as e:
            print(f"  ⚠️ 读取失败 ({file_path.name}): {e}")
            continue
    return all_status


def extract_recent_order_status(
    data_source: Path,
    window_days: int = 30
) -> pd.DataFrame:
    """
    从源文件提取最近 N 天的订单状态。

    策略（v2.1）：
      1. 优先读取 data_source 目录下今天放入的最新 .zip 文件
      2. zip 自动解压到临时目录，读取其中 csv/xlsx
      3. 无 zip 时 fallback 到 .csv / .xlsx
      4. 无今日文件时返回空 DataFrame（不再递归扫描旧文件）

    返回: DataFrame，列 = [order_id, latest_order_status, latest_is_refund, override_date]
    """
    import zipfile
    import tempfile
    import shutil

    print(f"\n提取最近 {window_days} 天订单状态...")

    cutoff = datetime.now() - timedelta(days=window_days)

    # —— 模式 A：读取今天放入的最新文件（zip 优先，兼容 csv/xlsx）——
    today = datetime.now().date()
    all_files = []
    for pattern in ["*.zip", "*.csv", "*.xlsx"]:
        all_files.extend(data_source.glob(pattern))

    today_files = sorted(
        [f for f in all_files
         if datetime.fromtimestamp(f.stat().st_mtime).date() == today],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if not today_files:
        print("  目录中无今日状态文件，跳过状态刷新")
        return pd.DataFrame(columns=['order_id', 'latest_order_status', 'latest_is_refund'])

    latest_file = today_files[0]
    print(f"  [模式: {latest_file.suffix}] 读取今日文件: {latest_file.name}")

    source_paths = []
    temp_dir = None

    # zip 解压
    if latest_file.suffix.lower() == '.zip':
        try:
            temp_dir = tempfile.mkdtemp(prefix="status_override_")
            with zipfile.ZipFile(latest_file, 'r') as zf:
                zf.extractall(temp_dir)
            # 扫描解压后的 csv 和 xlsx
            for pattern in ["*.csv", "*.xlsx"]:
                source_paths.extend(sorted(Path(temp_dir).rglob(pattern), key=lambda f: f.stat().st_mtime, reverse=True))
            if not source_paths:
                print("  ⚠️ zip 中无 csv/xlsx 文件")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return pd.DataFrame(columns=['order_id', 'latest_order_status', 'latest_is_refund'])
        except Exception as e:
            print(f"  ⚠️ zip 解压失败: {e}")
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return pd.DataFrame(columns=['order_id', 'latest_order_status', 'latest_is_refund'])
    else:
        source_paths = [latest_file]

    all_status = _extract_from_source_paths(source_paths, cutoff, window_days)

    # 清理临时目录
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if not all_status:
        print("  ⚠️ 未提取到任何状态数据")
        return pd.DataFrame(columns=['order_id', 'latest_order_status', 'latest_is_refund'])

    combined = pd.concat(all_status, ignore_index=True)

    # 同一 order_id 多条记录：取 pay_time 最晚的那条状态
    combined['pay_time'] = pd.to_datetime(combined['pay_time'], errors='coerce')
    combined = combined.sort_values('pay_time', ascending=False)
    latest = combined.drop_duplicates(subset='order_id', keep='first')

    result = latest[['order_id', 'latest_order_status', 'latest_is_refund']].copy()
    result['override_date'] = datetime.now().date()

    print(f"  提取到 {len(result):,} 个订单的最新状态")
    print(f"  其中退款订单: {result['latest_is_refund'].sum():,} ({result['latest_is_refund'].mean()*100:.1f}%)")

    return result


# =============================================================================
# 3. 增量刷新状态覆盖表（仅店铺，CSV 日更新）
# =============================================================================

def refresh_status_override(
    db_path: Path,
    shop_source: Path = None,
    window_days: int = 30
):
    """
    增量刷新状态覆盖表：
      1. 从店铺源文件提取最近 window_days 的订单状态
      2. UPSERT 到 order_status_override 表

    不修改 orders 表，只修改 override 表。
    """
    # QW0 埋点 — hot spot #5（66 次 N+1 DELETE = 3min）
    _rt_timer = PerfTimer("etl_status_override_refresh", window_days=window_days)
    _rt_timer.__enter__()
    try:
        return _refresh_status_override_impl(db_path, shop_source, window_days)
    finally:
        _rt_timer.__exit__(None, None, None)


def _refresh_status_override_impl(db_path: Path, shop_source: Path = None, window_days: int = 30):
    """refresh_status_override 实际实现（被 QW0 埋点包裹）"""
    from backend.config import SHOP_STATUS_REFRESH_DIR

    if shop_source is None:
        shop_source = SHOP_STATUS_REFRESH_DIR

    print("\n" + "=" * 50)
    print(f"刷新订单状态覆盖表 (窗口: {window_days}天)")
    print(f"源路径: {shop_source}")
    print("=" * 50)

    conn = duckdb.connect(str(db_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT})

    # 确保表存在
    create_override_table(conn)

    # 统计刷新前
    before_count = conn.execute("SELECT COUNT(*) FROM order_status_override").fetchone()[0]
    before_refund = conn.execute(
        "SELECT SUM(CASE WHEN latest_is_refund THEN 1 ELSE 0 END) FROM order_status_override"
    ).fetchone()[0] or 0
    print(f"  刷新前: {before_count:,} 条记录，退款订单: {before_refund:,}")

    # 从店铺源文件提取状态（仅店铺，会员日更新不需要）
    shop_status = extract_recent_order_status(shop_source, window_days)

    if shop_status.empty:
        print("  ⚠️ 未提取到任何订单状态数据")
        conn.close()
        return

    # UPSERT：先删除这些 order_id 的旧记录，再插入新记录
    order_ids = shop_status['order_id'].tolist()
    batch_size = 5000
    deleted_total = 0

    for i in range(0, len(order_ids), batch_size):
        batch = order_ids[i:i + batch_size]
        placeholders = ','.join(["'{}'".format(str(oid).replace("'", "''")) for oid in batch])
        before_del = conn.execute(
            f"SELECT COUNT(*) FROM order_status_override WHERE order_id IN ({placeholders})"
        ).fetchone()[0]
        conn.execute(f"DELETE FROM order_status_override WHERE order_id IN ({placeholders})")
        deleted_total += before_del

    # 批量插入新状态（覆盖式写入：今天读到的订单状态是最新的）
    import tempfile
    import os
    parquet_path = os.path.join(tempfile.gettempdir(), 'status_override.parquet')
    shop_status[['order_id', 'latest_order_status', 'latest_is_refund', 'override_date']].to_parquet(
        parquet_path, index=False
    )

    conn.execute("""
        INSERT INTO order_status_override (order_id, latest_order_status, latest_is_refund, override_date)
        SELECT order_id, latest_order_status, latest_is_refund, override_date
        FROM '{parquet_path}'
    """.format(parquet_path=parquet_path))
    os.remove(parquet_path)

    # 滚动清理：删除 override_date 超过 window_days 的过期记录
    cutoff_date = (datetime.now() - timedelta(days=window_days)).date()
    expired = conn.execute(
        "SELECT COUNT(*) FROM order_status_override WHERE override_date < ?",
        [cutoff_date]
    ).fetchone()[0]
    if expired > 0:
        conn.execute(
            "DELETE FROM order_status_override WHERE override_date < ?",
            [cutoff_date]
        )
        print(f"  滚动清理: 删除 {expired:,} 条过期记录（{cutoff_date} 之前）")

    # 统计刷新后
    after_count = conn.execute("SELECT COUNT(*) FROM order_status_override").fetchone()[0]
    after_refund = conn.execute(
        "SELECT SUM(CASE WHEN latest_is_refund THEN 1 ELSE 0 END) FROM order_status_override"
    ).fetchone()[0] or 0

    print("  刷新完成:")
    print(f"    删除旧记录: {deleted_total:,}")
    print(f"    写入新状态: {len(shop_status):,}")
    print(f"    刷新后合计: {after_count:,} 条记录，退款订单: {after_refund:,}")

    conn.close()


# =============================================================================
# 4. 反向同步：override 表 → orders 表
# =============================================================================

def sync_override_to_orders(db_path: Path, window_days: int = 30) -> int:
    """
    将 order_status_override 表中的最新状态反向同步到 orders 表。

    只同步窗口内订单（默认30天），历史订单不动。
    同步后 orders.is_refund 和 order_status 即为最新状态，
    所有看板 SQL 无需改动即可拿到正确 GSV。

    返回: 实际更新的行数
    """
    print("\n" + "=" * 50)
    print(f"反向同步 override → orders (窗口: {window_days}天)")
    print("=" * 50)

    conn = duckdb.connect(str(db_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        # 检查 override 表是否存在
        table_exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'order_status_override'"
        ).fetchone()[0] > 0
        if not table_exists:
            print("  ⚠️ order_status_override 表不存在，跳过反向同步")
            return 0

        # 检查 override 表是否有数据
        override_count = conn.execute("SELECT COUNT(*) FROM order_status_override").fetchone()[0]
        if override_count == 0:
            print("  ⚠️ order_status_override 表为空，跳过反向同步")
            return 0

        # 刷新前统计
        before = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE is_refund = TRUE"
        ).fetchone()[0]

        # DuckDB UPDATE...FROM 语法
        # 先统计匹配行数（DuckDB 无 changes()）
        updated = conn.execute(f"""
            SELECT COUNT(*)
            FROM orders o
            JOIN order_status_override s ON o.order_id = s.order_id
            WHERE DATE(o.pay_time) >= CURRENT_DATE - INTERVAL '{window_days} days'
        """).fetchone()[0]

        conn.execute(f"""
            UPDATE orders
            SET is_refund = s.latest_is_refund,
                order_status = s.latest_order_status
            FROM order_status_override s
            WHERE orders.order_id = s.order_id
              AND DATE(orders.pay_time) >= CURRENT_DATE - INTERVAL '{window_days} days'
        """)

        after = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE is_refund = TRUE"
        ).fetchone()[0]

        print(f"  更新行数: {updated:,}")
        print(f"  退款订单: {before:,} → {after:,}")
        return updated
    finally:
        conn.close()


# =============================================================================
# 5. GSV 计算改用 override 表（替换语义层中的 is_refund 判断）
# =============================================================================

GSV_OVERRIDE_SQL = """
-- 订单状态覆盖表 JOIN（每日刷新）
-- 原始 orders.is_refund 和 order_status 保留不变
-- GSV 计算使用 COALESCE(override.latest_is_refund, orders.is_refund)
-- 这样即使原始 ETL 时是"交易成功"，30天内变成"交易关闭"，GSV 也会正确排除

SELECT
    SUM(CASE WHEN
        {_VALID_BASE}
        AND COALESCE(
            (SELECT latest_is_refund FROM order_status_override os WHERE os.order_id = orders.order_id LIMIT 1),
            is_refund
        ) = FALSE
    THEN actual_amount ELSE 0 END) AS gsv
FROM orders
WHERE pay_time >= ? AND pay_time <= ?
"""

# 等价形式（用 LEFT JOIN）：
GSV_OVERRIDE_JOIN_SQL = """
SELECT
    SUM(CASE WHEN
        {_VALID_BASE_T}
        AND COALESCE(s.latest_is_refund, o.is_refund) = FALSE
    THEN o.actual_amount ELSE 0 END) AS gsv
FROM orders o
LEFT JOIN order_status_override s ON o.order_id = s.order_id
WHERE o.pay_time >= ? AND o.pay_time <= ?
"""


# =============================================================================
# 5. 重建状态覆盖表（全量，从 orders 表反推 + 源文件补充）
# =============================================================================

def rebuild_override_from_orders(db_path: Path):
    """
    从 orders 表重建状态覆盖表（基于原始 is_refund / order_status）。
    用于初始化或 override 表损坏时。
    """
    print("\n从 orders 表重建状态覆盖表...")

    conn = duckdb.connect(str(db_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    create_override_table(conn)

    # 清空
    conn.execute("DELETE FROM order_status_override")

    # 从 orders 导入（原始值）
    conn.execute("""
        INSERT INTO order_status_override
        SELECT
            order_id,
            order_status AS latest_order_status,
            is_refund AS latest_is_refund,
            DATE(pay_time) AS override_date
        FROM orders
        WHERE order_id IS NOT NULL
    """)

    count = conn.execute("SELECT COUNT(*) FROM order_status_override").fetchone()[0]
    print(f"  重建完成: {count:,} 条记录")
    conn.close()


# =============================================================================
# 使用指南
# =============================================================================
USAGE = """
═══════════════════════════════════════════════════════════════════════════════
芙清 CRM 订单状态覆盖表 - 使用指南
═══════════════════════════════════════════════════════════════════════════════

【架构设计】
  orders                    order_status_override
  ├─ 原始/静态              ├─ 每天刷新/动态
  ├─ Append-only            ├─ UPSERT 最新状态
  └─ 1028万行               └─ 仅30天窗口（可调整）
       │
       │ GSV 计算时 JOIN
       ▼
  所有业务指标查询

【每日状态刷新流程（CSV 模式）】
  1. 每天从 ERP/OMS 导出近30天订单 CSV
  2. 手动复制 CSV 到: /Users/hutou/Desktop/fuqin-date/芙清CRM数据库/芙清crm原始数据库/
  3. 运行状态刷新:
     cd "<项目根目录>"
     PYTHONPATH="." python -c "
     from scripts.etl_status_override import refresh_status_override;
     from backend.config import DUCKDB_PATH;
     refresh_status_override(DUCKDB_PATH, window_days=30)
     "

【命令行参数】
  --refresh-status          仅刷新状态覆盖表（不跑 ETL）
  --rebuild-override        从 orders 表全量重建 override 表
  --window-days N           状态刷新窗口天数（默认30）

【CSV 文件要求】
  - 文件名任意（.csv 后缀）
  - 编码: UTF-8 或 GBK（自动检测）
  - 必需列: 订单编号、付款时间、子订单状态
  - 可选列: 退款状态、退款金额（用于判断 is_refund）
  - 每天只需放最新的一个 CSV，脚本自动取最新文件

【语义层改造】
  状态覆盖表就绪后，需要将 backend/semantic/calculations.py 中的 GSV 计算
  从直接用 orders.is_refund 改为 COALESCE(override.latest_is_refund, orders.is_refund)。

  可在 filters.py 中新增：
    def valid_order_with_override():
        return (
            _VALID_BASE
            "AND COALESCE((SELECT latest_is_refund FROM order_status_override os WHERE os.order_id = orders.order_id LIMIT 1), is_refund) = FALSE",
            []
        )

【为什么只保留30天窗口的 override】
  30天前的订单状态基本稳定（退款周期已过），
  且 orders 表中 is_refund 的原始值本身就是"导入时"的状态。
  真正需要追踪变化的是近30天的新订单。

【状态覆盖表数据量】
  orders 表 1028万行，override 表只有 30天 × 约1万单/天 ≈ 30万行。
  极小，JOIN 成本可忽略。

═══════════════════════════════════════════════════════════════════════════════
"""

if __name__ == '__main__':
    print(USAGE)
