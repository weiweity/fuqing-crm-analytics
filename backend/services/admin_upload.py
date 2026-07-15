"""Sprint 205+ Admin Upload Sprint 1 服务层（v5 prompt §3 + §4 + §5）。

职责:
- 10 种 business_type 服务端 allowlist (admin.py 调用)
- 文件名校验 (空 / . / .. / NUL / 路径分隔符 / Path(name).name 完整性 / unicode normalize)
- 100MB 流式写入 + SHA-256 累计 (1MB chunk)
- preflight 校验 (CSV/XLSX/ZIP + 业务最小列)
- staging 目录管理 (data/processed/admin_uploads/staging/{upload_id}/payload{ext})
- upload registry fcntl.flock + 原子写 + .bak 恢复
- 幂等 (Idempotency-Key + business_type + sha256)
- 重复 (business_type + sha256, active status)

禁止:
- 不依赖 FastAPI Request / HTTPException (跟 L4.50 + L4.5 1:1 stable 永久规则链配套)
- 不重命名 / 删除正式 raw 数据源
- 不读 / 写 ETL pipeline 内部状态
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# pandas + openpyxl 是 Sprint 3+ 已经在 backend/services/* 大量使用的依赖
# (跟 L4.50 + L4.54 1:1 stable 永久规则化沿用)
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 服务端硬上限 (跟 v5 prompt §"验证命令" 1:1 stable)
# ─────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB

# L1 修法: Idempotency-Key 约束 (跟 v5 prompt §"API 端点" 1:1 stable)
IDEMPOTENCY_KEY_MAX_LENGTH = 128

# staging 根目录 (跟 v5 prompt §"Sprint 1 只上传到 staging" 1:1 stable)
_DEFAULT_STAGING_ROOT = Path(__file__).resolve().parents[2] / "data" / "processed" / "admin_uploads" / "staging"
_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "upload_registry.json"
_DEFAULT_REGISTRY_LOCK = Path(__file__).resolve().parents[2] / "data" / "processed" / "upload_registry.lock"
_DEFAULT_REGISTRY_BACKUP = Path(__file__).resolve().parents[2] / "data" / "processed" / "upload_registry.json.bak"


# ─────────────────────────────────────────────────────────────
# 10 种数据源服务端 allowlist (跟 v5 prompt §3 1:1 stable)
#
# target_path 引用 backend.config 已解析的 Path 常量, 不重新拼接,
# 不硬编码 /Users/... (跟 L4.34 + L4.60 1:1 stable 永久规则化沿用).
# Sprint 1 不替换正式路径 (跟 v5 prompt §"Sprint 1 只上传到 staging" 1:1 stable).
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _SourceConfig:
    business_type: str
    display_name: str
    allowed_extensions: Tuple[str, ...]
    mode: str  # "append" | "single"
    target_path: Path
    validator_kind: str  # csv | xlsx | zip | spu-mapping-csv
    future_post_actions: Tuple[str, ...]
    replacement_warning: Optional[str] = None


def _build_sources() -> dict[str, _SourceConfig]:
    """懒加载 10 种数据源（不在 module-level import backend.config 避免循环依赖风险）"""
    from backend import config as _cfg

    return {
        "shop": _SourceConfig(
            business_type="shop",
            display_name="店铺订单数据",
            allowed_extensions=(".xlsx",),
            mode="append",
            target_path=_cfg.SHOP_DATA_SOURCE,
            validator_kind="xlsx",
            future_post_actions=("refresh-shop-orders",),
        ),
        "member": _SourceConfig(
            business_type="member",
            display_name="会员数据",
            allowed_extensions=(".xlsx",),
            mode="append",
            target_path=_cfg.MEMBER_DATA_SOURCE,
            validator_kind="xlsx",
            future_post_actions=("refresh-member",),
        ),
        "status-refresh": _SourceConfig(
            business_type="status-refresh",
            display_name="订单状态刷新 (ZIP / CSV)",
            allowed_extensions=(".zip", ".csv"),
            mode="single",
            target_path=_cfg.SHOP_STATUS_REFRESH_DIR,
            validator_kind="zip-or-csv",
            future_post_actions=("refresh-order-status",),
            replacement_warning="替换后, 现有 status-refresh 数据会被新文件覆盖; 仅当今日有最新订单状态刷新文件时使用。",
        ),
        "taoke": _SourceConfig(
            business_type="taoke",
            display_name="淘客订单数据",
            allowed_extensions=(".csv", ".xlsx", ".xls"),
            mode="append",
            target_path=_cfg.TAOKE_DATA_SOURCE,
            validator_kind="taoke",
            future_post_actions=("invalidate-taoke-cache",),
        ),
        "live": _SourceConfig(
            business_type="live",
            display_name="直播间数据",
            allowed_extensions=(".csv", ".xlsx"),
            mode="append",
            target_path=_cfg.LIVE_DATA_SOURCE,
            validator_kind="live",
            future_post_actions=("invalidate-live-cache",),
        ),
        "visitor": _SourceConfig(
            business_type="visitor",
            display_name="店铺访客数据",
            allowed_extensions=(".xlsx",),
            mode="single",
            target_path=_cfg.VISITOR_XLSX_FILE,
            validator_kind="visitor",
            future_post_actions=("refresh-visitor",),
            replacement_warning="替换后, 历史访客快照会被新文件覆盖。",
        ),
        "spu-mapping": _SourceConfig(
            business_type="spu-mapping",
            display_name="SPU 单品匹配表 (无 header)",
            allowed_extensions=(".csv",),
            mode="single",
            target_path=_cfg.SPU_MAPPING_SOURCE,
            validator_kind="spu-mapping",
            future_post_actions=("rescan-spu",),
            replacement_warning="替换后, 需要 Sprint 2 rescan-spu 才能让历史订单的 SPU 字段同步更新。",
        ),
        "taoke-product": _SourceConfig(
            business_type="taoke-product",
            display_name="淘客商品 ID 表",
            allowed_extensions=(".csv",),
            mode="single",
            target_path=_cfg.TAOKE_PRODUCT_SOURCE,
            validator_kind="taoke-product",
            future_post_actions=("invalidate-taoke-product-cache",),
            replacement_warning="替换后, Sprint 2 才会触发 taoke-product cache 重建。",
        ),
        "channel-rules": _SourceConfig(
            business_type="channel-rules",
            display_name="渠道判定规则",
            allowed_extensions=(".csv",),
            mode="single",
            target_path=_cfg.CHANNEL_RULES_SOURCE,
            validator_kind="channel-rules",
            future_post_actions=("rescan-channel",),
            replacement_warning="替换后, Sprint 2 才会触发渠道判定 rescan。",
        ),
        "campaign-schedule": _SourceConfig(
            business_type="campaign-schedule",
            display_name="全年平台活动节奏",
            allowed_extensions=(".csv",),
            mode="single",
            target_path=_cfg.CAMPAIGN_SCHEDULE_SOURCE,
            validator_kind="campaign-schedule",
            future_post_actions=("refresh-campaign-schedule",),
            replacement_warning="替换后, Sprint 2 才会触发 campaign_schedule 表刷新。",
        ),
    }


# B4 修法: 移除 module-level `_SOURCES` 缓存 (test 假绿根因).
# 每次 get_sources() 重新 _build_sources() — backend.config.* 的 Path 已经被
# monkeypatch, 立即生效, 不需要 test fixture 显式 reset.
def get_sources() -> dict[str, _SourceConfig]:
    """每次重读 backend.config Path, 返回 10 种数据源 allowlist.

    B4 修法配套:
    - 无 module-level cache (移除原 _SOURCES = None 缓存)
    - 每次调 _build_sources() 重新读 backend.config.SHOP_DATA_SOURCE 等
    - monkeypatch.setattr("backend.config.X", fake) 立即生效, 不需 reset 缓存
    - 性能开销: 10 个 _resolve_shop() 等 lambda 调用, 都是 Path 读取, < 1ms
    """
    return _build_sources()


def get_source(business_type: str) -> Optional[_SourceConfig]:
    return get_sources().get(business_type)


# ─────────────────────────────────────────────────────────────
# 文件名校验 (跟 v5 prompt §"文件名安全" 1:1 stable)
# ─────────────────────────────────────────────────────────────
_FILENAME_BAD_CHARS = re.compile(r"[\x00-\x1f/\\]")


def validate_filename(name: str) -> Tuple[bool, str]:
    """严格校验用户上传的 original_filename (跟 v5 prompt 1:1 stable).

    拒绝:
    - 空 / 仅空白
    - "." / ".."
    - 含 NUL 或控制字符
    - 含 "/" / "\\"
    - Path(name).name != name (说明含父路径)
    - Unicode normalize (NFC) 后为空
    - 扩展名不在 allowlist (不在本函数检查, 由 caller 检查)
    """
    if not name or not name.strip():
        return False, "文件名不能为空"
    if name in (".", ".."):
        return False, "文件名不能为 . 或 .."
    if _FILENAME_BAD_CHARS.search(name):
        return False, "文件名包含非法字符"
    if Path(name).name != name:
        return False, "文件名不能包含路径分隔符"
    if not unicodedata.normalize("NFC", name).strip():
        return False, "文件名 Unicode 归一化后为空"
    return True, ""


def validate_extension(name: str, allowed_extensions: Iterable[str]) -> Tuple[bool, str]:
    """校验扩展名（大小写不敏感）"""
    if not name:
        return False, "文件名不能为空"
    suffix = Path(name).suffix.lower()
    allowed = tuple(ext.lower() for ext in allowed_extensions)
    if not suffix or suffix not in allowed:
        return False, f"扩展名必须是 {'/'.join(allowed)}"
    return True, ""


# ─────────────────────────────────────────────────────────────
# 上传结果数据类 (跟 UploadRecordOut 1:1 stable, 但 service 层返回 dataclass)
# ─────────────────────────────────────────────────────────────
@dataclass
class UploadResult:
    upload_id: str
    business_type: str
    original_filename: str
    extension: str
    size_bytes: int
    sha256: str
    uploaded_by: str
    uploaded_at: datetime
    status: str = "staged"
    validation: Optional[dict] = None
    future_post_actions: List[str] = field(default_factory=list)
    idempotency_hit: bool = False  # True 表示命中已有记录 (返 HTTP 200)


# ─────────────────────────────────────────────────────────────
# 自定义异常 (供 router 层映射 HTTPException)
# ─────────────────────────────────────────────────────────────
class AdminUploadError(Exception):
    """服务层基类"""

    code: str = "ADMIN_UPLOAD_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, code: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(message)
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class FilenameInvalid(AdminUploadError):
    code = "INVALID_FILENAME"
    http_status = 400


class ExtensionInvalid(AdminUploadError):
    code = "INVALID_EXTENSION"
    http_status = 422


class UnknownBusinessType(AdminUploadError):
    code = "UNKNOWN_BUSINESS_TYPE"
    http_status = 400


class FileTooLarge(AdminUploadError):
    code = "PAYLOAD_TOO_LARGE"
    http_status = 413


class EmptyFile(AdminUploadError):
    code = "EMPTY_FILE"
    http_status = 400


class ValidationFailed(AdminUploadError):
    code = "VALIDATION_FAILED"
    http_status = 422


class DuplicateUpload(AdminUploadError):
    code = "DUPLICATE_UPLOAD"
    http_status = 409


class IdempotencyConflict(AdminUploadError):
    code = "IDEMPOTENCY_CONFLICT"
    http_status = 409


class IdempotencyKeyInvalid(AdminUploadError):
    """L1 修法: Idempotency-Key 违反约束 (空/whitespace/>128 字符)."""
    code = "IDEMPOTENCY_KEY_INVALID"
    http_status = 400


class RegistryCorrupt(AdminUploadError):
    code = "REGISTRY_CORRUPT"
    http_status = 500


# ─────────────────────────────────────────────────────────────
# preflight: CSV / XLSX / ZIP / 业务最小校验
# (跟 v5 prompt §"内容 preflight" 1:1 stable)
# ─────────────────────────────────────────────────────────────
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "gb2312")


def _try_csv(path: Path) -> dict:
    """CSV preflight: 多编码尝试 + 至少 1 行非空 + 列数 > 0.

    P2-2 修法: 必须有非空数据行 (≥1 行 + 任意 1 个非 NaN 字段).
    仅表头 (1 行 + N 列, 全部 NaN) → ValidationFailed (422).
    """
    last_err: Optional[Exception] = None
    for enc in _CSV_ENCODINGS:
        try:
            # header=0 显式声明, skiprows 跳过表头后看 data rows
            df = pd.read_csv(path, encoding=enc, header=0, nrows=50)
            if df.empty and len(df.columns) == 0:
                continue
            # P2-2: 真正数据行 (剔除全 NaN 行 + 全空白列)
            non_empty_rows = df.dropna(how="all")
            # 进一步: 至少 1 行 + 至少 1 个非空字段
            if len(non_empty_rows) == 0 or non_empty_rows.notna().sum().sum() == 0:
                raise ValidationFailed(
                    f"CSV 只有表头无数据行 (encoding={enc})"
                )
            return {
                "validator": "csv-utf8",
                "valid": True,
                "detected_format": f"encoding={enc};cols={len(df.columns)}",
                "row_sample_count": len(non_empty_rows),
                "warnings": [],
            }
        except ValidationFailed:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise ValidationFailed(f"CSV 无法读取（尝试编码 {_CSV_ENCODINGS} 全部失败: {last_err}）")


def _try_xlsx(path: Path) -> dict:
    """XLSX preflight: pandas/openpyxl 可打开 + 至少 1 sheet + 首个 sheet ≥ 1 非空行.

    P2-2 修法: 必须有非空数据行. 空 sheet / 仅空白行 → ValidationFailed (422).
    """
    try:
        with pd.ExcelFile(path) as xl:
            sheets = xl.sheet_names
            if not sheets:
                raise ValidationFailed("XLSX 不含任何 sheet")
            df = pd.read_excel(xl, sheet_name=sheets[0], nrows=50)
            non_empty_rows = df.dropna(how="all")
            if len(non_empty_rows) == 0:
                raise ValidationFailed(
                    f"XLSX 首个 sheet 仅空白行无数据 (sheet={sheets[0]})"
                )
            return {
                "validator": "xlsx-pandas",
                "valid": True,
                "detected_format": f"sheets={sheets[:3]};first_sheet={sheets[0]};cols={len(df.columns)}",
                "row_sample_count": len(non_empty_rows),
                "warnings": [],
            }
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailed(f"XLSX 无法读取: {exc}") from exc


def _try_zip(path: Path, max_members: int = 100, max_total_uncompressed: int = 500 * 1024 * 1024,
             max_member_ratio: int = 100) -> dict:
    """ZIP preflight: status-refresh 专用.
    - 可打开
    - max member 100
    - 解压总大小 max 500MB
    - 单成员压缩比 max 100
    - 拒绝绝对路径 / .. / symlink / Windows 绝对路径 / UNC path (P2-6)
    - 至少 1 个 .csv
    - 不实际解压到正式目录
    """
    try:
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            if not infos:
                raise ValidationFailed("ZIP 不含任何成员")
            if len(infos) > max_members:
                raise ValidationFailed(f"ZIP 成员数 {len(infos)} 超过 {max_members}")
            total_uncompressed = 0
            csv_count = 0
            for info in infos:
                name = info.filename
                # P2-6: 拒绝 Windows 绝对路径 + UNC path
                # POSIX: /abs/..., ../xxx
                # Windows: C:/xxx, C:\\xxx, \\\\server\\share\\xxx
                if name.startswith("/") or name.startswith("\\"):
                    raise ValidationFailed(f"ZIP 成员路径非法 (绝对路径): {name!r}")
                # Windows drive letter: "C:" "D:" 等
                if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
                    raise ValidationFailed(f"ZIP 成员路径非法 (Windows drive): {name!r}")
                # UNC path: 形如 \\server\share (Windows) 或 //server/share (POSIX)
                if name.startswith("//"):
                    raise ValidationFailed(f"ZIP 成员路径非法 (UNC): {name!r}")
                # path traversal: .. 或 包含 .. 分段
                if ".." in Path(name).parts:
                    raise ValidationFailed(f"ZIP 成员路径非法 (path traversal): {name!r}")
                # POSIX / 混合路径分隔符 (跟 sources.py 1:1 stable 检查 \\)
                if "\\" in name:
                    raise ValidationFailed(f"ZIP 成员路径非法 (含反斜杠): {name!r}")
                # symlink 防御
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValidationFailed(f"ZIP 成员不能是 symlink: {name!r}")
                # 压缩比防御
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > max_member_ratio:
                        raise ValidationFailed(
                            f"ZIP 成员 {name!r} 压缩比 {ratio:.1f} 超过 {max_member_ratio}（疑似 zip bomb）"
                        )
                total_uncompressed += info.file_size
                if total_uncompressed > max_total_uncompressed:
                    raise ValidationFailed(
                        f"ZIP 解压总大小超过 {max_total_uncompressed // (1024 * 1024)} MB（疑似 zip bomb）"
                    )
                if name.lower().endswith(".csv"):
                    csv_count += 1
            if csv_count == 0:
                raise ValidationFailed("ZIP 内不含任何 .csv 文件")
            return {
                "validator": "zip-safe",
                "valid": True,
                "detected_format": f"members={len(infos)};csv_members={csv_count}",
                "row_sample_count": None,
                "warnings": [],
            }
    except ValidationFailed:
        raise
    except zipfile.BadZipFile as exc:
        raise ValidationFailed(f"ZIP 无法打开: {exc}") from exc


def _validate_spu_mapping(path: Path) -> dict:
    """spu-mapping 无 header CSV: 至少 11 列 + 第 1 列含数字 product_id.

    B3 修法: 跟 scripts/etl/sources.py::load_spu_mapping 1:1 stable:
    - header=None (SPU 文件是 headerless)
    - 编码顺序 gbk / gb2312 / utf-8
    - product_id 正则 `^\\d+\\.?\\d*$` (跟 sources.py:94 1:1 stable,
      兼容整数和小数 ID)
    - 至少 11 列
    - 至少 1 行数据 (空文件 → 422, 跟 P2-2 一致)
    """
    # P2-2: 空文件预检
    if path.stat().st_size == 0:
        raise ValidationFailed("spu-mapping 文件为空 (0 字节)")

    # 跟 sources.py 1:1 stable 编码顺序
    last_err: Optional[Exception] = None
    df = None
    for enc in ("gbk", "gb2312", "utf-8"):
        try:
            df = pd.read_csv(path, header=None, encoding=enc, nrows=20)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    if df is None:
        raise ValidationFailed(f"spu-mapping 无 header 读取失败: {last_err}")

    if len(df.columns) < 11:
        raise ValidationFailed(f"spu-mapping 列数 {len(df.columns)} < 11")
    # 至少 1 行数据
    if len(df) == 0 or df.dropna(how="all").empty:
        raise ValidationFailed("spu-mapping 无合法数据行")
    first_col = df.iloc[:, 0].astype(str)
    has_numeric = first_col.str.match(r"^\d+\.?\d*$", na=False).any()
    if not has_numeric:
        raise ValidationFailed(
            "spu-mapping 第 1 列未发现合法 product_id (要求数字或小数)"
        )
    return {
        "validator": "spu-mapping",
        "valid": True,
        "detected_format": f"encoding={enc};cols={len(df.columns)}",
        "row_sample_count": len(df.dropna(how="all")),
        "warnings": [],
    }


def _validate_taoke(path: Path) -> dict:
    """taoke 必须存在 "淘宝父订单编号" 列.

    P2-3 修法: 业务列校验复用 _try_csv 已检测成功的编码 (从 detected_format 解析),
    而不是硬编码 utf-8 重读. 合法 GBK taoke 文件能通过.
    """
    base = _try_csv_or_xlsx(path)
    # 从 base.detected_format 提取编码 (跟 _try_csv/_try_xlsx 写明一致)
    # 例如: "encoding=utf-8;cols=5" / "sheets=[...];first_sheet=Sheet1;cols=5"
    suffix = path.suffix.lower()
    enc: Optional[str] = None
    if suffix == ".csv":
        # 解析 "encoding=xxx;cols=N"
        dfmt = base.get("detected_format", "")
        for token in dfmt.split(";"):
            if token.startswith("encoding="):
                enc = token.split("=", 1)[1]
                break
    if suffix == ".csv" and enc:
        df = pd.read_csv(path, encoding=enc, nrows=1)
        cols = df.columns
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, nrows=1)
        cols = df.columns
    else:
        cols = []
    if not any("淘宝父订单编号" in str(c) for c in cols):
        raise ValidationFailed("taoke 文件缺少必需列 '淘宝父订单编号'")
    base["validator"] = "business-taoke"
    return base


def _validate_live(path: Path) -> dict:
    """live 必须存在 '父订单id' 或 '父订单ID' 列"""
    base = _try_csv_or_xlsx(path)
    cols = pd.read_csv(path, encoding="utf-8", nrows=1).columns if path.suffix.lower() == ".csv" else \
        pd.read_excel(path, nrows=1).columns
    if not any(str(c).strip() in ("父订单id", "父订单ID") for c in cols):
        raise ValidationFailed("live 文件缺少必需列 '父订单id' 或 '父订单ID'")
    base["validator"] = "business-live"
    return base


def _validate_visitor(path: Path) -> dict:
    """visitor 必须存在 '日期' 和 '访客数' 列"""
    df = pd.read_excel(path, nrows=1)
    cols = [str(c).strip() for c in df.columns]
    if "日期" not in cols:
        raise ValidationFailed("visitor 文件缺少必需列 '日期'")
    if "访客数" not in cols:
        raise ValidationFailed("visitor 文件缺少必需列 '访客数'")
    return {
        "validator": "business-visitor",
        "valid": True,
        "detected_format": f"cols={cols}",
        "row_sample_count": 1,
        "warnings": [],
    }


def _validate_taoke_product(path: Path) -> dict:
    """taoke-product 必须存在 '商品ID', '开始日期', '结束日期'"""
    base = _try_csv(path)
    df = pd.read_csv(path, encoding="utf-8", nrows=1)
    cols = [str(c).strip() for c in df.columns]
    for required in ("商品ID", "开始日期", "结束日期"):
        if required not in cols:
            raise ValidationFailed(f"taoke-product 缺少必需列 '{required}'")
    base["validator"] = "business-taoke-product"
    return base


def _validate_channel_rules(path: Path) -> dict:
    """channel-rules 复用 scripts/etl/sources.py::load_channel_rules 真实兼容规则.
    允许 2 列 (keyword+channel) 或 3 列 (keyword+channel+product_id). 不另造更严口径.

    Sprint 205+ P1-1 修法: 显式传 staged path 给 load_channel_rules,
    真实校验本次上传文件 (而非正式 CHANNEL_RULES_SOURCE). 任何异常
    fail-closed → ValidationFailed (422), 不允许退化宽松.

    P2-2 修法附加: 空内容 (只有 header 无 data row) 也走 fail-closed, 不允许
    0 条规则被当成"合法"上传.

    B5 修法附加:
    - loader 返回值归一化: (None, None) → ValidationFailed 422 (防止 TypeError on len)
    - loader 抛任何异常 → ValidationFailed 422 (fail-closed, 不泄露 traceback)
    """
    from scripts.etl.sources import load_channel_rules  # type: ignore
    # 先做基础 CSV 校验 (含 P2-2 空内容检查)
    _try_csv(path)
    # 显式传 staged path; None 表示用全局 (admin upload 路径下永远不传 None)
    try:
        keyword_rules, id_rules = load_channel_rules(channel_file=path)
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001
        # B5: loader 抛异常 (parse 错 / 数据格式异常 / 系统级错) → 422,
        # 防止 500 + traceback 泄露. 不修改 ETL loader 默认行为.
        raise ValidationFailed(
            f"channel-rules 解析失败: {type(exc).__name__}"
        ) from exc

    # B5: 归一化 None / 空 list (loader 在错误情况下可能返回 (None, None))
    if keyword_rules is None:
        keyword_rules = []
    if id_rules is None:
        id_rules = []
    if len(keyword_rules) == 0 and len(id_rules) == 0:
        raise ValidationFailed(
            "channel-rules 既无 keyword 规则也无商品 ID 规则 (空内容)"
        )
    return {
        "validator": "business-channel-rules",
        "valid": True,
        "detected_format": f"keyword_rules={len(keyword_rules)};id_rules={len(id_rules)}",
        "row_sample_count": None,
        "warnings": [],
    }


def _validate_campaign_schedule(path: Path) -> dict:
    """campaign-schedule 必需列 year / 活动名称 / 开始时间 / 结束时间"""
    base = _try_csv(path)
    df = pd.read_csv(path, encoding="utf-8", nrows=1)
    cols = [str(c).strip() for c in df.columns]
    for required in ("year", "活动名称", "开始时间", "结束时间"):
        if required not in cols:
            raise ValidationFailed(f"campaign-schedule 缺少必需列 '{required}'")
    base["validator"] = "business-campaign-schedule"
    return base


def _try_csv_or_xlsx(path: Path) -> dict:
    """根据扩展名分流 (业务校验统一入口)"""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _try_csv(path)
    if suffix in (".xlsx", ".xls"):
        return _try_xlsx(path)
    raise ValidationFailed(f"不支持的扩展名: {suffix}")


_VALIDATORS = {
    "xlsx": _try_xlsx,
    "csv": _try_csv,
    "zip-or-csv": lambda p: _try_zip(p) if p.suffix.lower() == ".zip" else _try_csv(p),
    "taoke": _validate_taoke,
    "live": _validate_live,
    "visitor": _validate_visitor,
    "spu-mapping": _validate_spu_mapping,
    "taoke-product": _validate_taoke_product,
    "channel-rules": _validate_channel_rules,
    "campaign-schedule": _validate_campaign_schedule,
}


def run_preflight(source: _SourceConfig, staged_path: Path) -> dict:
    """根据 source.validator_kind 调对应校验器. 校验失败抛 ValidationFailed (422)."""
    fn = _VALIDATORS.get(source.validator_kind)
    if fn is None:
        raise ValidationFailed(f"未知 validator_kind: {source.validator_kind}")
    return fn(staged_path)


# ─────────────────────────────────────────────────────────────
# 流式写入 staging
# ─────────────────────────────────────────────────────────────
def _generate_upload_id() -> str:
    return uuid.uuid4().hex


def _fsync_directory(path: Path) -> None:
    """fsync 目录. 抽成独立函数方便 B1 测试 monkeypatch 模拟失败."""
    dir_fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _stream_to_staging(
    file_obj,
    staging_root: Path,
    *,
    extension: str,
    max_bytes: int = MAX_UPLOAD_BYTES,
    chunk_size: int = CHUNK_SIZE,
) -> Tuple[Path, int, str]:
    """从可迭代 file_obj 流式写入 staging/{upload_id}/payload{ext}.

    行为 (B1 修法加固):
    - 创建 upload_id 临时子目录
    - 流式写 payload.part, 累计 SHA-256 + size
    - 超过 max_bytes 立即停止, 清整个 staging UUID 子目录, 抛 FileTooLarge
    - flush + os.fsync(file)
    - rename payload.part → payload{ext}
    - fsync staging 父目录 (抽成 _fsync_directory 便于测试)
    - 任何阶段失败 → _cleanup_staging_subdir (含已 rename 后的 final_path)

    Returns: (final_path, size_bytes, sha256_hex)
    """
    upload_id = _generate_upload_id()
    staging_subdir = staging_root / upload_id
    staging_subdir.mkdir(parents=True, exist_ok=True)
    part_path = staging_subdir / "payload.part"
    final_path = staging_subdir / f"payload{extension}"
    sha256 = hashlib.sha256()
    total = 0
    fd: Optional[int] = None
    try:
        fd = os.open(part_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            fd = None  # os.fdopen 接管 fd
            while True:
                chunk = file_obj.read(chunk_size) if hasattr(file_obj, "read") else b""
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    raise FileTooLarge(f"上传内容超过 {max_bytes // (1024 * 1024)} MB 限制")
                sha256.update(chunk)
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        # 关闭后再 rename
        os.replace(part_path, final_path)
        # fsync staging 父目录 (B1: 失败必须 cleanup 整个 staging 子目录)
        _fsync_directory(staging_subdir)
        return final_path, total, sha256.hexdigest()
    except Exception:
        # B1 修法: 任何阶段失败 → _cleanup_staging_subdir 删整个 staging UUID 子目录.
        # 不再 only-unlink part, 因为 rename 成功后 .part 已不存在, final_path 已存在.
        _cleanup_staging_subdir(staging_subdir)
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────
# Registry: fcntl.flock + 原子写 + .bak 恢复
# (跟 v5 prompt §"Registry" 1:1 stable)
# ─────────────────────────────────────────────────────────────
def _registry_paths(
    registry_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
    backup_path: Optional[Path] = None,
) -> Tuple[Path, Path, Path]:
    """解析 registry 路径 (test 可注入). 默认用 module-level constants."""
    return (
        registry_path or _DEFAULT_REGISTRY_PATH,
        lock_path or _DEFAULT_REGISTRY_LOCK,
        backup_path or _DEFAULT_REGISTRY_BACKUP,
    )


# B6 修法: 单一 _validate_registry_data 替代旧的浅校验 ("dict + uploads key").
# 校验 root 是 dict / uploads 是 list / 每个 entry 是 dict + 必需字段类型.
def _validate_registry_data(data: object) -> dict:
    """严格校验 registry 数据结构. 不合规抛 RegistryCorrupt (500) 让 caller 走 .bak.

    规则 (跟 B6 1:1 stable):
    - root 是 dict
    - "uploads" 存在且是 list
    - 每个 entry 是 dict
    - 必需字段 (按 sprint 1 schema):
        upload_id (str), business_type (str), original_filename (str),
        extension (str), staged_path (str), size_bytes (int),
        sha256 (str), uploaded_by (str), uploaded_at (str),
        status (str), validation (dict), future_post_actions (list),
        idempotency_key (str|None)
    - 未知扩展字段允许保留 (跟 L4.91 forward-compat 1:1 stable)
    """
    if not isinstance(data, dict):
        raise ValueError(f"root 不是 dict (实际 {type(data).__name__})")
    uploads = data.get("uploads")
    if not isinstance(uploads, list):
        raise ValueError(f"uploads 不是 list (实际 {type(uploads).__name__ if uploads is not None else 'None'})")
    required_str_fields = (
        "upload_id", "business_type", "original_filename", "extension",
        "staged_path", "sha256", "uploaded_by", "uploaded_at", "status",
    )
    for idx, entry in enumerate(uploads):
        if not isinstance(entry, dict):
            raise ValueError(f"uploads[{idx}] 不是 dict (实际 {type(entry).__name__})")
        for field_name in required_str_fields:
            v = entry.get(field_name)
            if not isinstance(v, str):
                raise ValueError(f"uploads[{idx}].{field_name} 不是 str (实际 {type(v).__name__ if v is not None else 'None'})")
        size_bytes = entry.get("size_bytes")
        if not isinstance(size_bytes, int):
            raise ValueError(f"uploads[{idx}].size_bytes 不是 int")
        validation = entry.get("validation")
        if not isinstance(validation, dict):
            raise ValueError(f"uploads[{idx}].validation 不是 dict")
        future = entry.get("future_post_actions")
        if not isinstance(future, list):
            raise ValueError(f"uploads[{idx}].future_post_actions 不是 list")
        # idempotency_key: 允许 str 或 None
        idem = entry.get("idempotency_key")
        if idem is not None and not isinstance(idem, str):
            raise ValueError(f"uploads[{idx}].idempotency_key 不是 str|None")
    return data


def _read_registry_only(registry_path: Path) -> Tuple[dict, Optional[str]]:
    """只读主 registry, 不尝试恢复. 用于 LOCK_SH 下的查询路径.

    Returns: (data, warning). warning 不为 None 表示主文件损坏, 由 caller 走恢复.
    """
    if not registry_path.exists():
        return {"schema_version": 1, "uploads": []}, None
    try:
        raw = registry_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        # B6: 严格结构校验替代旧浅校验
        try:
            _validate_registry_data(data)
            return data, None
        except ValueError as val_exc:
            return {"schema_version": 1, "uploads": []}, f"主 registry schema 异常: {val_exc}"
    except (json.JSONDecodeError, ValueError) as exc:
        return {"schema_version": 1, "uploads": []}, f"主 registry 损坏: {exc}"


def _recover_registry_to_main(
    registry_path: Path, backup_path: Path, *, lock_held: bool
) -> Tuple[dict, Optional[str]]:
    """P2-1: 恢复主 registry. 必须 lock_held=True (调用方持 LOCK_EX).

    防止多 reader 同时恢复写入主 registry. 如果 lock_held=False, 抛 PermissionError.

    B6 修法: 主 + .bak 都走 _validate_registry_data 严格校验. 不合规 raise
    RegistryCorrupt (500) → caller 决定后续.
    """
    if not lock_held:
        raise PermissionError("_recover_registry_to_main 必须在 LOCK_EX 下调用")

    # 主文件不存在 → 尝试 .bak, 或返空
    if not registry_path.exists():
        if backup_path.exists():
            try:
                bak_raw = backup_path.read_text(encoding="utf-8")
                bak_data = json.loads(bak_raw)
                _validate_registry_data(bak_data)
                logger.warning("[admin_upload] 主 registry 不存在, 从 .bak 恢复")
                _atomic_write_json(registry_path, bak_data, backup_path=None)
                return bak_data, "主 registry 不存在, 已从 .bak 恢复"
            except RegistryCorrupt:
                raise
            except Exception as bak_exc:
                logger.error("[admin_upload] .bak 不可用: %s", bak_exc)
                raise RegistryCorrupt(f".bak 不可用: {bak_exc}") from bak_exc
        return {"schema_version": 1, "uploads": []}, None

    try:
        raw = registry_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        _validate_registry_data(data)
        return data, None
    except (json.JSONDecodeError, ValueError) as exc:
        # 主 corrupt, 尝试 .bak
        if backup_path.exists():
            try:
                bak_raw = backup_path.read_text(encoding="utf-8")
                bak_data = json.loads(bak_raw)
                _validate_registry_data(bak_data)
                logger.warning("[admin_upload] 主 registry 损坏, 从 .bak 恢复: %s", exc)
                _atomic_write_json(registry_path, bak_data, backup_path=None)
                return bak_data, f"主 registry 损坏, 已从 .bak 恢复: {exc}"
            except RegistryCorrupt:
                raise
            except Exception as bak_exc:
                logger.error("[admin_upload] 主+备份 registry 都损坏: %s / %s", exc, bak_exc)
                raise RegistryCorrupt(
                    f"主 registry 损坏 ({exc}) 且备份 .bak 不可用 ({bak_exc})"
                ) from exc
        raise RegistryCorrupt(f"主 registry 损坏且无备份: {exc}") from exc


class AtomicWritePostReplaceError(Exception):
    """B2 修法 (Codex Stage 4 二审加固): target 文件已被 os.replace 成功替换,
    后续 fsync 失败时抛此异常. 携带 ``target`` (本层正在写的实际路径, 含 backup /
    main 区分) + ``cause`` (底层 OSError), 调用方根据 ``exc.target`` 决定是否
    保留 target + 关联资源 (committed=True) 或删除 (committed=False).
    """

    def __init__(self, target: Path, cause: Exception):
        self.target = Path(target)
        self.cause = cause
        super().__init__(
            f"target={self.target} 已替换成功但父目录 fsync 失败: {cause}"
        )


def _atomic_write_json(target: Path, data: dict, *, backup_path: Optional[Path] = None) -> None:
    """原子写 JSON: 临时文件 → fsync → os.replace → fsync 父目录.

    如果 backup_path 不为 None, 先把上一份 target 内容备份到 backup_path (同样原子写).

    B2 修法 (Codex Stage 4 二审加固):
    - replace 之前的异常 → 普通异常, 调用方可以重新尝试 (target 未变).
    - replace 之后的父目录 fsync 异常 → AtomicWritePostReplaceError(target, cause),
      调用方根据 ``exc.target`` 是否等于本次主 registry 决定 committed 状态:
      * 主 registry: target 已 replace, committed=True, 保留 payload + registry entry,
        相同 Idempotency-Key 重试可命中;
      * backup: target 已是旧主内容备份, 主 registry 尚未写入, committed=False,
        本次 payload 删除, 下次重试作为新上传处理.
    - 复用 ``_fsync_directory`` 跟 B1 staging 共用同一目录 fsync helper, 避免
      两份 open/fsync/close 逻辑漂移.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    # 备份上一份有效内容 (走 atomic write, 不传 backup_path 防递归)
    if backup_path is not None and target.exists():
        # B2 二审加固: 显式传 backup_path=None 防递归调用 _atomic_write_json
        # 同时捕获 backup 阶段异常 (旧行为是会传到 caller, 但 Codex 验证
        # backup 阶段的 AtomicWritePostReplaceError 应该归到 backup target,
        # 不能让主 upload() 误判为主 registry committed). 这里走 try/except:
        try:
            _atomic_write_json(backup_path, json.loads(target.read_text(encoding="utf-8")))
        except AtomicWritePostReplaceError as bak_exc:
            # backup 阶段的 fsync 失败 → 重新 raise 携带 backup target
            raise bak_exc  # bak_exc.target 已经是 backup_path
    # 临时文件: 进程级唯一名 (防并发冲突, 跟 v5 prompt §"原子写" 1:1 stable)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".upload_registry.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None  # 托管
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # replace 成功 — target 已可见. 此后的失败必须用 sentinel.
        os.replace(tmp_path, target)
        try:
            # B2 二审加固: 复用 _fsync_directory 跟 B1 staging 共享目录 fsync helper,
            # 失败时携带 target + cause 抛 AtomicWritePostReplaceError.
            _fsync_directory(target.parent)
        except Exception as post_replace_exc:
            # B2: replace 已成功, target 已被 commit. 调用方绝对不能删除 target.
            raise AtomicWritePostReplaceError(target, post_replace_exc) from post_replace_exc
    except AtomicWritePostReplaceError:
        # B2: 不要清理 tmp (replace 已挪走) 也不要清理 target (已 commit)
        raise
    except Exception:
        # replace 之前失败 (写 tmp / fsync tmp / os.replace) → 清 tmp
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


