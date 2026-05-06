"""
老客健康分析仪表盘 - 配置中心

V1: 只读（后端硬编码）
V2: 支持前端修改（持久化到JSON文件）
V3: 支持渠道级独立配置 + 基于去年同期自动初始化
V4: 配置历史/回滚 + 审计日志 + 多环境默认值
"""

import json
import os
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
import copy
from typing import Dict, List, Any, Optional

from backend.config import PROJECT_ROOT

# 配置文件路径（项目根目录下的 config/health_config.json）
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "health_config.json"

# 备份目录
BACKUP_DIR = CONFIG_DIR / "health_config_backups"

# 审计日志路径（与 BACKUP_DIR 同级，不嵌套在 backups 下）
AUDIT_LOG_PATH = CONFIG_DIR / "health_config_audit.log"


# ── 健康评分权重 ──
HEALTH_SCORE_WEIGHTS = {
    "all_store_repurchase_rate": 0.20,
    "same_product_repurchase_rate": 0.30,
    "old_customer_gsv_ratio": 0.10,
    "old_customer_aus": 0.30,
    "recent_7d_repurchase_users": 0.10,
}

# ── 健康评分目标阈值（满分100对应值） ──
# 基于2024-2025历史数据P75分布优化（Phase 3）
HEALTH_SCORE_TARGETS = {
    "all_store_repurchase_rate": 0.21,  # P75=21.1%
    "same_product_repurchase_rate": 0.10,  # 本品复购率约为全店一半
    "old_customer_gsv_ratio": 0.38,  # P75=38.4%
    "old_customer_aus": 100.0,  # P75=¥101
    "recent_7d_repurchase_users": 300,  # 滑动窗口中位数
}

# ── 告警阈值 ──
# 基于2024-2025历史数据P25分布（低于P25才告警）
ALERT_THRESHOLDS = {
    # 复购率
    "all_store_repurchase_rate_low": 0.10,  # <10% 告警（约P25）
    "same_product_repurchase_rate_drop": 0.10,  # 同比下跌>10pp 告警
    # 老客占比
    "old_customer_gsv_ratio_low": 0.25,  # <25% 告警（约P25）
    # AUS
    "old_customer_aus_low": 50.0,  # <¥50 告警（约P25）
}

# ── 健康等级边界 ──
HEALTH_LEVEL_BOUNDS = {
    "healthy": 70,  # >=70 健康
    "warning": 50,  # >=50 关注
    # <50 预警
}

# ── 价值分层阈值（基于历史数据分布） ──
VALUE_TIER_THRESHOLDS = {
    "lookback_days": 365,
    "top_percentile": 0.20,  # S: 前20%
    "high_percentile": 0.50,  # A: 前50%（不含S）
    "medium_percentile": 0.80,  # B: 前80%（不含S/A）
    # C: 其余
}

# ── 频次分层阈值 ──
FREQUENCY_TIER_THRESHOLDS = {
    "high": 5,  # >=5单
    "medium": 2,  # >=2单
    # low: 其余
}

# ── 大促配置 ──
PROMOTION_PERIODS: Dict[int, List[Dict[str, Any]]] = {
    2025: [
        {"name": "38节日", "start_date": "03-01", "end_date": "03-10"},
        {"name": "618节日", "start_date": "05-20", "end_date": "06-20"},
        {"name": "双11", "start_date": "10-20", "end_date": "11-11"},
    ],
    2026: [
        {"name": "38节日", "start_date": "03-01", "end_date": "03-10"},
        {"name": "618节日", "start_date": "05-20", "end_date": "06-20"},
        {"name": "双11", "start_date": "10-20", "end_date": "11-11"},
    ],
}

