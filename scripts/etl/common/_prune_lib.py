"""Sprint 116 抽 shared _prune_lib: cleanup_backups.py ↔ backup_duckdb.py 解耦 (修 #D8).

Sprint 112 抽 _prune_with_safety 后, cleanup_backups.py:`from scripts.etl import backup_duckdb`
拉起整个 backup_duckdb 模块, 包括 `from scripts.etl.common.lark import _send_lark_alert` +
lark SDK 加载 (即使 _prune_with_safety 路径不调 lark). 这是隐性 side effect
跟 Sprint 62 P3 launchd sandbox 教训同根因.

Sprint 116 修 #D8: 抽 scripts/etl/common/_prune_lib.py, 让 cleanup_backups.py + backup_duckdb.py
都从 _prune_lib import _prune_with_safety + constants. cleanup_backups.py 不再 import backup_duckdb,
backup_duckdb.py 仍然 import lark (因为 _send_lark_alert for loud_fail).

Sprint 116 同时修:
- #D7: 加 per-extension magic check table (PAR1 / DUCK / ZSTD_MAGIC, 修 Sprint 112 隐性 gap)
- #D9: 返 Tuple[int, list[str]] (cleanup_backups.py 拼回 '| files: ...' 字段, 修 observability regression)
"""
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Sprint 112 抽 shared: 跟 backup_duckdb.py 一致 BJ_TZ (UTC+8 = 北京时间)
# launchd 跑批 03:30 BJ + cleanup 03:00 BJ, 跨 sprint 同步.
BJ_TZ = timezone(timedelta(hours=8))

# Sprint 112 named const: Zstandard frame magic
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

# Sprint 116 named const: file suffix 跟 magic bytes + offset 映射 (修 #D7).
# Per-extension magic check 防误删非对应格式的文件 (e.g. 误 glob 到 *.txt 改名为 *.duckdb.zst).
# magic_at_offset 2-tuple: (magic_bytes, offset_in_header).
# - .parquet: PAR1 at offset 0 (Apache Parquet format spec)
# - .duckdb: DUCK at offset 8 (DuckDB v0.9+ standard marker, header magic + application ID)
# - .duckdb.zst: ZSTD_MAGIC at offset 0 (Sprint 62.5 治根 B1)
MAGIC_CHECKS: dict[str, tuple[bytes, int]] = {
    ".parquet": (b"PAR1", 0),
    ".duckdb": (b"DUCK", 8),
    ".duckdb.zst": (ZSTD_MAGIC, 0),
}


def _matches_magic(p: Path) -> bool:
    """Sprint 116 修 #D7: per-extension magic check.

    Returns True if file's magic header matches expected (or unknown suffix → trust caller).
    Returns False if magic mismatches → caller should skip via log_fn.
    """
    # 找最长匹配后缀 (优先 .duckdb.zst, 然后 .duckdb, 然后 .parquet, 然后其他)
    matched_suffix = None
    for suffix in MAGIC_CHECKS:
        if str(p).endswith(suffix):
            # 选最长匹配 (e.g. .duckdb.zst 优先 .duckdb)
            if matched_suffix is None or len(suffix) > len(matched_suffix):
                matched_suffix = suffix

    if matched_suffix is None:
        return True  # 未知后缀, trust caller

    expected_magic, offset = MAGIC_CHECKS[matched_suffix]
    try:
        with open(p, "rb") as f:
            header = f.read(offset + 4)
        if len(header) < offset + 4:
            return False  # 文件太小, 不可能是合法 magic
        actual_magic = header[offset:offset + 4]
        return actual_magic == expected_magic
    except OSError:
        return False  # open failed → 保守 skip (跟 lsof FileNotFoundError 一致)