class _RegistryLock:
    """fcntl.flock 跨进程 / 跨 worker 锁 (跟 v5 prompt §"Registry 锁要求" 1:1 stable).

    不使用 asyncio.Lock (跟 L4.36 永久规则化沿用: 跨 worker 必 fcntl.flock).
    """

    def __init__(self, lock_path: Path, *, exclusive: bool = True):
        self.lock_path = lock_path
        self.exclusive = exclusive
        self._fd: Optional[int] = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH)
        return self

    def __exit__(self, *exc):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


def _find_active_duplicate(
    registry_data: dict,
    *,
    business_type: str,
    sha256: str,
) -> Optional[dict]:
    """找 business_type + sha256 匹配且 status 活跃的记录."""
    for entry in registry_data.get("uploads", []):
        if (
            entry.get("business_type") == business_type
            and entry.get("sha256") == sha256
            and entry.get("status") in ("staged", "queued", "promoted", "active")
        ):
            return entry
    return None


def _find_idempotency_match(
    registry_data: dict,
    *,
    idempotency_key: str,
    business_type: str,
    sha256: str,
) -> Optional[dict]:
    """找 idempotency_key + business_type + sha256 全部匹配的记录 (不管 status)."""
    for entry in registry_data.get("uploads", []):
        if (
            entry.get("idempotency_key") == idempotency_key
            and entry.get("business_type") == business_type
            and entry.get("sha256") == sha256
        ):
            return entry
    return None


