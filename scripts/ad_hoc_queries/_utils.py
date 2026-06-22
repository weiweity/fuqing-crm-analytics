"""
ad_hoc_queries._utils — 共享 utility 模块 (read_only DuckDB + semantic import + CSV/stdout).

Sprint 61 MVP 范围:
- read_only DuckDB 连接 (跟 uvicorn 共存, 跟 Sprint 53 race flake 治本同模式)
- semantic 层导入 (filters / calculations)
- 简化版 output formatter: stdout 表格 + CSV (不引 rich / openpyxl)
- /tmp/.etl_running.flag 检测 (Sprint 60+ 沉淀)

不做 (留 Sprint 62+):
- rich table 输出 (用 plain stdout)
- Excel 输出 (用 csv 替代)
- --format 枚举扩展
"""
from __future__ import annotations

import csv
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Sequence

# 把项目根加进 path, 跟 scripts/run_etl.py 一致
_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 复用 backend.config (跟 scripts/run_etl.py:49-53 模式一致)
from backend.config import DUCKDB_PATH, DUCKDB_MEMORY_LIMIT  # noqa: E402

# semantic 层 SSOT

# ETL 跑批中标记文件
ETL_RUNNING_FLAG = Path("/tmp/.etl_running.flag")
# audit log (跟 /ship .ship-audit.log 同模式)
AD_HOC_AUDIT_LOG = Path("/tmp/fuqing_adhoc_audit.log")


def check_etl_running() -> bool:
    """
    检测 ETL 跑批中标记. 存在 flag 文件 → True.
    Sprint 60+ 沉淀: ETL 跑批中查询可能卡顿 / 锁冲突.
    """
    return ETL_RUNNING_FLAG.exists()


@contextmanager
def read_only_conn(db_path: Path | None = None, memory_limit: str | None = None):
    """
    read_only DuckDB 上下文管理器.

    复用 scripts/run_etl.py:49-53 模式: read_only=True + 单独 memory_limit 不污染主进程.
    Sprint 53 race flake 治本后, 跟 uvicorn 共存安全.
    """
    import duckdb  # local import 避免启动慢

    path = db_path or DUCKDB_PATH
    limit = memory_limit or DUCKDB_MEMORY_LIMIT
    conn = duckdb.connect(str(path), read_only=True, config={"memory_limit": limit})
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def tmp_write_conn(
    name_prefix: str,
    db_path: Path | None = None,
    memory_limit: str | None = None,
):
    """
    Sprint 62.5 B3 治根: 写 /tmp 临时 DuckDB 必须走 TrackerDB.

    反向教训: Sprint 62 yoy-battle / channel-slice 测试时外部 Bash 直调
    `duckdb.connect("/private/tmp/fuqing_e2e_yoyb.duckdb")` 留下 109GB 永久孤儿,
    tracker 没 register, cleanup cap 100GB 兜不住. 治根: /ad-hoc-query 任何写 tmp
    duckdb 都必须走本 helper, 自动 register → TTL 过期清理.

    用法:
        with tmp_write_conn("fuqing_e2e_yoyb") as conn:
            conn.execute("...")  # 写到 /private/tmp/fuqing_e2e_yoyb.duckdb
        # 自动 unlink + tracker.remove (退出 with 块)

    Args:
        name_prefix: tracker 跟踪的 prefix (e.g. "fuqing_e2e_yoyb")
        db_path: 默认 /private/tmp/{name_prefix}.duckdb
    """
    import duckdb
    import os
    from scripts.etl.common import tmp_tracker as _tt_module
    _TrackerDBCls = _tt_module.TrackerDB

    path = db_path or Path(f"/private/tmp/{name_prefix}.duckdb")
    tracker = _TrackerDBCls()
    # pre-register (让 cleanup 即使异常也能追踪)
    try:
        tracker.register(str(path), size=0, pid=os.getpid())
    except Exception:
        pass

    conn = None
    try:
        limit = memory_limit or DUCKDB_MEMORY_LIMIT
        conn = duckdb.connect(str(path), config={"memory_limit": limit})
        yield conn
    finally:
        if conn is not None:
            conn.close()
        # exit 时 unlink + tracker remove (Sprint 62.5 治根: 不留孤儿)
        try:
            path.unlink()
        except OSError:
            pass
        try:
            tracker.remove(str(path))
        except Exception:
            pass