def _prune_with_safety(
    backup_dir: Path,
    glob_patterns: tuple[str, ...],
    retention_days: int,
    keep_min: int,
    log_fn: Callable[[str], None],
) -> tuple[int, list[str]]:
    """Sprint 116 抽 shared _prune_with_safety (跨模块复用, 修 #D7+#D8+#D9).

    8 项 safety check:
      1. mtime age > retention (避免误删最新)
      2. 保留 keep_min 最新份 (防 cap=0 误删全部)
      3. 文件 > 0 字节 (防空文件假象)
      4. per-extension magic check (#D7 修: PAR1 / DUCK / ZSTD_MAGIC 跟 suffix 映射, 防误删非对应格式)
      5. lsof 0 fd (无活跃 fd, lsof 不可用时保守放行 #D10)
      6. caller-side invariant (本次刚生成的 mtime 极新不会超 retention 阈值)
      7. sorted by mtime desc (最新优先保留)
      8. soft fail (删失败 log 不 raise, #D10 lsof FileNotFoundError 走保守放行)

    Args:
        backup_dir: 要清理的目录 (e.g. BACKUP_DIR)
        glob_patterns: glob 模式 (e.g. ("*.parquet", "*.duckdb", "*.duckdb.zst"))
        retention_days: 保留天数
        keep_min: 至少保留最新 N 份 (防 cap=0 误删全部)
        log_fn: 日志函数 (e.g. backup_duckdb.log 或 cleanup_backups.log)

    Returns:
        (deleted_count, deleted_names) tuple. Sprint 116 修 #D9 改返 Tuple[int, list[str]]
        (vs Sprint 112 返 int). callers 拼回 '| files: ...' observability 字段.

    Sprint 116 改动:
    - 修 #D7: 加 _matches_magic() per-extension magic check (PAR1 / DUCK / ZSTD_MAGIC)
    - 修 #D8: 从 scripts/etl/common/_prune_lib.py export, cleanup_backups.py 不再 import backup_duckdb
    - 修 #D9: 返 Tuple[int, list[str]] (跟 Sprint 111 main() '| files: ...' observability 字段对齐)
    - 修 #D10: lsof FileNotFoundError 走保守放行 (Sprint 112 已实施, Sprint 116 加 test coverage)
    """
    try:
        all_files = []
        for pat in glob_patterns:
            all_files.extend(backup_dir.glob(pat))
        sorted_files = sorted(all_files, key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError as e:
        log_fn(f"prune: glob failed ({e}), skip")
        return 0, []

    if len(sorted_files) <= keep_min:
        log_fn(f"prune: {len(sorted_files)} file(s), <= keep_min={keep_min}, skip")
        return 0, []

    cutoff = datetime.now(BJ_TZ).timestamp() - retention_days * 86400
    candidates = [p for p in sorted_files[keep_min:] if p.stat().st_mtime < cutoff]

    deleted = 0
    deleted_names: list[str] = []
    for p in candidates:
        # 3: size > 0
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size <= 0:
            log_fn(f"prune: skip {p.name} (size={size})")
            continue
        # 4: per-extension magic check (Sprint 116 修 #D7)
        if not _matches_magic(p):
            log_fn(f"prune: skip {p.name} (magic check failed)")
            continue
        # 5: lsof 0 fd (Sprint 116 修 #D10: FileNotFoundError 保守放行已实施, 加 test coverage)
        try:
            out = subprocess.run(
                ["lsof", "-t", str(p)],
                capture_output=True, text=True, timeout=5,
            )
            if out.stdout.strip():
                log_fn(f"prune: skip {p.name} (lsof open: {out.stdout.strip()!r})")
                continue
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # lsof 不可用 / 超时 → 保守放行
        # 8: soft fail — 先算 age (unlink 前), 再 unlink, 再 log
        age_d = (datetime.now(BJ_TZ).timestamp() - p.stat().st_mtime) / 86400
        try:
            p.unlink()
            deleted += 1
            deleted_names.append(p.name)  # Sprint 116 修 #D9: 收集 deleted_names
            log_fn(f"prune: deleted {p.name} ({size / 1024 / 1024 / 1024:.1f} GiB, age={age_d:.1f}d)")
        except OSError as e:
            log_fn(f"prune: delete failed {p.name}: {e}")
    return deleted, deleted_names
