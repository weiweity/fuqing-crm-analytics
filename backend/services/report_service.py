"""
Sample CRM 客户分析系统 - 报告汇总服务
Week 4 报告汇总（整合所有服务的数据）
"""

from typing import Dict, Any

from backend.services.metrics_service import get_overview_metrics, get_daily_trend
from backend.services.flow_service import get_flow_matrix
from backend.services.geo_service import get_geo_distribution, get_geo_segment_matrix
from backend.services.category_service import get_category_distribution, get_category_segment_matrix
from backend.semantic.time import normalize_date as _normalize_date


def get_report_summary(
    start_date: str,
    end_date: str,
    lookback_days: int = 90
) -> Dict[str, Any]:
    """
    获取报告汇总（整合所有数据）

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        lookback_days: 回溯天数

    Returns:
        {
            "date_range": {"start": str, "end": str},
            "overview": {...},           # 核心指标
            "segments": {...},           # 象限分布
            "geo": {...},                # 地域分布
            "category": {...},           # 品类分布
            "summary": {...}             # 摘要洞察
        }
    """
    start_str = _normalize_date(start_date)
    end_str = _normalize_date(end_date)

    # 1. 核心指标
    overview = get_overview_metrics(start_str, end_str)

    # 2. 每日趋势
    try:
        daily_trend = get_daily_trend(start_str, end_str)
    except Exception:
        daily_trend = {"dates": [], "amounts": [], "orders": [], "users": []}

    # 3. 象限分布
    try:
        flow_data = get_flow_matrix(start_str, end_str, lookback_days=lookback_days)
        # 计算各象限用户数
        segment_counts = {i: 0 for i in range(1, 10)}
        for record in flow_data.get('flow_matrix', []):
            from_seg = record.get('from', 0)
            to_seg = record.get('to', 0)
            count = record.get('count', 0)
            if 1 <= from_seg <= 9:
                segment_counts[from_seg] += count
            if 1 <= to_seg <= 9:
                segment_counts[to_seg] += count

        segments = {
            "distribution": [
                {
                    "segment_id": seg_id,
                    "name": flow_data['segments'][seg_id - 1]['name'],
                    "color": flow_data['segments'][seg_id - 1]['color'],
                    "user_count": segment_counts[seg_id]
                }
                for seg_id in range(1, 10)
            ],
            "flow_matrix": flow_data.get('flow_matrix', []),
            "summary": flow_data.get('summary', {})
        }
    except Exception:
        segments = {"distribution": [], "flow_matrix": [], "summary": {}}

    # 4. 地域分布
    try:
        geo_data = get_geo_distribution(end_str, lookback_days=lookback_days, level="省份", top_n=20)
        geo_matrix = get_geo_segment_matrix(end_str, lookback_days=lookback_days, top_n=5)
        geo = {
            "distribution": geo_data.get('distribution', []),
            "total_users": geo_data.get('total_users', 0),
            "total_gmv": geo_data.get('total_gmv', 0),
            "segment_matrix": geo_matrix.get('matrix', {})
        }
    except Exception:
        geo = {"distribution": [], "total_users": 0, "total_gmv": 0, "segment_matrix": {}}

    # 5. 品类分布
    try:
        category_data = get_category_distribution(end_str, lookback_days=lookback_days, level="category")
        category_matrix = get_category_segment_matrix(end_str, lookback_days=lookback_days, level="type", top_n=5)
        category = {
            "distribution": category_data.get('distribution', []),
            "total_users": category_data.get('total_users', 0),
            "total_gmv": category_data.get('total_gmv', 0),
            "segment_matrix": category_matrix.get('matrix', {})
        }
    except Exception:
        category = {"distribution": [], "total_users": 0, "total_gmv": 0, "segment_matrix": {}}

    # 6. 摘要洞察（基于数据生成简单洞察）
    summary = _generate_summary(overview, segments, geo, category)

    return {
        "date_range": {"start": start_str, "end": end_str},
        "overview": overview,
        "daily_trend": daily_trend,
        "segments": segments,
        "geo": geo,
        "category": category,
        "summary": summary
    }


def _generate_summary(
    overview: Dict[str, Any],
    segments: Dict[str, Any],
    geo: Dict[str, Any],
    category: Dict[str, Any]
) -> Dict[str, Any]:
    """生成摘要洞察"""
    insights = []

    # GMV 洞察
    amount = overview.get('amount', 0)
    if amount > 0:
        insights.append(f"分析期内 GMV 合计 ¥{amount:,.2f}")

    # 新老客比例
    new_users = overview.get('new_users', 0)
    old_users = overview.get('old_users', 0)
    total_users = new_users + old_users
    if total_users > 0:
        new_ratio = new_users / total_users * 100
        insights.append(f"新客占比 {new_ratio:.1f}%，老客 {100 - new_ratio:.1f}%")

    # 会员占比 (overview.member_ratio 是 0-1 ratio, Sprint 14.5 OverviewMetrics.member_ratio
    # 治根后保持 0-1 decimal; Sprint 27 同路线, 显示时 caller 自 ×100, 跟 AudienceView.vue:1073 模式一致)
    member_ratio = overview.get('member_ratio', 0)
    if member_ratio > 0:
        insights.append(f"会员金额占比 {member_ratio * 100:.1f}%")

    # 象限洞察
    seg_dist = segments.get('distribution', [])
    if seg_dist:
        # 找出用户最多的象限
        max_seg = max(seg_dist, key=lambda x: x.get('user_count', 0))
        insights.append(f"最大象限：{max_seg.get('name', '未知')}（{max_seg.get('user_count', 0):,} 用户）")

    # 地域洞察
    geo_dist = geo.get('distribution', [])
    if geo_dist:
        top_province = geo_dist[0].get('name', '未知')
        top_pct = geo_dist[0].get('占比', 0)
        insights.append(f"第一大省份：{top_province}（{top_pct:.1f}%）")

    # 品类洞察
    cat_dist = category.get('distribution', [])
    if cat_dist:
        top_cat = cat_dist[0].get('name', '未知')
        top_pct = cat_dist[0].get('占比', 0)
        insights.append(f"第一大品类：{top_cat}（{top_pct:.1f}%）")

    # 环比同比
    mom = overview.get('mom_change', {}).get('amount_pct', 0)
    yoy = overview.get('yoy_change', {}).get('amount_pct', 0)
    if mom != 0 or yoy != 0:
        insights.append(f"环比 {'↑' if mom > 0 else '↓'} {abs(mom):.1f}%，同比 {'↑' if yoy > 0 else '↓'} {abs(yoy):.1f}%")

    return {
        "insights": insights,
        "highlights": [
            {
                "type": "opportunity",
                "title": "地域机会",
                "description": f"{geo_dist[1].get('name', '未知') if len(geo_dist) > 1 else '待分析'} 省份有增长空间"
            },
            {
                "type": "warning",
                "title": "流失风险",
                "description": "关注沉睡土豪象限用户，择机激活"
            }
        ] if seg_dist else []
    }


if __name__ == "__main__":
    # 测试
    print("=== 报告汇总测试 ===")
    result = get_report_summary("2026-03-01", "2026-03-19", lookback_days=90)
    print(f"日期范围: {result['date_range']}")
    print(f"GMV: {result['overview'].get('amount', 0):,.2f}")
    print(f"象限数: {len(result['segments'].get('distribution', []))}")
    print(f"地域top3: {[g['name'] for g in result['geo'].get('distribution', [])[:3]]}")
    print(f"品类top3: {[c['name'] for c in result['category'].get('distribution', [])[:3]]}")
    print(f"洞察: {result['summary'].get('insights', [])}")
