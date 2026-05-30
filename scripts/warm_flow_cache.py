"""
RFM Flow 缓存预热脚本

遍历月/季/年维度的所有时间段，对 R/F/M 三个 flow 端点调用一次，
触发缓存写入。已缓存的自动跳过。

用法: PYTHONPATH="." python scripts/warm_flow_cache.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.rfm._shared import (
    _fetch_data_version,
    _flow_cache_key,
    _get_cached_flow,
)
from backend.services.rfm.r_flow import get_rfm_r_flow
from backend.services.rfm.f_flow import get_rfm_f_flow
from backend.services.rfm.m_flow import get_rfm_m_flow


def generate_periods():
    """生成所有缓存时间段：月 / 季 / 年"""
    periods = []

    # 月度：2024-01 ~ 2026-05
    for year in [2024, 2025, 2026]:
        for month in range(1, 13):
            if year == 2026 and month > 5:
                break
            start = f"{year}-{month:02d}-01"
            # 月底日期
            if month == 12:
                end = f"{year}-12-31"
            elif month == 2:
                # 简单处理闰年
                import calendar
                last = calendar.monthrange(year, month)[1]
                end = f"{year}-{month:02d}-{last:02d}"
            elif month in [4, 6, 9, 11]:
                end = f"{year}-{month:02d}-30"
            else:
                end = f"{year}-{month:02d}-31"
            # 如果当前月在 5 月，安全截断
            from datetime import date
            today = date.today()
            if year == today.year and month == today.month:
                end = f"{today.year}-{today.month:02d}-{(today.day - 1):02d}"
            periods.append(("月度", start, end))

    # 季度：2024Q1 ~ 2026Q2
    quarters = [
        (2024, 1), (2024, 2), (2024, 3), (2024, 4),
        (2025, 1), (2025, 2), (2025, 3), (2025, 4),
        (2026, 1), (2026, 2),
    ]
    for y, q in quarters:
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        start = f"{y}-{start_month:02d}-01"
        import calendar as cal
        last = cal.monthrange(y, end_month)[1]
        end = f"{y}-{end_month:02d}-{last}"
        from datetime import date
        today = date.today()
        if y == today.year and end_month >= today.month:
            end = f"{today.year}-{today.month:02d}-{(today.day - 1):02d}"
        periods.append(("季度", start, end))

    # 年度：2024, 2025, 2026YTD
    period_ranges = [
        ("年度", "2024-01-01", "2024-12-31"),
        ("年度", "2025-01-01", "2025-12-31"),
    ]
    from datetime import date
    today = date.today()
    ytd_end = f"{today.year}-{today.month:02d}-{(today.day - 1):02d}"
    period_ranges.append(("年度", "2026-01-01", ytd_end))

    periods.extend(period_ranges)
    return periods


def main():
    data_version = _fetch_data_version()
    print(f"数据版本: {data_version}")
    periods = generate_periods()
    print(f"待覆盖: {len(periods)} 个时间段 × 3 端点 = {len(periods) * 3} 次查询\n")

    skipped = 0
    cached = 0
    for label, start, end in periods:
        for flow_type, func in [("r_flow", get_rfm_r_flow), ("f_flow", get_rfm_f_flow), ("m_flow", get_rfm_m_flow)]:
            key = _flow_cache_key(flow_type, start, end, None, "GSV", None, None, None, data_version)
            if _get_cached_flow(key, data_version):
                skipped += 1
                continue

            try:
                func(start_date=start, end_date=end, metric_type="GSV")
                cached += 1
                print(f"  ✅ {label} {start}~{end} {flow_type}")
            except Exception as e:
                print(f"  ❌ {label} {start}~{end} {flow_type}: {e}")

    print(f"\n完成：缓存 {cached} 个，已跳过 {skipped} 个")


if __name__ == "__main__":
    main()
