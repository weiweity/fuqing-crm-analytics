#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMP数据抓取工具 - 统一入口
整合资产诊断、流转数据、单品洞察三个模块
支持独立运行或统一调度

用法:
    python dmp_master.py              # 运行所有模块
    python dmp_master.py --assets     # 仅运行资产诊断
    python dmp_master.py --flow       # 仅运行流转数据
    python dmp_master.py --items      # 仅运行单品洞察
    python dmp_master.py --assets --flow  # 运行指定模块
"""

import sys
import os
import argparse
import time
import random
from datetime import datetime

# 确保 core/ 目录在搜索路径中（处理从不同目录运行脚本的情况）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# 导入公共模块（必须在 sys.path.insert 之后，详见上方 _SCRIPT_DIR 块）
from dmp_common import (  # noqa: E402
    log, Config, BrowserManager, read_account, login_qianniu, check_dmp_session,
    get_missing_dates_assets, get_missing_dates_flow, get_missing_dates_item
)

# 导入三个子模块（保持原功能，必须在 sys.path.insert 之后）
import dmp_scraper  # noqa: E402
import dmp_flow_scraper  # noqa: E402
import dmp_item_insight_scraper  # noqa: E402
from dmp_item_insight_scraper import _get_latest_row_for_item  # noqa: E402

# 6 道门禁 + 飞书 webhook 告警（独立模块，详见 sanity_check.py 文档）
import sanity_check  # noqa: E402

# 缓存：item_id -> 最新一条CSV记录（每个item只查一次CSV）
_latest_row_cache = {}


def _get_latest_row_for_item_cached(item_id):
    """从缓存读取最新历史记录，每个item只全量扫描CSV一次"""
    if item_id not in _latest_row_cache:
        _latest_row_cache[item_id] = _get_latest_row_for_item(
            Config.ITEM_DATA_FILE, item_id
        )
    return _latest_row_cache[item_id]


def _is_page_alive(page):
    """快速检查页面/浏览器上下文是否仍然有效
    
    如果页面已崩溃，page.evaluate() 会抛出 TargetClosedError，
    此时所有后续 page 操作都会失败。
    """
    try:
        page.evaluate("() => 1")
        return True
    except Exception as e:
        log(f"⚠️ 页面健康检查失败: {e}")
        return False


def _recreate_page_and_login(browser, page, username, password):
    """重建 page 并重新登录，返回新的 page 对象
    
    Args:
        browser: BrowserContext 对象
        page: 当前的 page（将被关闭）
        username: 用户名
        password: 密码
    
    Returns:
        新的 page 对象，或 None 表示重建失败
    """
    # 先尝试关闭旧页面
    try:
        page.close()
    except Exception:
        pass
    
    time.sleep(2)
    
    try:
        new_page = browser.new_page()
        new_page.set_viewport_size({'width': 1920, 'height': 1080})
        log("✓ 新页面创建成功，重新登录...")
        
        if login_qianniu(new_page, username, password):
            log("✓ 重新登录成功")
            return new_page
        else:
            log("✗ 重新登录失败")
            return None
    except Exception as e:
        log(f"✗ 创建新页面或重新登录失败: {e}")
        return None


def run_assets_module(page, username, password):
    """
    运行资产诊断模块
    
    Args:
        page: Playwright页面对象
        username: 用户名
        password: 密码
    
    Returns:
        tuple: (success_count, total_count)
    """
    log("\n" + "=" * 60)
    log("【模块1/3】资产诊断数据抓取")
    log("=" * 60)
    
    # 检查需要补齐的日期
    missing_dates = get_missing_dates_assets(Config.ASSETS_DATA_FILE)
    
    if not missing_dates:
        log("资产诊断数据已是最新，无需补齐")
        return 0, 0
    
    log(f"需要补齐 {len(missing_dates)} 天: {[str(d) for d in missing_dates]}")
    
    # 循环抓取数据
    success_count = 0
    fail_dates = []
    
    for date_obj in missing_dates:
        log(f"\n{'='*40}")
        log(f"正在处理: {date_obj}")
        log(f"{'='*40}")
        
        try:
            # 使用原模块的抓取函数
            data = dmp_scraper.fetch_data_for_date(page, date_obj)
            
            if data and len(data) >= 4:
                dmp_scraper.append_to_csv(Config.ASSETS_DATA_FILE, date_obj, data)
                success_count += 1
                log(f"✓ {date_obj} 数据抓取成功")
            else:
                log(f"✗ {date_obj} 数据抓取失败或数据不足")
                fail_dates.append(date_obj)
        except Exception as e:
            log(f"✗ {date_obj} 抓取出错: {e}")
            fail_dates.append(date_obj)
    
    # ========== 失败重试机制（2026-05-20新增）==========
    if fail_dates:
        log(f"\n{'='*60}")
        log(f"等待 60 秒后对 {len(fail_dates)} 个失败日期进行重试...")
        log(f"{'='*60}")
        time.sleep(60)
        still_failed = []
        for date_obj in fail_dates:
            log(f"\n[重试] 资产诊断: {date_obj}")
            try:
                data = dmp_scraper.fetch_data_for_date(page, date_obj)
                if data and len(data) >= 4:
                    dmp_scraper.append_to_csv(Config.ASSETS_DATA_FILE, date_obj, data)
                    success_count += 1
                    log(f"✓ [重试成功] {date_obj}")
                else:
                    still_failed.append(date_obj)
                    log(f"✗ [重试失败] {date_obj} 数据不足")
            except Exception as e:
                log(f"✗ [重试异常] {date_obj}: {e}")
                still_failed.append(date_obj)
        fail_dates = still_failed
    
    log(f"\n资产诊断完成: 成功 {success_count}/{len(missing_dates)}")
    if fail_dates:
        log(f"最终失败日期: {[str(d) for d in fail_dates]}")
    
    return success_count, len(missing_dates)


def run_flow_module(page, username, password):
    """
    运行流转数据模块
    
    Args:
        page: Playwright页面对象
        username: 用户名
        password: 密码
    
    Returns:
        tuple: (success_count, total_count)
    """
    log("\n" + "=" * 60)
    log("【模块2/3】流转数据抓取")
    log("=" * 60)
    
    # 检查需要补齐的日期
    missing_dates = get_missing_dates_flow(Config.FLOW_DATA_FILE)
    
    if not missing_dates:
        log("流转数据已是最新，无需补齐")
        return 0, 0
    
    log(f"需要补齐 {len(missing_dates)} 天: {[str(d) for d in missing_dates]}")
    
    # 使用原模块的抓取函数
    try:
        success_count, stale_count, fail_count = dmp_flow_scraper.fetch_flow_data_for_dates(page, missing_dates)
        total = len(missing_dates)
        
        # ========== 失败重试机制（2026-05-20新增）==========
        if fail_count > 0:
            log(f"\n{'='*60}")
            log(f"等待 60 秒后对 {fail_count} 个失败日期进行重试...")
            log(f"{'='*60}")
            time.sleep(60)
            # 重新调用。已成功的数据CSV去重会跳过，只处理之前失败的
            retry_success, retry_stale, retry_fail = dmp_flow_scraper.fetch_flow_data_for_dates(page, missing_dates)
            success_count += retry_success
            fail_count = retry_fail  # 只保留最终失败数
            log(f"流转重试结果: 成功 +{retry_success}, 仍然失败 {retry_fail}")
        
        if stale_count > 0 or fail_count > 0:
            # 陈旧是T+1平台特性，不算失败；只统计真正的失败
            log(f"\n流转数据完成: 成功 {success_count}/{total}, T+1数据未更新 {stale_count}/{total}, 失败 {fail_count}/{total}")
        else:
            log(f"\n流转数据完成: 成功 {success_count}/{total}")
        return success_count, total
    except Exception as e:
        log(f"流转数据模块出错: {e}")
        return 0, len(missing_dates)


def run_items_module(page, username, password):
    """
    运行单品洞察模块
    
    Args:
        page: Playwright页面对象
        username: 用户名
        password: 密码
    
    Returns:
        tuple: (success_count, total_count)
    """
    log("\n" + "=" * 60)
    log("【模块3/3】单品洞察数据抓取")
    log("=" * 60)
    
    from datetime import datetime, timedelta
    from dmp_common import format_date_for_csv
    
    # 获取目标日期
    today = datetime.now()
    t_minus_1 = today - timedelta(days=1)
    t_minus_2 = today - timedelta(days=2)
    
    log(f"目标日期 T-1: {format_date_for_csv(t_minus_1)}, T-2: {format_date_for_csv(t_minus_2)}")
    
    # 分析欠缺日期
    missing_dates = get_missing_dates_item(Config.ITEM_DATA_FILE, Config.ITEM_IDS, max_days_to_fill=90)
    
    if not missing_dates:
        log("所有商品最近7天的数据都已齐全，无需抓取")
        return 0, 0
    
    # 构建需要抓取的任务列表
    tasks = []
    for item_id, dates in missing_dates.items():
        for date_str in dates:
            try:
                date_parts = date_str.split('/')
                target_date = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]))
                tasks.append({
                    'item_id': item_id,
                    'target_date': target_date,
                    'date_str': date_str
                })
            except Exception:
                log(f"解析日期失败: {date_str}")
    
    # === 断点续传：加载已完成的任务 ===
    completed_items = dmp_item_insight_scraper._load_completed_items()
    log(f"已完成缓存中已有 {len(completed_items)} 条记录")
    
    # 过滤掉已完成的任務
    tasks_to_run = [t for t in tasks if (t['item_id'], t['date_str']) not in completed_items]
    skipped_count = len(tasks) - len(tasks_to_run)
    if skipped_count > 0:
        log(f"断点续传：跳过 {skipped_count} 条已完成的任务，剩余 {len(tasks_to_run)} 条")
    
    if not tasks_to_run:
        log("所有任务均已完成，无需抓取")
        return 0, 0
    
    log(f"\n共需抓取 {len(tasks_to_run)} 条数据")
    for task in tasks_to_run[:5]:  # 只显示前5个
        log(f"  - 商品 {task['item_id']} 日期 {task['date_str']}")
    if len(tasks_to_run) > 5:
        log(f"  ... 还有 {len(tasks_to_run)-5} 个任务")
    
    # ========== 按日期分组抓取（为Date级Gate做准备）==========
    # 按 date_str 分组
    from collections import defaultdict
    tasks_by_date = defaultdict(list)
    for task in tasks_to_run:
        tasks_by_date[task['date_str']].append(task)

    log(f"\n共 {len(tasks_by_date)} 个日期需要处理")

    success_count = 0
    fail_tasks = []

    for date_str, date_tasks in tasks_by_date.items():
        log(f"\n{'='*50}")
        log(f"处理日期: {date_str}，共 {len(date_tasks)} 个商品")
        log(f"{'='*50}")

        # -------- 第一步：抓取该日期下所有商品的数据 --------
        all_data = {}  # item_id -> data
        for task_index, task in enumerate(date_tasks):
            item_id = task['item_id']
            target_date = task['target_date']
            log(f"\n--- 商品 {item_id} ---")
            try:
                t1 = target_date
                t2 = target_date - timedelta(days=1)
                data = dmp_item_insight_scraper.fetch_item_data(page, item_id, t1, t2)
                all_data[item_id] = data
            except Exception as e:
                error_msg = str(e).lower()
                if 'closed' in error_msg or 'target' in error_msg:
                    log("⚠️ 浏览器崩溃，向上传播")
                    raise
                all_data[item_id] = None
                log(f"抓取出错: {e}")

            # 商品间延迟（反检测）：与 run_items_fetch() 保持一致
            if task_index < len(date_tasks) - 1:
                delay = random.uniform(10, 20)  # 10-20秒随机延迟
                log(f"随机延迟 {delay:.1f}秒后处理下一个商品...")
                time.sleep(delay)

        # Gate 2 已删除：不按数值跳过日期，每个日期都写入
        # 日期去重由 append_tocsv 的 L2465 处理（同商品同日期才跳过）


        # -------- 第三步：写入数据（逐个，过滤空数据）--------
        for task in date_tasks:
            item_id = task['item_id']
            date_str_task = task['date_str']
            data = all_data[item_id]

            try:
                if data and data.get('zichan_zongliang', 0) > 0:
                    # 6 道门禁（独立模块）— 失败 → 标 likely-wrong + 推飞书 webhook
                    # 不阻塞写入：append_tocsv 自己还有阻塞类校验
                    try:
                        sanity_result = sanity_check.run_all(
                            data=data,
                            csv_file=Config.ITEM_DATA_FILE,
                            spa_date=data.get('_spa_trigger_date'),
                            target_date=date_str_task,
                            scraper_name='dmp_item_insight',
                        )
                        if sanity_result['should_flag_likely_wrong']:
                            data['_sanity'] = 'likely-wrong'
                            failed_names = [n for n, _ in sanity_result['failed_gates']]
                            log(f"⚠️ 6 道门禁失败 ({len(failed_names)}/6): {failed_names}，"
                                f"标 data_quality_flag=likely-wrong，"
                                f"webhook={'已发' if sanity_result['alert']['sent'] else sanity_result['alert']['reason']}")
                    except Exception as sc_err:
                        # sanity_check 异常 → 不影响主流程，仅记录
                        log(f"⚠️ sanity_check.run_all 异常（不阻塞写入）: {sc_err}")

                    # append_to_csv 内部会走 Gate 1（完全相同则跳过）
                    if dmp_item_insight_scraper.append_tocsv(Config.ITEM_DATA_FILE, data):
                        success_count += 1
                        # 写入缓存（断点续传的前提）
                        try:
                            dmp_item_insight_scraper._mark_completed(item_id, date_str_task)
                        except Exception as e:
                            log(f"⚠️ 写入完成缓存失败（非致命）: {e}")
                        log(f"✓ 商品 {item_id} 日期 {date_str_task} 写入成功")
                    else:
                        log(f"✗ 商品 {item_id} 日期 {date_str_task} 保存失败")
                        fail_tasks.append(task)
                else:
                    log(f"  商品 {item_id} 日期 {date_str_task} 数据为空，跳过")
                    dmp_item_insight_scraper._mark_completed(item_id, date_str_task)
            except Exception as e:
                error_msg = str(e).lower()
                log(f"✗ 商品 {item_id} 日期 {date_str_task} 出错: {e}")
                fail_tasks.append(task)
                if 'closed' in error_msg or 'target' in error_msg:
                    log("⚠️ 浏览器崩溃，向上传播")
                    raise

        # 每个日期之间间隔2秒
        time.sleep(2)
    
    log(f"\n单品洞察第一轮完成: 成功 {success_count}/{len(tasks_to_run)}")
    if fail_tasks:
        log(f"失败任务数: {len(fail_tasks)}")
        
        # ========== 失败重试机制（2026-05-20新增） ==========
        # 05-07 证据：早上12:00 10个商品失败(总资产=0)，下午17:17 全部成功
        # 根因：达摩盘部分商品数据T+1生成有延迟，不是商品问题，是时间问题
        # 方案：等60秒后重试一轮，大幅提高成功率
        retry_count = 0
        retry_success = 0
        still_failed = []
        
        log(f"\n{'='*60}")
        log(f"等待 60 秒后对 {len(fail_tasks)} 个失败任务进行重试...")
        log(f"{'='*60}")
        time.sleep(60)
        
        for i, task in enumerate(fail_tasks, 1):
            item_id = task['item_id']
            target_date = task['target_date']
            date_str = task['date_str']
            
            log(f"\n[重试 {i}/{len(fail_tasks)}] 商品 {item_id} 日期 {date_str}")
            
            try:
                t1 = target_date
                t2 = target_date - timedelta(days=1)
                data = dmp_item_insight_scraper.fetch_item_data(page, item_id, t1, t2)

                if data and data.get('zichan_zongliang', 0) > 0:
                    # 6 道门禁（独立模块）— 失败 → 标 likely-wrong + 推飞书 webhook
                    try:
                        sanity_result = sanity_check.run_all(
                            data=data,
                            csv_file=Config.ITEM_DATA_FILE,
                            spa_date=data.get('_spa_trigger_date'),
                            target_date=date_str,
                            scraper_name='dmp_item_insight (retry)',
                        )
                        if sanity_result['should_flag_likely_wrong']:
                            data['_sanity'] = 'likely-wrong'
                            failed_names = [n for n, _ in sanity_result['failed_gates']]
                            log(f"⚠️ [重试] 6 道门禁失败 ({len(failed_names)}/6): {failed_names}，"
                                f"标 data_quality_flag=likely-wrong")
                    except Exception as sc_err:
                        log(f"⚠️ [重试] sanity_check.run_all 异常（不阻塞写入）: {sc_err}")

                    if dmp_item_insight_scraper.append_tocsv(Config.ITEM_DATA_FILE, data):
                        success_count += 1
                        retry_success += 1
                        retry_count += 1
                        # 写入缓存（断点续传的前提）
                        try:
                            dmp_item_insight_scraper._mark_completed(item_id, date_str)
                        except Exception as mc_err:
                            log(f"⚠️ 写入完成缓存失败（非致命）: {mc_err}")
                        log(f"✓ [重试成功] 商品 {item_id} 日期 {date_str}")
                    else:
                        still_failed.append(task)
                        retry_count += 1
                        log(f"✗ [重试失败-保存] 商品 {item_id} 日期 {date_str}")
                else:
                    still_failed.append(task)
                    retry_count += 1
                    log(f"✗ [重试失败-空数据] 商品 {item_id} 日期 {date_str}")
                
                if i < len(fail_tasks):
                    time.sleep(2)
                    
            except Exception as e:
                error_msg = str(e).lower()
                log(f"✗ [重试异常] 商品 {item_id} 日期 {date_str}: {e}")
                still_failed.append(task)
                retry_count += 1
                
                if 'closed' in error_msg or 'target' in error_msg:
                    log("⚠️ 浏览器已崩溃，中断重试")
                    break
        
        # 更新失败列表
        fail_tasks = still_failed
        log(f"\n单品洞察重试结果: 成功 {retry_success}/{retry_count}")
    
    if fail_tasks:
        log(f"最终失败任务数: {len(fail_tasks)}")
    
    # 抓取完成后统一排序CSV（append_to_csv改为追加模式后的性能优化）
    try:
        dmp_item_insight_scraper.sort_csv_by_date(Config.ITEM_DATA_FILE)
        log("单品洞察CSV已按日期排序")
    except Exception as e:
        log(f"排序CSV失败: {e}")
    
    return success_count, len(tasks_to_run)


def sync_to_frontend():
    """
    自动同步CSV数据文件到前端看板目录
    抓取完成后自动调用，无需手动复制
    """
    import shutil
    
    # 数据文件列表
    data_files = ['data.csv', 'data2.csv', 'data3.csv']
    
    # frontend目录：core的上一级就是DMP_test_package，下面是frontend
    frontend_dir = os.path.join(os.path.dirname(Config._SCRIPT_DIR), 'frontend')
    
    log("\n" + "-" * 40)
    log("同步数据到前端看板...")
    log("-" * 40)
    
    if not os.path.exists(frontend_dir):
        log(f"警告：前端目录不存在 {frontend_dir}，跳过同步")
        return
    
    synced = 0
    for f in data_files:
        src = os.path.join(Config._SCRIPT_DIR, f)
        dst = os.path.join(frontend_dir, f)
        
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                log(f"  [OK] {f} -> frontend/")
                synced += 1
            except Exception as e:
                log(f"  [FAIL] {f} 同步失败: {e}")
        else:
            log(f"  [SKIP] {f} 不存在，跳过")
    
    log(f"同步完成: {synced}/{len(data_files)} 个文件")
    log("-" * 40)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='DMP数据抓取工具 - 统一入口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python dmp_master.py              # 运行所有模块
  python dmp_master.py --assets     # 仅运行资产诊断
  python dmp_master.py --flow       # 仅运行流转数据
  python dmp_master.py --items      # 仅运行单品洞察
  python dmp_master.py -a -f        # 运行资产诊断+流转数据
        """
    )
    
    parser.add_argument('-a', '--assets', action='store_true',
                        help='运行资产诊断模块')
    parser.add_argument('-f', '--flow', action='store_true',
                        help='运行流转数据模块')
    parser.add_argument('-i', '--items', action='store_true',
                        help='运行单品洞察模块')
    parser.add_argument('--all', action='store_true',
                        help='运行所有模块（默认）')
    
    args = parser.parse_args()
    
    # 如果没有指定任何模块，默认运行所有
    if not (args.assets or args.flow or args.items):
        args.assets = True
        args.flow = True
        args.items = True
    
    # 启动信息
    log("=" * 60)
    log("DMP数据抓取工具 - 统一入口")
    log("=" * 60)
    
    # 显示运行计划
    modules = []
    if args.assets:
        modules.append("资产诊断")
    if args.flow:
        modules.append("流转数据")
    if args.items:
        modules.append("单品洞察")
    
    log(f"计划运行模块: {', '.join(modules)}")
    
    # 读取账号
    username, password = read_account()
    if not username or not password:
        log("错误：无法读取账号密码")
        return False
    
    # 使用浏览器上下文管理器
    # headless=True: 单品洞察 API 拦截在有头模式下失败(页面调整后),
    # 无头模式验证通过。资产诊断和流转在无头模式下也正常。
    with BrowserManager(headless=True) as browser:
        page = browser.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})
        
        try:
            # 会话检测：避免重复登录触发DMP反爬
            log("\n" + "=" * 60)
            log("步骤1: 检查达摩盘会话状态")
            log("=" * 60)
            
            if check_dmp_session(page):
                log("✓ 会话有效，跳过登录流程")
            else:
                log("会话已过期，需要重新登录")
                if not login_qianniu(page, username, password, debug_name="master_login"):
                    log("登录失败，退出")
                    return False
                log("✓ 登录成功！")
            
            # 验证达摩盘可达性（快速健康检查）
            log("\n验证达摩盘可达性...")
            try:
                from datetime import timedelta
                check_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
                health_url = f"{Config.DMP_BASE_URL}?spm={Config.DMP_SPM}{Config.DMP_ROUTE_ASSETS}?bizDate={check_date}"
                page.goto(health_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                page_title = page.title() or ""
                if "404" in page_title or "not found" in page_title.lower():
                    log("⚠️ 警告：达摩盘URL可能已变更（检测到404）")
                    log(f"   当前SPM: {Config.DMP_SPM}")
                    log(f"   当前路由: {Config.DMP_ROUTE_ASSETS}")
                    log("   请手动确认达摩盘URL格式是否变化")
                else:
                    log("✓ 达摩盘可达性检查通过")
            except Exception as e:
                log(f"⚠️ 达摩盘健康检查失败: {e}（继续尝试抓取）")
            
            # 运行各模块
            results = {}
            
            if args.assets:
                try:
                    success, total = run_assets_module(page, username, password)
                    results['assets'] = (success, total)
                except Exception as e:
                    log(f"资产诊断模块异常: {e}")
                    results['assets'] = (0, 0)
                
                # P1修复：资产诊断完成后检查页面健康状态
                if args.flow or args.items:
                    if not _is_page_alive(page):
                        log("⚠️ 资产诊断后页面已失效，重建中...")
                        new_page = _recreate_page_and_login(browser, page, username, password)
                        if new_page:
                            page = new_page
                        else:
                            log("✗ 页面重建失败，后续模块可能无法正常工作")
            
            if args.flow:
                try:
                    success, total = run_flow_module(page, username, password)
                    results['flow'] = (success, total)
                except Exception as e:
                    log(f"流转数据模块异常: {e}")
                    results['flow'] = (0, 0)
                
                # P1修复：流转完成后检查页面健康状态
                if args.items:
                    if not _is_page_alive(page):
                        log("⚠️ 流转模块后页面已失效，重建中...")
                        new_page = _recreate_page_and_login(browser, page, username, password)
                        if new_page:
                            page = new_page
                        else:
                            log("✗ 页面重建失败，后续模块可能无法正常工作")
            
            if args.items:
                # 单品模块可能耗时较长，增加崩溃重试机制
                max_item_retries = 2
                for item_retry in range(max_item_retries + 1):
                    try:
                        success, total = run_items_module(page, username, password)
                        results['items'] = (success, total)
                        break
                    except Exception as e:
                        error_msg = str(e).lower()
                        if ('closed' in error_msg or 'target' in error_msg) and item_retry < max_item_retries:
                            log(f"⚠️ 单品模块浏览器崩溃（第{item_retry+1}次），尝试恢复...")
                            try:
                                page.close()
                            except Exception:
                                pass
                            time.sleep(3)
                            
                            # P1修复：先尝试在当前上下文中新建页面
                            try:
                                new_page = browser.new_page()
                                new_page.set_viewport_size({'width': 1920, 'height': 1080})
                                page = new_page
                                log("✓ 在当前上下文中创建新页面成功")
                            except Exception:
                                # 上下文已崩溃，需要重建整个 BrowserManager
                                log("⚠️ 浏览器上下文已损坏，尝试完整重建...")
                                try:
                                    browser.close()
                                except Exception:
                                    pass
                                time.sleep(3)
                                try:
                                    new_browser = BrowserManager(headless=True).__enter__()
                                    page = new_browser.new_page()
                                    page.set_viewport_size({'width': 1920, 'height': 1080})
                                    # 注意：这里 browser 被重新赋值，但旧 browser 已在 __exit__ 中关闭
                                    browser = new_browser
                                    log("✓ 浏览器上下文完全重建成功")
                                except Exception as rebuild_err:
                                    log(f"✗ 浏览器上下文重建失败: {rebuild_err}")
                                    results['items'] = (0, 0)
                                    break
                            
                            log("重新登录...")
                            if login_qianniu(page, username, password):
                                log("✓ 重新登录成功，继续单品模块")
                                continue
                            else:
                                log("✗ 重新登录失败")
                                results['items'] = (0, 0)
                                break
                        else:
                            log(f"单品洞察模块异常: {e}")
                            results['items'] = (0, 0)
                            break
            
            # 汇总结果
            log("\n" + "=" * 60)
            log("抓取完成汇总")
            log("=" * 60)
            
            total_success = 0
            total_tasks = 0
            
            for module_name, (success, total) in results.items():
                name_map = {
                    'assets': '资产诊断',
                    'flow': '流转数据',
                    'items': '单品洞察'
                }
                log(f"{name_map.get(module_name, module_name)}: {success}/{total}")
                total_success += success
                total_tasks += total
            
            log(f"\n总计: {total_success}/{total_tasks}")
            log("=" * 60)
            
            # 自动同步CSV到前端看板目录
            sync_to_frontend()
            
        except Exception as e:
            log(f"运行出错: {e}")
            import traceback
            log(traceback.format_exc())
    
    log("\n所有任务完成，浏览器已关闭")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
