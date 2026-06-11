"""
ETL 跑完通知（W6）— 复用 scraper 6 道门禁 lark-cli 通道。

设计：docs/design/etl-phase4-architecture.md §W6
- 复用 scraper/core/sanity_check.py::_send_lark_alert（不引入新依赖）
- graceful degrade：未配置 NOTIFY_OPEN_IDS / lark-cli 失败均不阻塞 ETL
- 区分 status: 'success' / 'failed'（避免推送"成功"假象）
"""
import os
from datetime import datetime
from typing import Tuple

# 跨子项目 import scraper 6 道门禁通道（monorepo 内 PYTHONPATH="$(pwd)" 包含项目根）
# B1 治根 (Sprint 16.5+1): 改走 ETL 自己的 lark 通道 (scripts/etl/common/lark.py)
try:
    from scripts.etl.common.lark import _send_lark_alert
except ImportError:  # 单测 / 独立运行兼容
    _send_lark_alert = None  # type: ignore[assignment]


def notify_etl_complete(
    stats: dict,
    status: str = "success",
) -> Tuple[bool, str]:
    """ETL 跑完通知（lark-cli 推老板 + 运营，9 点上班就能看到数据）。

    Args:
        stats: 跑批摘要 dict，必填键：
            - orders_count: orders 表行数
            - user_rfm_count: user_rfm 表行数
            - wall_min: 跑批 wall time（分钟）
          可选键：
            - mode: 'auto' / 'full' / 'inc'
            - run_mode: 'full' / 'incremental'
            - gates_overall: 6 道门禁结果（'pass' / 'fail' / 'skipped'）
        status: 'success' / 'failed'（控制消息 emoji 和文案）

    Returns:
        (success: bool, reason: str)
        - success=True 表示所有 oid 推送成功
        - reason 详细说明（never raises）

    CLAUDE.md 合规：
        ① 复用现有 lark-cli 通道（不引入新依赖）
        ② graceful degrade：未配置 NOTIFY_OPEN_IDS / lark-cli 不存在不报错
        ③ ETL 失败时推"❌ ETL 失败"而非 skip（避免静默成功假象）
    """
    oids_env = os.environ.get("NOTIFY_OPEN_IDS", "")
    oids = [o.strip() for o in oids_env.split(",") if o.strip()]
    if not oids:
        return False, "未配置 NOTIFY_OPEN_IDS，跳过通知（不报错）"

    if status == "success":
        emoji = "✅"
        title = "ETL 跑完"
    else:
        emoji = "❌"
        title = "ETL 失败"

    msg = (
        f"{emoji} {title} {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"orders: {stats.get('orders_count', '?')}\n"
        f"user_rfm: {stats.get('user_rfm_count', '?')}\n"
        f"wall time: {stats.get('wall_min', '?')}min\n"
        f"mode: {stats.get('mode', '?')} / {stats.get('run_mode', '?')}\n"
        f"6 道门禁: {stats.get('gates_overall', '?')}"
    )

    if _send_lark_alert is None:
        return False, "scraper._send_lark_alert 不可用（PYTHONPATH 未包含项目根）"

    # FIX-S6: 并行推送（ThreadPoolExecutor），替代 9 oids 串行最坏阻塞 ETL 退出 45s
    # 每个 _send_lark_alert 内部 timeout=5s, 9 oids 并行 = ~5s worst case
    from concurrent.futures import ThreadPoolExecutor
    # max_workers 限制在 [1, min(len(oids), 5)] 避免过多并发
    max_workers = max(1, min(len(oids), 5))
    # 按 oids 顺序提交, 按 oids 顺序收集结果 (保留入参顺序, 测试稳定)
    oid_results: list[tuple[str, bool, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_send_lark_alert, msg, open_id=oid) for oid in oids]
        for oid, future in zip(oids, futures):
            try:
                # WO-4 P2-#1: 加 10s timeout (scraper 内部 5s, 外层放宽 2x)
                # 防止 scraper SDK 升级后 timeout 失效 / subprocess 卡 stdout 拖累 ETL 退出
                sent, reason = future.result(timeout=10)
            except Exception as e:
                # 未来不应抛 (graceful _send_lark_alert 设计), 但兜底
                sent, reason = False, f"推送异常: {type(e).__name__}: {str(e)[:100]}"
            oid_results.append((oid, sent, reason))

    results = [r[1] for r in oid_results]
    reasons = [f"{r[0][:8]}…={r[1]}" for r in oid_results]
    success = all(results)
    summary = f"{sum(results)}/{len(oids)} 推送成功 [{'; '.join(reasons)}]"
    return success, summary