def _entry_to_result(entry: dict) -> UploadResult:
    """registry entry → UploadResult."""
    validation = entry.get("validation") or {}
    uploaded_at = entry.get("uploaded_at")
    if isinstance(uploaded_at, str):
        uploaded_at_dt = datetime.fromisoformat(uploaded_at)
    else:
        uploaded_at_dt = datetime.now(timezone.utc)
    return UploadResult(
        upload_id=entry["upload_id"],
        business_type=entry["business_type"],
        original_filename=entry["original_filename"],
        extension=entry["extension"],
        size_bytes=entry["size_bytes"],
        sha256=entry["sha256"],
        uploaded_by=entry["uploaded_by"],
        uploaded_at=uploaded_at_dt,
        status=entry.get("status", "staged"),
        validation=validation,
        future_post_actions=list(entry.get("future_post_actions", [])),
    )


def upload(
    *,
    business_type: str,
    file_obj,
    original_filename: str,
    uploaded_by: str,
    idempotency_key: Optional[str] = None,
    staging_root: Optional[Path] = None,
    registry_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
    backup_path: Optional[Path] = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> UploadResult:
    """主入口: 流式写入 staging + preflight + 原子写 registry + 幂等/dedup.

    异常分类:
    - FilenameInvalid / ExtensionInvalid (400/422)
    - UnknownBusinessType (400)
    - FileTooLarge (413)
    - EmptyFile (400)
    - ValidationFailed (422)
    - DuplicateUpload (409)
    - IdempotencyConflict (409)
    - RegistryCorrupt (500)
    """
    staging_root = staging_root or _DEFAULT_STAGING_ROOT
    registry_path, lock_path, backup_path = _registry_paths(registry_path, lock_path, backup_path)

    # L1 修法: defensive Idempotency-Key 校验 (双层防御 router 也设, 这里兜底).
    # router FastAPI Header 会先 reject, 但 service 仍需独立校验
    # (防止 admin_upload.upload() 被其他内部调用绕过 router 层).
    if idempotency_key is not None:
        if not isinstance(idempotency_key, str):
            raise IdempotencyKeyInvalid("Idempotency-Key 必须是字符串")
        if len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise IdempotencyKeyInvalid(
                f"Idempotency-Key 长度 {len(idempotency_key)} 超过 {IDEMPOTENCY_KEY_MAX_LENGTH}"
            )
        if not idempotency_key.strip():
            raise IdempotencyKeyInvalid("Idempotency-Key 不能为空或纯空白")

    # 1. 校验 business_type
    src = get_source(business_type)
    if src is None:
        raise UnknownBusinessType(f"未知业务类型: {business_type}")

    # 2. 校验文件名
    ok, msg = validate_filename(original_filename)
    if not ok:
        raise FilenameInvalid(msg)

    # 3. 校验扩展名
    ok, msg = validate_extension(original_filename, src.allowed_extensions)
    if not ok:
        raise ExtensionInvalid(msg)

    # 4. 流式写 staging
    extension = Path(original_filename).suffix.lower()
    final_path, size_bytes, sha256 = _stream_to_staging(
        file_obj,
        staging_root,
        extension=extension,
        max_bytes=max_bytes,
    )
    staging_subdir = final_path.parent  # = staging/{upload_id}/
    committed = False  # registry 成功接管后才置 True, cleanup 跳过
    try:
        if size_bytes == 0:
            raise EmptyFile("文件为空 (0 字节)")

        # 5. preflight
        validation = run_preflight(src, final_path)

        # 6. registry 操作 (全程持 flock)
        with _RegistryLock(lock_path, exclusive=True):
            data, warning = _recover_registry_to_main(registry_path, backup_path, lock_held=True)
            if warning:
                logger.warning("[admin_upload] %s", warning)

            # 6a. 幂等检查
            if idempotency_key:
                hit = _find_idempotency_match(
                    data,
                    idempotency_key=idempotency_key,
                    business_type=business_type,
                    sha256=sha256,
                )
                if hit:
                    # P1-2: 幂等命中删本次新写入的 payload + 空 UUID 子目录,
                    # 不得删除旧 registry 记录对应 staged 文件
                    result = _entry_to_result(hit)
                    result.idempotency_hit = True
                    # raise 之前标记 not committed → outer except 清理本次 staging
                    raise _IdempotencyHit(result)
                # 幂等 key 已存在但 business_type 或 sha256 不一致 → 409
                for entry in data.get("uploads", []):
                    if entry.get("idempotency_key") == idempotency_key:
                        raise IdempotencyConflict(
                            "Idempotency-Key 已绑定不同请求 (business_type 或 sha256 不一致)"
                        )

            # 6b. 重复检查 (business_type + sha256)
            dup = _find_active_duplicate(data, business_type=business_type, sha256=sha256)
            if dup is not None:
                raise DuplicateUpload(
                    f"同一业务类型已存在相同 hash 的 staged 记录 ({dup['upload_id']})"
                )

            # 6c. 写新 entry
            upload_id = staging_subdir.name  # = upload_id
            now = datetime.now(timezone.utc)
            new_entry = {
                "upload_id": upload_id,
                "business_type": business_type,
                "original_filename": original_filename,
                "extension": extension,
                "staged_path": str(_project_relative(final_path)),
                "size_bytes": size_bytes,
                "sha256": sha256,
                "uploaded_by": uploaded_by,
                "uploaded_at": now.isoformat(),
                "status": "staged",
                "validation": validation,
                "idempotency_key": idempotency_key,
                "future_post_actions": list(src.future_post_actions),
            }
            data["uploads"].append(new_entry)
            # Codex Stage 4 二审加固: 写盘前先校验 registry 结构, 阻止内部构造
            # 错误的数据落盘 (即使 _atomic_write_json 写成功, 下次读也会触发
            # RegistryCorrupt → 走 .bak recovery 误删刚写的记录). 跟 L4.91 forward-compat
            # 1:1 stable 永久规则化沿用 (未知扩展字段允许保留).
            _validate_registry_data(data)
            try:
                _atomic_write_json(registry_path, data, backup_path=backup_path)
            except AtomicWritePostReplaceError as exc:
                # B2 修法 (Codex Stage 4 二审加固): 只有当异常来自主 registry 才
                # 标记 committed=True. 如果异常来自 backup 阶段, 主 registry 尚未
                # 写入, 必须让 outer except 清掉本次 payload.
                if exc.target.resolve() == registry_path.resolve():
                    # 主 registry 已 replace 成功, 不能删 payload, 相同 Idempotency-Key
                    # 重试能命中这条记录, 不会产生第二份.
                    committed = True
                # 重新 raise 让上层返 500; 上层根据 committed 决定是否 cleanup
                raise
            # registry 成功接管本次 UUID → 后续 cleanup 不删 staging
            committed = True
            return UploadResult(
                upload_id=upload_id,
                business_type=business_type,
                original_filename=original_filename,
                extension=extension,
                size_bytes=size_bytes,
                sha256=sha256,
                uploaded_by=uploaded_by,
                uploaded_at=now,
                status="staged",
                validation=validation,
                future_post_actions=list(src.future_post_actions),
            )
    except _IdempotencyHit as hit_exc:
        # 幂等命中: 删本次新写入的 payload + 空 UUID 目录
        _cleanup_staging_subdir(staging_subdir)
        return hit_exc.result
    except Exception:
        # 任何其他失败 → 统一清本次 staging (registry 未接管)
        if not committed:
            _cleanup_staging_subdir(staging_subdir)
        raise


class _IdempotencyHit(Exception):
    """内部 sentinel: 6a 命中 → 调 _cleanup_staging_subdir → 返老记录."""

    def __init__(self, result: UploadResult):
        super().__init__("idempotency hit")
        self.result = result


def _cleanup_staging_subdir(subdir: Path) -> None:
    """P1-2 统一 cleanup: 删本次 staging 子目录下所有文件 + 子目录本身 (仅当空).

    行为:
    - 删除 payload.part + payload.{ext} 等
    - 删空子目录 (含隐藏文件如 .DS_Store 等)
    - 如果子目录非空 (sprint 2 promotion 时会变非空), 保留 (不强行 rmtree)
    - 任何 OSError 静默 (跟 L4.50 fail-open 1:1 stable 永久规则化沿用)
    """
    if not subdir.exists():
        return
    try:
        for child in subdir.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    # 仅删真正空的子目录, 防止误删
                    try:
                        child.rmdir()
                    except OSError:
                        pass
            except OSError:
                pass
        try:
            subdir.rmdir()
        except OSError:
            # 非空 (sprint 2 promotion 后续操作可能写入), 保留
            pass
    except OSError:
        pass


def list_uploads(
    *,
    business_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    registry_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
    backup_path: Optional[Path] = None,
) -> Tuple[List[UploadResult], int]:
    """查询 registry, 按 uploaded_at 降序.

    P2-1 修法: LOCK_SH 下只读+检测; 若主文件损坏, 释放共享锁 → 获取 LOCK_EX →
    重新检查 (可能其他进程已恢复) → 走 _recover_registry_to_main. 防止多 reader
    同时恢复写入主 registry.
    """
    registry_path, lock_path, backup_path = _registry_paths(registry_path, lock_path, backup_path)
    # 1. LOCK_SH: 只读 + 检测损坏
    with _RegistryLock(lock_path, exclusive=False):
        data, warning = _read_registry_only(registry_path)
        if warning is None:
            # 主文件健康 → 直接返 (含 total)
            return _paginate_uploads(data, business_type, status, limit, offset)
        # 主损坏, 出 LOCK_SH 后再处理

    # 2. 主损坏 → 升 LOCK_EX 走恢复 (防多 reader 同时写)
    with _RegistryLock(lock_path, exclusive=True):
        data, _ = _recover_registry_to_main(
            registry_path, backup_path, lock_held=True
        )

    return _paginate_uploads(data, business_type, status, limit, offset)


def _paginate_uploads(
    data: dict,
    business_type: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[UploadResult], int]:
    items = data.get("uploads", [])
    if business_type:
        items = [e for e in items if e.get("business_type") == business_type]
    if status:
        items = [e for e in items if e.get("status") == status]
    items = sorted(items, key=lambda e: str(e.get("uploaded_at", "")), reverse=True)
    total = len(items)
    page = items[offset: offset + limit]
    return [_entry_to_result(e) for e in page], total


def _project_relative(absolute_path: Path) -> Path:
    """把绝对路径转成项目根目录相对路径 (registry staged_path 用)."""
    try:
        return absolute_path.relative_to(Path(__file__).resolve().parents[2])
    except ValueError:
        # 不在项目根下 (test 注入 tmp_path), 原样存
        return absolute_path


# ─────────────────────────────────────────────────────────────
# 客户端可见配置 (GET /upload-config)
# ─────────────────────────────────────────────────────────────
def public_sources_for_response() -> List[dict]:
    """把 10 种 _SourceConfig 转成客户端可见 dict (禁暴露 target_path/staged_path)."""
    out = []
    for src in get_sources().values():
        out.append({
            "business_type": src.business_type,
            "display_name": src.display_name,
            "allowed_extensions": list(src.allowed_extensions),
            "mode": src.mode,
            "max_size_bytes": MAX_UPLOAD_BYTES,
            "future_post_actions": list(src.future_post_actions),
            "replacement_warning": src.replacement_warning,
        })
    return out