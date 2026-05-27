#!/usr/bin/env python3
"""
芙清 CRM 架构合规检查脚本

检查规则：
1. 前端禁止计算 YOY 等业务指标
2. Service 禁止自行定义 _yoy 等函数
3. 后端应返回 TTL 行

运行方式：
    python scripts/check_architecture.py
    python scripts/check_architecture.py --fix  # 自动修复（部分场景）

退出码：
    0 = 通过
    1 = 警告（可修复）
    2 = 错误（需人工检查）
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend-vue3" / "src"
BACKEND = ROOT / "backend"


def check_frontend_yoy_calculation():
    """检查前端是否在计算 YOY 等业务指标"""
    issues = []

    # 匹配前端的 YOY 计算模式（排除合法场景）
    patterns = [
        (r'yoy\s*:\s*[^(]*\([^)]*\)', '前端 YOY 计算'),
        (r'ratio_yoy\s*:', '前端 ratio_yoy 计算'),
        (r'member_ratio_yoy\s*:', '前端 member_ratio_yoy 计算'),
    ]

    for vue_file in FRONTEND.rglob("*.vue"):
        content = vue_file.read_text()
        for pattern, desc in patterns:
            matches = re.findall(pattern, content)
            if matches:
                # 过滤合法场景：后端返回数据的直接使用
                for match in matches:
                    if 'backend' in match or 'api' in match or 'response' in match:
                        continue
                    issues.append(f"  {vue_file.relative_to(ROOT)}: {desc}")

    return issues


def check_service_local_yoy():
    """检查 Service 是否自行定义了 _yoy 函数"""
    issues = []

    forbidden_patterns = [
        (r'def _yoy\s*\(', 'Service 中定义了 _yoy 函数'),
        (r'def _yoy_ratio\s*\(', 'Service 中定义了 _yoy_ratio 函数'),
        (r'def _mom\s*\(', 'Service 中定义了 _mom 函数'),
        (r'def _yoy_rate\s*\(', 'Service 中定义了 _yoy_rate 函数'),
    ]

    for service_file in (BACKEND / "services").glob("*.py"):
        content = service_file.read_text()
        for pattern, desc in forbidden_patterns:
            if re.search(pattern, content):
                issues.append(f"  {service_file.relative_to(ROOT)}: {desc}")

    return issues


def check_backend_ttl_return():
    """检查后端是否返回 TTL 行"""
    issues = []

    # 检查 metrics_service.py 是否在 channel_all 中追加 TTL 行
    metrics_file = BACKEND / "services" / "metrics_service.py"
    if metrics_file.exists():
        content = metrics_file.read_text()
        if '"channel": "TTL"' not in content and "'channel': 'TTL'" not in content:
            issues.append("  metrics_service.py: channel_all 未返回 TTL 行")

    return issues


def check_calculations_import():
    """检查 Service 是否导入了 calculations"""
    issues = []

    for service_file in (BACKEND / "services").glob("*.py"):
        content = service_file.read_text()

        # 检查是否使用了 calculations 中的函数
        if 'from backend.semantic.calculations import' not in content:
            # 检查是否有 yoy_absolute 等函数调用
            if re.search(r'yoy_absolute|yoy_ratio|yoy_repurchase_rate', content):
                issues.append(f"  {service_file.relative_to(ROOT)}: 使用了 calculations 函数但未导入")

    return issues


def main():
    print("=" * 60)
    print("芙清 CRM 架构合规检查")
    print("=" * 60)

    all_issues = []
    warnings = []
    errors = []

    # 执行各项检查
    checks = [
        ("前端业务计算检查", check_frontend_yoy_calculation, "error"),
        ("Service 本地函数检查", check_service_local_yoy, "error"),
        ("后端 TTL 返回检查", check_backend_ttl_return, "warning"),
        ("Calculations 导入检查", check_calculations_import, "error"),
    ]

    for name, check_func, severity in checks:
        print(f"\n[{name}]")
        issues = check_func()
        if issues:
            print(f"  ❌ 发现 {len(issues)} 个问题:")
            for issue in issues:
                print(issue)
            if severity == "error":
                errors.extend(issues)
            else:
                warnings.extend(issues)
        else:
            print("  ✅ 通过")

    # 输出总结
    print("\n" + "=" * 60)
    print("检查总结")
    print("=" * 60)
    print(f"  错误: {len(errors)} 个")
    print(f"  警告: {len(warnings)} 个")

    if errors:
        print("\n❌ 架构违规，必须修复")
        return 2
    elif warnings:
        print("\n⚠️  存在警告，建议修复")
        return 1
    else:
        print("\n✅ 全部检查通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