# ── 多环境默认值预设 ──
# aggressive: 激进目标（高要求）
# conservative: 保守目标（低要求，适合大促/淡季）
ENV_PRESETS: Dict[str, Dict[str, Any]] = {
    "aggressive": {
        "weights": {
            "all_store_repurchase_rate": 0.20,
            "same_product_repurchase_rate": 0.30,
            "old_customer_gsv_ratio": 0.10,
            "old_customer_aus": 0.30,
            "recent_7d_repurchase_users": 0.10,
        },
        "targets": {
            "all_store_repurchase_rate": 0.25,  # 高于默认
            "same_product_repurchase_rate": 0.12,
            "old_customer_gsv_ratio": 0.42,
            "old_customer_aus": 120.0,
            "recent_7d_repurchase_users": 350,
        },
        "alert_thresholds": {
            "all_store_repurchase_rate_low": 0.12,
            "same_product_repurchase_rate_drop": 0.10,
            "old_customer_gsv_ratio_low": 0.28,
            "old_customer_aus_low": 60.0,
        },
        "health_level_bounds": {
            "healthy": 75,
            "warning": 55,
        },
    },
    "conservative": {
        "weights": {
            "all_store_repurchase_rate": 0.20,
            "same_product_repurchase_rate": 0.30,
            "old_customer_gsv_ratio": 0.10,
            "old_customer_aus": 0.30,
            "recent_7d_repurchase_users": 0.10,
        },
        "targets": {
            "all_store_repurchase_rate": 0.18,  # 低于默认
            "same_product_repurchase_rate": 0.08,
            "old_customer_gsv_ratio": 0.35,
            "old_customer_aus": 90.0,
            "recent_7d_repurchase_users": 250,
        },
        "alert_thresholds": {
            "all_store_repurchase_rate_low": 0.08,
            "same_product_repurchase_rate_drop": 0.10,
            "old_customer_gsv_ratio_low": 0.22,
            "old_customer_aus_low": 45.0,
        },
        "health_level_bounds": {
            "healthy": 65,
            "warning": 45,
        },
    },
}


def _load_config() -> Dict[str, Any]:
    """从文件加载配置，不存在则返回空字典"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_config(config: Dict[str, Any]) -> None:
    """保存配置到文件"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _get_env_preset() -> Optional[str]:
    """读取环境变量获取当前环境预设名称"""
    return os.environ.get("HEALTH_ENV", None)


def get_health_config() -> Dict[str, Any]:
    """获取健康分析完整配置（V4支持多环境默认值）"""
    env = _get_env_preset()
    # 如果指定了环境预设，使用预设作为基础默认值
    if env and env in ENV_PRESETS:
        preset = ENV_PRESETS[env]
        base = {
            "weights": copy.deepcopy(preset.get("weights", HEALTH_SCORE_WEIGHTS)),
            "targets": copy.deepcopy(preset.get("targets", HEALTH_SCORE_TARGETS)),
            "alert_thresholds": copy.deepcopy(preset.get("alert_thresholds", ALERT_THRESHOLDS)),
            "health_level_bounds": copy.deepcopy(preset.get("health_level_bounds", HEALTH_LEVEL_BOUNDS)),
            "value_tier": copy.deepcopy(VALUE_TIER_THRESHOLDS),
            "frequency_tier": copy.deepcopy(FREQUENCY_TIER_THRESHOLDS),
            "promotions": copy.deepcopy(PROMOTION_PERIODS),
            "channel_overrides": {},
            "env_preset": env,
        }
    else:
        # 基础默认值
        base = {
            "weights": copy.deepcopy(HEALTH_SCORE_WEIGHTS),
            "targets": copy.deepcopy(HEALTH_SCORE_TARGETS),
            "alert_thresholds": copy.deepcopy(ALERT_THRESHOLDS),
            "health_level_bounds": copy.deepcopy(HEALTH_LEVEL_BOUNDS),
            "value_tier": copy.deepcopy(VALUE_TIER_THRESHOLDS),
            "frequency_tier": copy.deepcopy(FREQUENCY_TIER_THRESHOLDS),
            "promotions": copy.deepcopy(PROMOTION_PERIODS),
            "channel_overrides": {},
            "env_preset": None,
        }
    # 合并用户自定义配置（覆盖默认值）
    user_config = _load_config()
    for key in base:
        if key in user_config:
            if isinstance(base[key], dict) and isinstance(user_config[key], dict):
                base[key].update(user_config[key])
            else:
                base[key] = user_config[key]
    return base


