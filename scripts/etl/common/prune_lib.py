"""Sprint 117 真 refactor: rename _prune_lib → prune_lib (修 #D11) + 4 项真治本 (修 #D11-#D14).

Sprint 116 抽 _prune_lib 解耦 cleanup_backups.py ↔ backup_duckdb.py (修 #D8).
Sprint 116 /review maintainability 反馈 4 项 defer:
- #D11: '_' 前缀违反 PEP 8 private 约定 (跨模块访问 private 符号)
- #D12: _matches_magic 返 False 时 log 丢 offset + actual magic bytes
- #D13: case-sensitive glob mismatch (macOS APFS case-preserving vs Linux HFS+ case-insensitive)
- #D14: longest-wins 依赖 dict iteration order (implicit contract)

Sprint 117 修:
- #D11: rename _prune_lib.py → prune_lib.py (PEP 8 public, 跟 scripts/etl/common/lark.py 命名一致)
- #D12: _matches_magic 改返 tuple[bool, str] (reason), caller log 完整信息 (offset + actual magic)
- #D13: case-insensitive 匹配 (Path(p).suffix.lower() 跟 MAGIC_CHECKS key 都 lowercase)
- #D14: 显式 sort longest first (sorted(MAGIC_CHECKS, key=len, reverse=True)), 不依赖 insertion order

(解耦 from #D8 持续生效: cleanup_backups.py 不 import backup_duckdb, 避免拉起 lark SDK 副作用)
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
#
# Sprint 117 修 #D14: 显式 sort longest-first (sorted(..., key=len, reverse=True)),
# 不依赖 Python 3.7+ dict insertion order. 后人加新 suffix 不会因 insertion 顺序引入 bug.
MAGIC_CHECKS: dict[str, tuple[bytes, int]] = {
    ".parquet": (b"PAR1", 0),
    ".duckdb": (b"DUCK", 8),
    ".duckdb.zst": (ZSTD_MAGIC, 0),
}


def _suffix_order() -> list[str]:
    """Sprint 117 修 #D14: 显式 longest-first 顺序, 不依赖 dict iteration order.

    后人加新 suffix 到 MAGIC_CHECKS 时, 不必担心 insertion 顺序问题:
    - .duckdb.zst (10) 排第一 (最长)
    - .duckdb (7) 排第二
    - .parquet (8) 排第三
    排序后顺序: [.duckdb.zst, .parquet, .duckdb] (按 len desc)
    """
    return sorted(MAGIC_CHECKS.keys(), key=len, reverse=True)


def _matches_magic(p: Path) -> tuple[bool, str]:
    """Sprint 117 修 #D12+#D13: per-extension magic check 返 tuple[bool, str].

    Returns (True, "matched {suffix}" or "trust caller (unknown suffix)") on success.
    Returns (False, reason) on mismatch — reason 包含 offset + actual magic 信息, 好诊断.

    Sprint 117 修 #D13: case-insensitive 匹配 (macOS APFS case-preserving
    vs Linux HFS+ default case-insensitive). 用 Path(p).suffix.lower() 跟
    MAGIC_CHECKS key 都 lowercase 比较.

    Sprint 117 修 #D14: 用 _suffix_order() 显式 sort longest first.
    """
    # Sprint 117 修 #D13: case-insensitive suffix 比较
    p_suffix = Path(p).suffix.lower()
    matched_suffix = None
    for suffix in _suffix_order():  # Sprint 117 修 #D14: 显式 sort
        # 比较时两边都 lowercase (MAGIC_CHECKS key 设计已经是 lowercase)
        if p_suffix == suffix.lower():
            matched_suffix = suffix
            break  # longest-first 排序, 第一个匹配就是 longest

    if matched_suffix is None:
        return True, f"trust caller (unknown suffix {p_suffix!r})"

    expected_magic, offset = MAGIC_CHECKS[matched_suffix]
    try:
        with open(p, "rb") as f:
            header = f.read(offset + 4)
        if len(header) < offset + 4:
            return False, f"file too small (read {len(header)} bytes, need {offset + 4})"
        actual_magic = header[offset:offset + 4]
        if actual_magic == expected_magic:
            return True, f"magic OK ({matched_suffix}: {expected_magic!r}@{offset})"
        # Sprint 117 修 #D12: log 完整信息 (expected vs actual, 都含 offset)
        return False, (
            f"magic mismatch for {matched_suffix}: "
            f"expected {expected_magic!r}@{offset}, got {actual_magic!r}@{offset}"
        )
    except OSError as e:
        return False, f"open failed: {e}"


def _prune_with_safety(
    backup_dir: Path,
    glob_patterns: tuple[str, ...],
    retention_days: int,
    keep_min: int,
    log_fn: Callable[[str], None],
) -> tuple[int, list[str]]:
    """Sprint 116 抽 shared _prune_with_safety (跨模块复用, 修 #D7+#D8+#D9).
    Sprint 117 修 #D12: 调 _matches_magic 拿 reason, log 完整信息.

    8 项 safety check:
      1. mtime age > retention (避免误删最新)
      2. 保留 keep_min 最新份 (防 cap=0 误删全部)
      3. 文件 > 0 字节 (防空文件假象)
      4. per-extension magic check (#D7 修: PAR1 / DUCK / ZSTD_MAGIC 跟 suffix 映射, 防误删非对应格式;
         Sprint 117 修 #D12+#D13: tuple 返值 + case-insensitive, 完整 log reason)
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
        # 4: per-extension magic check (Sprint 116 修 #D7 + Sprint 117 修 #D12+#D13: tuple 返值)
        ok, reason = _matches_magic(p)
        if not ok:
            # Sprint 117 修 #D12: log 完整 reason (offset + actual magic)
            log_fn(f"prune: skip {p.name} ({reason})")
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