def log_audit(command: str, status: str, **fields: Any) -> None:
    """
    追加 audit 记录 (跟 /ship .ship-audit.log 同模式).
    失败静默 (Sprint 60+ 沉淀: 审计失败不该影响主流程).
    """
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        extra = " ".join(f"{k}={v}" for k, v in fields.items())
        line = f"{ts}\t{command}\t{status}\t{extra}\n"
        with AD_HOC_AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def format_stdout_table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    """
    简化版 stdout 表格 (MVP 范围, 不引 rich).
    列宽 = max(列名长, 列值 max 长), 用 | 分隔.
    """
    if not rows and not headers:
        return ""
    # 算列宽
    cols = len(headers)
    widths = [len(str(h)) for h in headers]
    for row in rows:
        # 补齐短行
        if len(row) < cols:
            row = list(row) + [""] * (cols - len(row))
        for i, v in enumerate(row[:cols]):
            widths[i] = max(widths[i], len(str(v)))
    # 构造行
    sep = "-+-".join("-" * w for w in widths)
    lines = []
    lines.append(" | ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    lines.append(sep)
    for row in rows:
        if len(row) < cols:
            row = list(row) + [""] * (cols - len(row))
        lines.append(" | ".join(str(v).ljust(w) for v, w in zip(row[:cols], widths)))
    return "\n".join(lines)


def _sanitize_path_component(name: str, max_length: int = 100) -> str:
    """
    Sanitize 文件/目录名组件 (Codex P1 fix).

    - 拒绝绝对路径 (/) 和 Windows 盘符 (C:\\)
    - 拒绝 .. 路径遍历
    - 替换路径分隔符 / \\ 和控制字符为 _
    - 截断到 max_length 字符
    - 空字符串 fallback 为 _unnamed
    """
    if not name:
        return "_unnamed"
    # 绝对路径前缀
    if os.path.isabs(name) or name.startswith("~"):
        name = os.path.basename(name)
    # 替换非法字符: 路径分隔符 + 控制字符 + Windows 保留字符
    sanitized = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    # 防 .. 路径遍历 (即便 sanitized 之后也不留 raw '..')
    if sanitized in (".", "..") or sanitized.startswith(".."):
        sanitized = "_" + sanitized
    # 截断
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized or "_unnamed"


def _check_take_root_containment(path: Path) -> None:
    """
    校验 path 在 TAKE_ROOT 内, 防路径逃逸 (Codex P1 fix).

    raise ValueError 如果 path 不在 TAKE_ROOT 内.
    """
    try:
        path.resolve().relative_to(TAKE_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(
            f"path {path} escapes TAKE_ROOT {TAKE_ROOT}: {exc}"
        ) from exc


def write_csv(rows: Iterable[Sequence[Any]], headers: Sequence[str], output_path: str | None = None) -> str:
    """
    写 CSV. 不传 output_path → 返 stdout 文本. 传了 → 写文件并返路径.
    路径冲突自动 timestamp suffix (Sprint 60+ 沉淀).
    Codex P2 fix: 微秒后缀 + 独占创建, 防同秒覆盖 (TOCTOU).

    注: user 显式 --output 参数不受 TAKE_ROOT containment 校验限制,
    只有自动路径生成 (build_take_path) 走 containment 校验.
    """
    import io
    from datetime import datetime
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    csv_text = buf.getvalue()
    if not output_path:
        return csv_text
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Codex P2: 独占创建防同秒覆盖 (TOCTOU)
    if out.exists():
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        out = out.with_name(f"{out.stem}_{suffix}{out.suffix}")
    # 再次独占创建 (O_EXCL 在 POSIX, macOS 支持)
    fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
    except FileExistsError:
        # 极小概率: 并发进程同微秒, 再次加 random suffix
        import secrets
        suffix = secrets.token_hex(4)
        out = out.with_name(f"{out.stem}_{suffix}{out.suffix}")
        fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
    return str(out)


# Sprint 61+ 取数目录规则 (user 拍板)
# 路径: ~/Desktop/fuqin date/取数/<年份>年/<年份>年<月>月<日>日/<基期年份>年-<生成日期>-<业务标签>/<file>.csv
# 任何 ad-hoc query 都走这个规则, 跨 sprint 一致.
# 测试隔离: FQ_TAKE_ROOT env 可覆盖, 默认绝对路径.
TAKE_ROOT = Path(os.environ.get("FQ_TAKE_ROOT", "/Users/hutou/Desktop/fuqin date/取数"))


def build_take_path(
    business_tag: str,
    base_year: int,
    date_range: str,
    file_name: str | None = None,
) -> Path:
    """
    按 Sprint 61+ 双层目录规则生成取数路径.

    规则:
    - 第 1 层: <年份>年 (按 base_year, 业务基期年份)
    - 第 2 层: <年份>年<月>月<日>日 (按当前生成日期)
    - 第 3 层: <基期年份>年-<生成日期>-<业务标签> (业务上下文)
    - 文件名 (默认): <file_name> 或自动 <business_tag>-<date_range>.csv

    Codex P1 fix: business_tag / file_name / base_year 全部 sanitize,
    防路径遍历 (../../../tmp/evil) + 绝对路径 + Windows 盘符 + 控制字符.

    Args:
        business_tag: 业务标签 (e.g. "新老客数据" / "RFM分布" / "渠道切片")
        base_year: 业务基期年份 (e.g. 2026 表示基期是 2026 年, 文件夹会出现在 2026年/)
        date_range: 日期范围字符串 (e.g. "2026-06-01至2026-06-21")
        file_name: 自定义文件名, 不传则默认 <business_tag>-<date_range>.csv

    Returns:
        完整文件路径 (Path, 不一定已存在, mkdir 在 write_csv 时统一做)

    Examples:
        >>> build_take_path("新老客数据", 2026, "2026-06-01至2026-06-21")
        /Users/hutou/Desktop/fuqin date/取数/2026年/2026年6月22日/2026年-2026年6月22日-新老客数据/新老客数据-2026-06-01至2026-06-21.csv

        >>> build_take_path("../../../tmp/evil", 2025, "2025-12-01至2025-12-31")
        /Users/hutou/Desktop/fuqin date/取数/2025年/2026年6月22日/2025年-2026年6月22日-.._.._.._tmp_evil/.._.._.._tmp_evil-2025-12-01至2025-12-31.csv
    """
    from datetime import datetime
    today = datetime.now()
    # Codex P1: sanitize business_tag (防 ../ + 绝对路径 + 控制字符)
    safe_tag = _sanitize_path_component(business_tag)
    # base_year 强制 int + 范围 (1000-9999, 防 -1, 0 等异常)
    if not isinstance(base_year, int) or base_year < 1000 or base_year > 9999:
        raise ValueError(f"base_year must be int 1000-9999, got {base_year!r}")
    year_layer = f"{base_year}年"
    date_layer = f"{today.year}年{today.month}月{today.day}日"
    context_layer = f"{base_year}年-{today.year}年{today.month}月{today.day}日-{safe_tag}"
    if file_name:
        # Codex P1: sanitize 用户自定义文件名
        file_name_final = _sanitize_path_component(file_name)
        # 强制 .csv 后缀
        if not file_name_final.endswith(".csv"):
            file_name_final += ".csv"
    else:
        # 自动文件名, sanitize file_name part
        safe_date_range = _sanitize_path_component(date_range, max_length=50)
        file_name_final = f"{safe_tag}-{safe_date_range}.csv"
    return TAKE_ROOT / year_layer / date_layer / context_layer / file_name_final


def resolve_output_path(
    user_output: str | None,
    business_tag: str,
    base_year: int,
    date_range: str,
) -> str | None:
    """
    解析最终输出路径. 优先级:
    1. user_output (--output 参数) → 直接用
    2. None → 走 build_take_path 默认双层目录规则

    Args:
        user_output: 用户传的 --output 参数 (None = 用默认目录)
        business_tag: 业务标签
        base_year: 基期年份
        date_range: 日期范围字符串

    Returns:
        完整路径字符串, 或 None (stdout 输出)
    """
    if user_output:
        return user_output
    return str(build_take_path(business_tag, base_year, date_range))