# ── 配置历史（备份/回滚）──

def _backup_config(action: str) -> str:
    """保存当前配置备份，返回备份ID"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{backup_id}_{action}.json"
    current = _load_config()
    backup_data = {
        "backup_id": backup_id,
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "config": current,
    }
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    return backup_id


def list_config_history(limit: int = 20) -> List[Dict[str, Any]]:
    """列出配置历史备份（按时间倒序）"""
    if not BACKUP_DIR.exists():
        return []
    backups = []
    for f in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            backups.append({
                "backup_id": data.get("backup_id", f.stem),
                "action": data.get("action", "unknown"),
                "timestamp": data.get("timestamp", ""),
                "file_name": f.name,
            })
        except (json.JSONDecodeError, IOError):
            continue
        if len(backups) >= limit:
            break
    return backups


def restore_config(backup_id: str) -> Dict[str, Any]:
    """从备份恢复配置"""
    backup_path = BACKUP_DIR / f"{backup_id}_update.json"
    if not backup_path.exists():
        backup_path = BACKUP_DIR / f"{backup_id}_reset.json"
    if not backup_path.exists():
        # 尝试模糊匹配
        for f in BACKUP_DIR.glob(f"{backup_id}*.json"):
            backup_path = f
            break
    if not backup_path.exists():
        raise FileNotFoundError(f"备份不存在: {backup_id}")

    with open(backup_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    restored = data.get("config", {})
    _save_config(restored)
    _log_audit("restore", {"backup_id": backup_id, "action": data.get("action", "")})
    return get_health_config()


# ── 审计日志 ──

MAX_AUDIT_LOG_SIZE = 5 * 1024 * 1024  # 5MB 轮转阈值

def _rotate_audit_log_if_needed() -> None:
    """单文件超过阈值时轮转：health_config_audit.log → .1 → .2"""
    if not AUDIT_LOG_PATH.exists():
        return
    if AUDIT_LOG_PATH.stat().st_size < MAX_AUDIT_LOG_SIZE:
        return
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for i in range(2, 0, -1):
        src = AUDIT_LOG_PATH.parent / f"health_config_audit.{i}.log"
        dst = AUDIT_LOG_PATH.parent / f"health_config_audit.{i + 1}.log"
        if src.exists():
            src.rename(dst)
    AUDIT_LOG_PATH.rename(AUDIT_LOG_PATH.parent / "health_config_audit.1.log")


def _log_audit(action: str, details: Dict[str, Any]) -> None:
    """记录审计日志（自动轮转 + HMAC 签名防篡改）"""
    _rotate_audit_log_if_needed()
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
    }
    # P2 fix: 添加 HMAC-SHA256 签名，防止审计日志被篡改
    secret = os.environ.get("AUDIT_LOG_SECRET", "")
    if secret:
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        entry["signature"] = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    with open(AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_audit_log(limit: int = 50) -> List[Dict[str, Any]]:
    """获取审计日志（按时间倒序）"""
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(entries[-limit:]))


# ── 配置更新/重置（带备份和审计）──

def _clear_health_cache() -> None:
    """清除健康评分缓存，确保配置变更后重新计算"""
    from backend.config import DATA_DIR
    cache_dir = DATA_DIR / "cache" / "health_overview"
    if cache_dir.exists():
        for f in cache_dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass


def update_health_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """更新配置（增量更新，只覆盖提供的字段）"""
    _backup_config("update")
    current = _load_config()
    # 记录变更摘要
    changed_keys = []
    for key, value in updates.items():
        if key in current and current[key] != value:
            changed_keys.append(key)
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    _save_config(current)
    _clear_health_cache()  # 清除缓存，确保新配置生效
    _log_audit("update", {"changed_keys": changed_keys, "keys": list(updates.keys())})
    return get_health_config()


def reset_health_config() -> Dict[str, Any]:
    """重置为默认配置"""
    _backup_config("reset")
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
    _clear_health_cache()  # 清除缓存，确保新配置生效
    _log_audit("reset", {"previous_config_exists": True})
    return get_health_config()
