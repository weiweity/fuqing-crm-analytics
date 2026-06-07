#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
淘宝达摩盘单品洞察数据自动抓取工具
流程：千牛登录 -> 循环14个商品ID -> 设置日期 -> 抓取单品资产数据

支持独立运行或通过 dmp_master.py 统一调度
"""

import csv
import json
import time
import os
import sys
import re
import random
from datetime import datetime, timedelta
from pathlib import Path

# playwright 用于独立运行模式
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# 导入反检测模块
try:
    from anti_detect import (
        human_delay, human_delay_normal, human_scroll,
        apply_anti_detect, RateLimiter
    )
    HAS_ANTI_DETECT = True
except ImportError:
    HAS_ANTI_DETECT = False

import yaml

# 尝试导入选择器引擎
try:
    from selector_engine import AIAgent
    HAS_SELECTOR_ENGINE = True
except ImportError:
    HAS_SELECTOR_ENGINE = False

# 先定义一个简单的log函数（用于load_config，避免循环依赖）
def _simple_log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# 先定义load_config函数（在try之前，确保两种模式都能用）
def load_config():
    """从config/items.yaml加载配置"""
    config_path = Path(__file__).parent / "config" / "items.yaml"
    default_config = {
        'items': [
            "587051744204", "597655781410", "587053192746", "683395365107", "654390297284",
            "803474428381", "870597889980", "621639424901", "601760206476", "612503357090",
            "803417397714", "994162104051", "933524395698", "900975734816",
            "1010458880710"  # 传明酸面膜（2026-04-21新增）
        ],
        'anti_detect': {
            'max_items_per_run': 5,
            'item_delay_min': 10,
            'item_delay_max': 30,
            'max_requests_per_day': 50,
            'page_load_delay_min': 2,
            'page_load_delay_max': 4,
            'date_picker_delay_min': 1,
            'date_picker_delay_max': 2,
            'data_refresh_delay_min': 1.5,
            'data_refresh_delay_max': 2.5,
        },
        'browser': {
            'viewport_width': 1920,
            'viewport_height': 1080,
            'launch_args': [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
            'user_data_dir': 'chrome_profile',
        },
        'scraping': {
            'date_select_max_retries': 3,
            'data_refresh_max_wait': 12,
            'data_refresh_poll_count': 6,
            'days_to_check': 7,
        },
        'paths': {
            'item_data_file': 'data3.csv',
            'debug_dir': 'del',
            'account_file': 'account.txt',
        }
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
            if yaml_config:
                for key in default_config:
                    if key in yaml_config:
                        if isinstance(default_config[key], dict):
                            default_config[key].update(yaml_config[key])
                        else:
                            default_config[key] = yaml_config[key]
            _simple_log(f"已从配置文件加载: {config_path}")
        except Exception as e:
            _simple_log(f"加载配置文件失败，使用默认配置: {e}")
    
    return default_config


def _get_min_valid_total_for_item(item_id):
    """从配置文件读取指定商品的benchmark过滤阈值
    
    Args:
        item_id: 商品ID（字符串）
    
    Returns:
        int: 最小有效资产总量阈值（未配置时返回默认值20000）
    """
    import yaml
    config_path = Path(__file__).parent / "config" / "items.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        per_item = cfg.get('benchmark_filter', {}).get('per_item', {})
        default_min = cfg.get('benchmark_filter', {}).get('default_min_valid_total', 20000)
        return per_item.get(str(item_id), default_min)
    except Exception:
        return 20000  # 读取失败时使用默认值

# 尝试导入公共模块
try:
    from dmp_common import (
        log, Config, BrowserManager, read_account, login_qianniu,
        detect_encoding, format_date_for_csv,
        get_missing_dates_item
    )
    USING_COMMON = True
    
    # 使用公共模块的配置 - 创建配置适配器
    class ConfigAdapter:
        """适配器类，使Config类可以像字典一样使用"""
        def __init__(self):
            self.config_obj = Config()
            
        def get(self, key, default=None):
            """模拟字典的get方法"""
            # 特殊处理某些键
            if key == 'items':
                return self.config_obj.ITEM_IDS
            elif key == 'paths':
                return {
                    'item_data_file': os.path.basename(self.config_obj.ITEM_DATA_FILE),
                    'debug_dir': os.path.basename(self.config_obj.DEBUG_DIR),
                    'account_file': os.path.basename(self.config_obj.ACCOUNT_FILE)
                }
            elif key == 'browser':
                return {
                    'user_data_dir': os.path.basename(self.config_obj.USER_DATA_DIR)
                }
            elif key == 'anti_detect':
                # 提供默认的反检测配置
                return {
                    'page_load_delay_min': 2,
                    'page_load_delay_max': 4,
                    'data_refresh_delay_min': 1.5,
                    'data_refresh_delay_max': 2.5,
                    'date_picker_delay_min': 1,
                    'date_picker_delay_max': 2,
                    'max_items_per_run': 5,
                    'item_delay_min': 10,
                    'item_delay_max': 30,
                    'max_requests_per_day': 50
                }
            else:
                return default
    
    CONFIG = ConfigAdapter()
    
    # 公共模块模式下的变量设置
    config_obj = Config()
    _SCRIPT_DIR = Path(__file__).parent.resolve()
    
    # 设置文件路径（与独立模式保持一致）
    DATA_FILE = config_obj.ITEM_DATA_FILE
    DEBUG_DIR = config_obj.DEBUG_DIR
    USER_DATA_DIR = config_obj.USER_DATA_DIR
    ACCOUNT_FILE = config_obj.ACCOUNT_FILE
    
    # 商品ID列表
    ITEM_IDS = config_obj.ITEM_IDS
    
except ImportError:
    USING_COMMON = False
    
    # 独立模式：加载YAML配置
    CONFIG = load_config()
    
    # 获取脚本所在目录（跨平台）
    _SCRIPT_DIR = Path(__file__).parent.resolve()
    
    # 从配置读取路径
    DATA_FILE = str(_SCRIPT_DIR / CONFIG['paths']['item_data_file'])
    DEBUG_DIR = str(_SCRIPT_DIR / CONFIG['paths']['debug_dir'])
    USER_DATA_DIR = str(_SCRIPT_DIR / CONFIG['browser']['user_data_dir'])
    ACCOUNT_FILE = str(_SCRIPT_DIR / CONFIG['paths']['account_file'])
    
    # 从配置读取商品ID列表
    ITEM_IDS = CONFIG['items']
    
    def log(msg):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] {msg}")
    
    def detect_encoding(file_path):
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1024)
                return encoding
            except Exception:
                continue
        return 'utf-8'
    
    def read_account():
        try:
            with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                username = lines[0].strip().replace('账号：', '')
                password = lines[1].strip().replace('密码：', '')
                log(f"读取到用户名: {username}")
                return username, password
        except Exception as e:
            log(f"读取账号文件失败: {e}")
            return None, None
    
    def format_date_for_csv(dt):
        return f"{dt.year}/{dt.month}/{dt.day}"
    
    # parse_number 和 get_missing_dates 使用全局版本（见下方）


def get_target_dates():
    """获取目标日期（T-1优先，T-2备选）"""
    today = datetime.now()
    t_minus_1 = today - timedelta(days=1)
    t_minus_2 = today - timedelta(days=2)
    return t_minus_1, t_minus_2


def get_missing_dates(csv_file, item_ids, days_to_check=7):
    """分析CSV文件，找出每个商品ID欠缺的日期
    
    Args:
        csv_file: CSV文件路径
        item_ids: 商品ID列表
        days_to_check: 检查最近多少天的数据
    
    Returns:
        dict: {item_id: [date1, date2, ...]} 需要补抓的日期列表
    """
    from datetime import datetime, timedelta
    
    # 生成最近N天的日期列表（从昨天开始倒推）
    today = datetime.now()
    target_dates = []
    for i in range(1, days_to_check + 1):
        date = today - timedelta(days=i)
        target_dates.append(format_date_for_csv(date))
    
    log(f"需要检查的日期: {target_dates}")
    
    # 读取CSV中已有的数据
    existing_data = {}  # {item_id: set(dates)}
    
    if os.path.exists(csv_file):
        try:
            encoding = detect_encoding(csv_file)
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item_id = row.get('ID', '')
                    date = row.get('时间', '')
                    if item_id and date:
                        if item_id not in existing_data:
                            existing_data[item_id] = set()
                        existing_data[item_id].add(date)
            log(f"CSV中已有 {len(existing_data)} 个商品的数据")
        except Exception as e:
            log(f"读取CSV分析欠缺日期失败: {e}")
    
    # 找出每个商品欠缺的日期
    missing_dates = {}
    for item_id in item_ids:
        existing_dates = existing_data.get(item_id, set())
        missing = [d for d in target_dates if d not in existing_dates]
        if missing:
            missing_dates[item_id] = missing
            log(f"商品 {item_id} 欠缺 {len(missing)} 天数据: {missing}")
    
    return missing_dates


# ============ 辅助函数 ============
def _get_prev_day_total(item_id, prev_date_str, data_file):
    """从CSV读取指定商品在指定日期的资产总量

    Args:
        item_id: 商品ID
        prev_date_str: 日期字符串，格式 'YYYY/M/D'（非零填充，如 '2026/5/15'）
        data_file: CSV文件路径

    Returns:
        int: 资产总量，读取失败返回None
    """
    if not data_file or not os.path.exists(data_file):
        return None
    try:
        encoding = detect_encoding(data_file)
        with open(data_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ID', '').strip() == str(item_id).strip():
                    date_val = row.get('时间', '').strip()
                    # 日期匹配（CSV中格式为 '2026/5/15' 或 '2026/05/15'）
                    # 统一去掉前导零进行比较
                    def normalize_date(d):
                        parts = d.split('/')
                        return f"{parts[0]}/{int(parts[1])}/{int(parts[2])}"
                    if normalize_date(date_val) == prev_date_str:
                        total_str = row.get('资产总量', '0').replace(',', '').strip()
                        return int(total_str) if total_str.isdigit() else None
    except Exception:
        pass
    return None


# ============ 登录（兼容模式） ============
# ============ 单品数据抓取 ============
def fetch_item_data(page, item_id, target_date, fallback_date):
    """抓取单个商品的数据 - 修复版：确保选择正确的日期
    
    Args:
        page: Playwright页面对象
        item_id: 商品ID
        target_date: 目标日期对象（优先尝试）
        fallback_date: 备选日期对象
    
    Returns:
        dict: 包含资产数据的字典，失败返回None
    """
    # 确定DEBUG_DIR
    debug_dir = Config.DEBUG_DIR if USING_COMMON else DEBUG_DIR
    
    # 初始化 selected_date（避免 Python 局部变量作用域问题）
    selected_date = None
    
    # 2026-04 更新：需要加 spm 参数，否则返回404
    spm = Config.DMP_SPM
    route = Config.DMP_ROUTE_ITEM
    
    # ===== 核心改进：直接在URL中包含日期参数，避免UI交互的不确定性 =====
    # 日期格式转换：支持 datetime 对象或字符串 '2026/4/3'
    if hasattr(target_date, 'strftime'):
        # datetime 对象
        date_str = target_date.strftime('%Y-%m-%d')
    elif isinstance(target_date, str):
        # 字符串格式：2026/4/3 -> 2026-04-03
        if '/' in target_date:
            parts = target_date.split('/')
            date_str = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        else:
            date_str = target_date.replace('/', '-')
    else:
        date_str = str(target_date)
    
    # 正确格式: ?spm=xxx#!/route?itemId=xxx&endDate=2026-04-03
    url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?itemId={item_id}&endDate={date_str}"
    log(f"访问单品洞察页面（含日期参数）: {url}")

    # ===== 先注册API拦截器，再访问页面 =====
    # 传递 item_id 用于过滤不匹配的API响应
    # 获取该商品的benchmark过滤阈值（配置化）
    min_valid_total = _get_min_valid_total_for_item(item_id)
    api_collector = _ItemAssetCollector(target_item_id=item_id, min_valid_total=min_valid_total)

    def api_response_handler(resp):
        # 只通过 on_response 处理，让它自动过滤和处理数据
        api_collector.on_response(resp)

    page.on('response', api_response_handler)

    try:
        # 访问页面（URL已包含日期参数）
        page.goto(url, wait_until="domcontentloaded", timeout=120000)

        # 验证页面是否正常加载（检测404/错误页）
        page_title = page.title() or ""
        page_content = page.content() or ""
        if "404" in page_title or "not found" in page_title.lower() or "找不到" in page_content:
            log("⚠️ 检测到页面404，尝试备用URL格式...")
            # 备用URL：不带spm参数的旧格式
            fallback_url = f"https://dmp.taobao.com/index_new.html{Config.DMP_ROUTE_ITEM}?itemId={item_id}"
            log(f"访问备用URL: {fallback_url}")
            page.goto(fallback_url, wait_until="domcontentloaded", timeout=120000)

        # 等待数据渲染（确保API已返回）
        log("等待数据渲染...")
        time.sleep(5)
        # [优化] 合并重复日志：原代码"页面加载完成，等待数据渲染..."与上方重复，删除
        # 反检测：正态分布延迟替代均匀随机
        if HAS_ANTI_DETECT:
            delay = human_delay_normal(3, 0.8, 1.5, 5)
            log(f"正态分布延迟 {delay:.1f}秒")
        else:
            time.sleep(random.uniform(2, 4))

        # 截图保存
        screenshot_path = os.path.join(debug_dir, f"item_{item_id}_initial.png")
        page.screenshot(path=screenshot_path, full_page=True)
        log(f"已保存初始页面截图: {screenshot_path}")

        # 滚动到单品资产分析区域
        log("滚动到单品资产分析区域...")
        try:
            # 反检测：模拟人类滚动行为
            if HAS_ANTI_DETECT:
                human_scroll(page, distance=500, duration=1.0)
            else:
                # 尝试找到资产分析区域并滚动
                page.evaluate("""() => {
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        if (el.textContent && el.textContent.includes('单品资产分析')) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            return true;
                        }
                    }
                    // 如果没找到，滚动到页面中部
                    window.scrollTo(0, document.body.scrollHeight * 0.5);
                    return false;
                }""")
            if HAS_ANTI_DETECT:
                human_delay(0.5, 1.0)
            else:
                time.sleep(1)  # 加速：2秒→1秒
        except Exception as e:
            log(f"滚动页面失败: {e}")

        # ===== Phase 1: 早期数据检查 + Fallback触发 =====
        # 注意：collector在整个过程中保持活跃，新的API响应会不断更新其内部assets
        
        # ========== 优化: 延长等待时间让SPA有更多渲染机会 ==========
        # 问题：原5秒等待对于某些SPA可能不够，尤其是达摩盘这种重型前端框架
        # 方案：分阶段等待，期间持续检测collector是否有数据
        log("等待API响应（URL已包含日期参数，分阶段检测）...")
        
        early_data = None
        max_wait = 12  # 最多等12秒
        waited = 0
        interval = 2   # 每2秒检查一次
        
        while waited < max_wait:
            time.sleep(interval)
            waited += interval
            
            # 检查是否有数据
            check_data = api_collector.get_data()
            if check_data and check_data.get('zichan_zongliang', 0) > 0:
                early_data = check_data
                log(f"✅ 第{waited}秒检测到API数据: 总量={early_data.get('zichan_zongliang', 0):,}")
                break
            else:
                log(f"  [{waited}s] 暂无数据，继续等待... (已拦截{api_collector.captured_count}次)")
        
        if early_data is None:
            log(f"⚠️ {max_wait}秒内未捕获到有效API数据，尝试备用方案...")

        # ===== 历史数据合理性校验（2026-05-18修复T-1数据回填未完成问题）=====
        if early_data and early_data.get('zichan_zongliang'):
            current_total = early_data.get('zichan_zongliang', 0)
            # 从CSV读取该商品的前一天数据进行对比
            prev_date = (target_date - timedelta(days=1)).strftime('%Y/%m/%d')
            prev_total = _get_prev_day_total(item_id, prev_date, DATA_FILE)
            if prev_total and prev_total > 0:
                ratio = current_total / prev_total
                if ratio < 0.20:  # 跌幅超过80%，疑似T-1数据回填未完成或SPA参数未生效
                    log(f"⚠️ 数据异常：{current_total:,} / 前日{prev_total:,} = {ratio:.1%}，触发日期选择器")
                    early_data = None  # 废弃当前数据，强制走Fallback
                else:
                    log(f"✅ API早期数据已获取: {early_data}")
            else:
                log(f"✅ API早期数据已获取: {early_data}")
        else:
            log("⚠️ 未捕获到API数据，尝试备用方案：手动选择日期")
            # 备用方案：如果URL日期参数没生效，尝试手动选择
            selected_date = select_date_smart_v2(page, target_date, fallback_date)
            if selected_date:
                log(f"手动选择日期成功: {selected_date}")
                
                # ========== 优化: Fallback后智能等待 ==========
                # 手动选择日期后，SPA需要时间重新请求数据并渲染
                fallback_wait = 0
                fallback_max = 10
                while fallback_wait < fallback_max:
                    time.sleep(2)
                    fallback_wait += 2
                    early_data = api_collector.get_data()
                    if early_data and early_data.get('zichan_zongliang', 0) > 0:
                        log(f"✅ Fallback后第{fallback_wait}秒检测到数据: {early_data.get('zichan_zongliang', 0):,}")
                        break
                    log(f"  Fallback后第{fallback_wait}秒，暂无数据... (已拦截{api_collector.captured_count}次)")
                
                if early_data and early_data.get('zichan_zongliang', 0) > 0:
                    log(f"✅ 备用方案成功，API数据: {early_data}")
                else:
                    log("⚠️ 备用方案仍未获取到有效数据，继续轮询...")
            else:
                log(f"❌ 商品 {item_id} 日期选择失败")

        # ========== 优化Phase 2: 增加轮询次数和API检查频率 ==========
        # ===== Phase 2: 数据稳定轮询 + API交叉验证 =====
        # 在此期间API拦截器保持活跃，可能捕获到更准确的数据
        log("等待数据刷新（轮询检测模式 + API交叉验证）...")
        prev_snapshot = None
        stable_count = 0
        data_refreshed = False
        max_attempts = 12  # ========== 优化: 增加到12次(24秒)，给SPA更多渲染时间 ==========
        
        # 从配置读取延迟参数
        anti_detect_cfg = CONFIG.get('anti_detect', {})
        delay_min = anti_detect_cfg.get('data_refresh_delay_min', 1.5)
        delay_max = anti_detect_cfg.get('data_refresh_delay_max', 2.5)

        for wait_attempt in range(max_attempts):
            # 反检测：随机延迟替代固定2秒
            if HAS_ANTI_DETECT:
                human_delay(delay_min, delay_max)
            else:
                time.sleep(random.uniform(delay_min, delay_max))
            current_snapshot = page.evaluate("""() => {
                const nums = [];
                document.querySelectorAll('.font-tahoma, strong').forEach(el => {
                    const v = (el.innerText||'').trim().replace(/,/g,'');
                    if(/^\\d{4,}$/.test(v)) nums.push(v);
                });
                return nums.join(',');
            }""")
            
            # ========== 优化: 每轮都检查API数据（不减半） ==========
            fresh_api = api_collector.get_data()
            if fresh_api and fresh_api.get('zichan_zongliang', 0) > 0:
                fresh_total = fresh_api.get('zichan_zongliang', 0)
                early_total = early_data.get('zichan_zongliang', 0) if early_data else 0
                if fresh_total > early_total:
                    early_data = fresh_api
                    log(f"  [API交叉验证] 捕获到更新的API数据（总量={fresh_total:,}）")

            if prev_snapshot is None:
                log(f"  记录基准数据快照（尝试{wait_attempt+1}/{max_attempts}）")
            elif current_snapshot == prev_snapshot:
                stable_count += 1
                log(f"  数据稳定 {stable_count}/2（尝试{wait_attempt+1}/{max_attempts}）")
                if stable_count >= 2:  # 连续3次一致（基准+2次确认）
                    data_refreshed = True
                    log("  数据已确认稳定")
                    break
            else:
                if stable_count > 0:
                    log(f"  数据发生变化，稳定计数重置（尝试{wait_attempt+1}/{max_attempts}）")
                else:
                    log(f"  数据发生变化（尝试{wait_attempt+1}/{max_attempts}）")
                stable_count = 0
            prev_snapshot = current_snapshot

        if not data_refreshed and prev_snapshot:
            log("⚠️ 警告：数据在24秒内未稳定，可能日期选择未生效或数据仍在加载")

        # ===== Phase 3: 注销拦截器，获取最终数据 =====
        try:
            page.remove_listener('response', api_response_handler)
        except Exception:
            pass

        # 截图保存
        screenshot_path = os.path.join(debug_dir, f"item_{item_id}_final.png")
        page.screenshot(path=screenshot_path, full_page=True)
        log(f"已保存最终页面截图: {screenshot_path}")

        # 取early_data和收集器最终数据中较好的一个
        final_data = api_collector.get_data()
        early_total = early_data.get('zichan_zongliang', 0) if early_data else 0
        final_total = final_data.get('zichan_zongliang', 0) if final_data else 0
        
        if final_total > early_total:
            api_data = final_data
            log(f"[DEBUG] 使用最终收集数据（总量={final_total:,} > 早期{early_total:,}）")
        else:
            api_data = early_data or final_data
            log(f"[DEBUG] 使用早期数据（总量={early_total:,}），api_data = {api_data}")
        
        # 检查数据有效性
        if api_data and api_data.get('zichan_zongliang', 0) <= 0:
            log(f"[DEBUG] 有效数据检查失败，api_data = {api_data}")
            api_data = None

        # 严格检查数据有效性（纯API方案）
        data = None
        if api_data and api_data.get('zichan_zongliang', 0) > 0:
            api_zongliang = api_data.get('zichan_zongliang', 0)
            if api_zongliang < 100000:
                log(f"⚠️ API数据异常（资产总量={api_zongliang:,} 太小），记录警告")
            data = api_data
            log(f"API拦截方案成功: {data}")

        # API拦截失败，直接返回None
        if data is None:
            log("API拦截未获取到有效数据，跳过该商品")
            return None

        # 如果提取失败，尝试AI自动修复
        if not data or all(v == 0 for v in data.values()):
            log(f"商品 {item_id} 数据提取失败，尝试AI自动修复...")

            if HAS_SELECTOR_ENGINE:
                ai_fix = ai_analyze_and_fix_item_extraction(page, debug_dir)
                if ai_fix:
                    log("AI修复建议已保存到 debug 目录，人工介入处理")

            # 如果仍然失败，记录错误但继续
            if not data or all(v == 0 for v in data.values()):
                log(f"商品 {item_id} 数据提取失败，已尝试AI修复但仍无数据")
                # 保存HTML片段供后续分析
                html_path = os.path.join(debug_dir, f"item_{item_id}_failed.html")
                try:
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    log(f"已保存失败页面HTML: {html_path}")
                except Exception:
                    pass
                return None

        if data:
            # 检查数据完整性
            if data.get('_integrity_check') == 'zichan_too_small':
                log(f"商品 {item_id} 数据完整性异常（资产总量小于子字段），跳过写入")
                return None
            data['item_id'] = item_id
            # selected_date在URL参数化方案中未定义，使用target_date作为默认值
            # 格式化日期为字符串
            if hasattr(target_date, 'strftime'):
                date_str = target_date.strftime('%Y/%m/%d')
            else:
                date_str = str(target_date)
            data['date'] = date_str
            log(f"商品 {item_id} 数据提取成功: {data}")
            return data
        else:
            log(f"商品 {item_id} 数据提取失败")
            return None

    except Exception as e:
        log(f"抓取商品 {item_id} 失败: {e}")
        return None


def ai_analyze_and_fix_item_extraction(page, debug_dir):
    """AI分析单品洞察页面，修复提取逻辑

    Returns:
        dict: 包含修复建议的字典，如有建议返回 {'custom_js': '...'}
    """
    try:
        # 获取页面HTML片段（资产卡片区域）
        html_snippet = page.evaluate("""() => {
            // 查找资产卡片区域
            const cards = document.querySelectorAll("[class*='aoK']");
            if (cards.length > 0) {
                // 返回前3个卡片的outerHTML
                let result = '';
                for (let i = 0; i < Math.min(3, cards.length); i++) {
                    result += '=== CARD ' + i + ' ===\\n' + cards[i].outerHTML.substring(0, 2000) + '\\n\\n';
                }
                return result;
            }
            // 如果没找到aoK，尝试查找其他可能的元素
            const assetArea = document.querySelector('.dKqGwkoRaoK, .dKqGwkoRade, [class*="asset"], [class*="card"]');
            if (assetArea) {
                return assetArea.outerHTML.substring(0, 3000);
            }
            return '';
        }""")

        if not html_snippet:
            log("AI分析失败：无法获取页面HTML片段")
            return None

        # 保存HTML片段
        html_path = os.path.join(debug_dir, "ai_analysis_snippet.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_snippet)
        log(f"AI分析HTML已保存: {html_path}")

        # 调用AI分析
        ai_agent = AIAgent()
        suggestions = ai_agent.analyze_item_selectors(html_snippet)

        if suggestions and 'error' not in suggestions:
            # 记录AI修复
            log(f"AI修复建议: {suggestions}")

            # 保存修复记录
            memory_file = os.path.join(debug_dir, "ai_fixes_log.txt")
            with open(memory_file, 'a', encoding='utf-8') as f:
                f.write(f"\\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\\n")
                f.write(f"HTML片段: {html_snippet[:500]}...\\n")
                f.write(f"AI建议: {suggestions}\\n")

            return suggestions
        else:
            log(f"AI分析失败: {suggestions.get('error', '未知错误')}")
            return None

    except Exception as e:
        log(f"AI分析过程出错: {e}")
        return None


def _find_date_trigger_multi(page, timeout=5000):
    """通过多种策略查找日期选择器触发元素，任一匹配即可
    
    策略优先级：.mx-trigger（真正的触发器）> 模糊class > 文本匹配
    
    Returns:
        tuple: (element, strategy_name) 成功找到返回(element, strategy_name)，失败返回(None, None)
    """
    strategies = [
        # 策略1（最高优先）：.mxgc-calendar-datepicker 内的 .mx-trigger — 真正的触发器元素
        {
            'name': 'exact-mxgc-trigger',
            'locator': page.locator(".mxgc-calendar-datepicker .mx-trigger").first,
            'filter': lambda el: el.is_visible()
        },
        # 策略2：模糊class匹配 [class*='calendar'] [class*='trigger']
        {
            'name': 'class-fuzzy-calendar-trigger',
            'locator': page.locator("[class*='calendar'] [class*='trigger']").first,
            'filter': lambda el: el.is_visible()
        },
        # 策略3：文本包含"昨日"（可能是显示文本，需配合其他策略）
        {
            'name': 'text-yesterday',
            'locator': page.locator("div:has-text('昨日')").first,
            'filter': lambda el: el.is_visible() and '昨日' in (el.text_content() or '')
        },
        # 策略4：文本包含日期格式 2026-xx-xx
        {
            'name': 'text-date-format',
            'locator': page.locator("div:has-text('2026-')").first,
            'filter': lambda el: el.is_visible() and '2026-' in (el.text_content() or '')
        },
    ]
    
    for strategy in strategies:
        try:
            el = strategy['locator']
            if el and strategy['filter'](el):
                log(f"  [_find_date_trigger_multi] [{strategy['name']}] 找到日期选择器")
                return el, strategy['name']
        except Exception:
            continue
    
    log("  [_find_date_trigger_multi] 所有策略都未能找到日期选择器")
    return None, None


def select_date_smart_v2(page, target_date, fallback_date):
    """智能日期选择V2 - 修复：确保点击的是日期选择器而非其他下拉框
    
    关键区别：
    - 同行对比选择器：包含"同行同层"文本
    - 日期选择器：包含日期格式如"2026-03-23"
    
    Returns:
        str: 选中的日期字符串（2026/3/26格式），失败返回None
    """
    # 确定debug目录
    debug_dir = Config.DEBUG_DIR if USING_COMMON else DEBUG_DIR
    
    target_str = format_date_for_csv(target_date)
    fallback_str = format_date_for_csv(fallback_date)
    
    log(f"尝试选择日期，目标: {target_str}, 备选: {fallback_str}")

    try:
        # 等待页面完全稳定
        log("等待页面稳定...")
        if HAS_ANTI_DETECT:
            human_delay(0.8, 1.5)
        else:
            time.sleep(1)

        # 滚动到页面顶部，确保日期选择器可见
        log("滚动到页面顶部...")
        page.evaluate("() => { window.scrollTo(0, 0); }")
        if HAS_ANTI_DETECT:
            human_delay(0.5, 1.0)
        else:
            time.sleep(1)

        # === 关闭可能的弹窗/对话框（避免遮挡日期选择器）===
        try:
            page.evaluate("""() => {
                // 关闭达摩盘新功能提示弹窗（wrapper_dlg_632 等）
                const dialogs = document.querySelectorAll('[id^="wrapper_dlg_"][data-daynamic-view*="dialog"]');
                dialogs.forEach(d => {
                    // 尝试找关闭按钮
                    const closeBtn = d.querySelector('.close-btn, [class*="close"], .mx-dialog-close');
                    if (closeBtn) closeBtn.click();
                });
                
                // 强制隐藏所有遮罩层对话框
                const overlays = document.querySelectorAll('[class*="mask"], [class*="overlay"]');
                overlays.forEach(o => {
                    if (o.style) o.style.display = 'none';
                });
                
                // 直接隐藏已知遮挡元素
                const blockingDivs = document.querySelectorAll('div[id^="wrapper_dlg_"]');
                blockingDivs.forEach(d => { if (d.style) d.style.display = 'none'; });
            }""")
            log("已尝试关闭可能遮挡的弹窗")
            time.sleep(1)
        except Exception as e:
            log(f"关闭弹窗时出错（非关键）: {e}")

        # 点击日期选择器 - 关键：必须点击包含日期格式的元素
        log("点击日期选择器...")
        
        clicked = False
        
        # 方法1：多路径fallback查找日期选择器触发元素
        try:
            log("尝试通过多路径fallback查找日期选择器...")
            date_trigger, trigger_strategy = _find_date_trigger_multi(page)
            
            if date_trigger:
                try:
                    date_trigger.scroll_into_view_if_needed()
                    time.sleep(0.3)
                    date_trigger.click()
                    text = date_trigger.text_content()
                    log(f"方法1成功：通过 [{trigger_strategy}] 点击日期选择器元素 - {text}")
                    clicked = True
                    if HAS_ANTI_DETECT:
                        human_delay_normal(1.5, 0.5, 0.8, 2.5)
                    else:
                        time.sleep(random.uniform(1, 3))
                except Exception as click_err:
                    log(f"  点击日期选择器失败: {click_err}")
            else:
                log("方法1失败: 未能找到日期选择器")
        except Exception as e:
            log(f"方法1失败: {e}")
        
        # 方法2：通过文本内容查找（支持"昨日"和日期格式）
        if not clicked:
            try:
                date_elements = page.locator("text=/昨日|\\d{4}-\\d{2}-\\d{2}/").all()
                log(f"方法2找到 {len(date_elements)} 个文本匹配元素")
                
                for i, el in enumerate(date_elements):
                    try:
                        text = el.text_content()
                        if text and (re.match(r'^\d{4}-\d{2}-\d{2}$', text.strip()) or text.strip() == '昨日'):
                            el.scroll_into_view_if_needed()
                            time.sleep(0.3)
                            el.click()
                            log(f"方法2成功：点击日期元素 - {text}")
                            clicked = True
                            if HAS_ANTI_DETECT:
                                human_delay_normal(1.5, 0.5, 0.8, 2.5)
                            else:
                                time.sleep(random.uniform(1, 3))
                            break
                    except Exception:
                        continue
            except Exception as e:
                log(f"方法2失败: {e}")
        
        # 方法3：JS 精确点击（.mxgc-calendar-datepicker 内的 .mx-trigger）
        if not clicked:
            js_result = page.evaluate("""() => {
                // 正确策略：找到 .mxgc-calendar-datepicker 容器，然后点击里面的 .mx-trigger
                const datePicker = document.querySelector('.mxgc-calendar-datepicker');
                if (!datePicker) {
                    return {success: false, reason: 'no-mxgc-calendar-datepicker'};
                }
                
                const trigger = datePicker.querySelector('.mx-trigger');
                if (!trigger) {
                    return {success: false, reason: 'no-trigger-in-datepicker'};
                }
                
                // 点击触发器
                trigger.click();
                trigger.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                trigger.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                trigger.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                
                return {
                    success: true,
                    method: 'datepicker-trigger-click',
                    triggerClass: trigger.className,
                    triggerId: trigger.id,
                    parentClass: datePicker.className
                };
            }""")
            log(f"方法2结果: {js_result}")
            if js_result and js_result.get('success'):
                clicked = True
                if HAS_ANTI_DETECT:
                    human_delay_normal(1.5, 0.5, 0.8, 2.5)
                else:
                    time.sleep(random.uniform(1, 3))
        
        if not clicked:
            log("所有点击方法都失败")
            return None

        # 等待日历弹出 — 使用 Playwright 原生等待
        log("等待日历弹出...")
        calendar_visible = False

        # 首次等待 Playwright 原生 selector
        try:
            page.wait_for_selector('.mx-output-bottom.mx-output-open', timeout=8000)
            calendar_visible = True
            log("日历已成功弹出")
        except Exception:
            log("警告：日历未在8秒内弹出，开始轮询检测...")

        # 轮询检测：最多等10秒（10次 x 1秒）
        if not calendar_visible:
            for i in range(10):
                has_calendar = page.evaluate("""() => {
                    const popup = document.querySelector('.mx-output-bottom');
                    return popup && popup.classList.contains('mx-output-open');
                }""")
                if has_calendar:
                    calendar_visible = True
                    log(f"日历已弹出（轮询检测到，共等待{i+1}秒）")
                    break
                time.sleep(1)
            if not calendar_visible:
                log(f"警告：日历仍未弹出（已等待{(i+1) if not calendar_visible else 0}秒），保存截图并返回失败")

            debug_path = os.path.join(debug_dir, "calendar_not_visible.png")
            page.screenshot(path=debug_path, full_page=True)
            log(f"已保存调试截图: {debug_path}")
            return None

        # 先尝试选择目标日期
        log(f"尝试选择目标日期: {target_str}")
        if try_select_date_v2(page, target_date):
            log(f"成功选择目标日期: {target_str}")
            return target_str

        # 目标日期不可选，尝试备选日期
        log(f"目标日期不可用，尝试备选日期: {fallback_str}")
        if try_select_date_v2(page, fallback_date):
            log(f"成功选择备选日期: {fallback_str}")
            return fallback_str

        log("目标日期和备选日期都不可用")
        return None
        
    except Exception as e:
        log(f"日期选择出错: {e}")
        import traceback
        log(traceback.format_exc())
        return None


def try_select_date_v2(page, target_date):
    """尝试选择指定日期 - mxgc日历组件专用版

    关键发现：
    1. 日历弹窗class是 'mx-output-bottom mx-output-open'
    2. 弹窗在 body 最后面渲染，不在 .mxgc-calendar-datepicker 内
    3. 年月导航和日期选择都在弹窗内

    Returns:
        bool: 是否选择成功
    """
    try:
        year = target_date.year
        month = target_date.month
        day = target_date.day

        log(f"查找日期: {year}-{month:02d}-{day:02d}")

        # 先保存调试截图
        debug_dir = Config.DEBUG_DIR if USING_COMMON else DEBUG_DIR
        debug_screenshot = os.path.join(debug_dir, f"date_picker_debug_{year}{month:02d}{day:02d}.png")
        page.screenshot(path=debug_screenshot, full_page=False)
        log(f"已保存日期选择器调试截图: {debug_screenshot}")

        # ========== 步骤1：确保日历弹窗已打开 ==========
        # 检查日历弹窗是否可见
        calendar_open = page.evaluate("""() => {
            const popup = document.querySelector('.mx-output-bottom');
            return popup ? {
                visible: popup.classList.contains('mx-output-open'),
                className: popup.className,
                hasNavButtons: popup.querySelectorAll('button').length > 0
            } : null;
        }""")
        
        log(f"日历弹窗状态: {calendar_open}")
        
        if not calendar_open or not calendar_open.get('visible'):
            log("日历弹窗未打开，尝试再次点击触发器...")
            page.evaluate("""() => {
                const datePicker = document.querySelector('.mxgc-calendar-datepicker');
                if (datePicker) {
                    const trigger = datePicker.querySelector('.mx-trigger');
                    if (trigger) trigger.click();
                }
            }""")
            page.wait_for_timeout(2000)

        # ========== 步骤2：获取当前月份并导航 ==========
        # 修复（2026-06-02 MEMO_2026-06-02.md）：用 DMP 真实 class .dKqGwkfJca 读月份
        # 修复：用 span.dKqGwkfJbY 作为月导航（0=上月 1=下月），不再用 button
        month_info = page.evaluate(r"""() => {
            const popup = document.querySelector('.mx-output-bottom');
            if (!popup) return null;
            // 真实 DMP 月份标题 class: dKqGwkfJca
            const titleEl = popup.querySelector('.dKqGwkfJca');
            if (!titleEl) return null;
            const m = (titleEl.textContent || '').match(/(\d{4})年(\d{1,2})月/);
            return {
                year: m ? parseInt(m[1]) : null,
                month: m ? parseInt(m[2]) : null,
                title: (titleEl.textContent || '').trim()
            };
        }""")

        log(f"月份信息: {month_info}")

        if not month_info or not month_info.get('year'):
            log("无法获取日历月份信息")
            return False

        months_diff = (year - month_info['year']) * 12 + (month - month_info['month'])
        if months_diff != 0:
            log(f"需要切换 {abs(months_diff)} 个月 {'向后' if months_diff > 0 else '向前'}")

            for i in range(abs(months_diff)):
                nav_ok = page.evaluate(f"""() => {{
                    const popup = document.querySelector('.mx-output-bottom');
                    if (!popup) return false;
                    // 真实 DMP 月导航 class: dKqGwkfJbY (按 DOM 顺序: 0=上月, 1=下月)
                    const navs = popup.querySelectorAll('span.dKqGwkfJbY');
                    if (navs.length < 2) return false;
                    const target = {months_diff} > 0 ? navs[1] : navs[0];
                    target.click();
                    return true;
                }}""")
                if nav_ok:
                    page.wait_for_timeout(800)
                else:
                    log(f"月导航第 {i+1}/{abs(months_diff)} 步失败 → BUG: month nav 阻塞")
                    return False

        # ========== 步骤3：选择日期 ==========
        # 修复（2026-06-02 MEMO_2026-06-02.md）：用 span.dKqGwkfJcd + title 属性定位
        # 移除 span-click fallback（Codex 注释 line 1487 BUG TRIGGER）
        page.wait_for_timeout(800)
        target_iso = f"{year:04d}-{month:02d}-{day:02d}"
        select_result = page.evaluate(f"""() => {{
            const popup = document.querySelector('.mx-output-bottom');
            if (!popup) return {{ success: false, reason: 'no-popup' }};

            // 真实 DMP 日期格: span.dKqGwkfJcd, 定位靠 title 属性
            // disabled 标识: class 含 dKqGwkfJcf
            const cells = popup.querySelectorAll('span.dKqGwkfJcd');
            for (const cell of cells) {{
                const cls = (cell.className || '').trim();
                if (cls.includes('dKqGwkfJcf')) continue;  // 跳过 disabled
                if (cell.getAttribute('title') === '{target_iso}') {{
                    cell.click();
                    return {{ success: true, method: 'cell-click', title: '{target_iso}', className: cls }};
                }}
            }}

            // 诊断：列出所有 cell
            const sample = Array.from(cells).slice(0, 5).map(c => ({{
                text: (c.textContent || '').trim(),
                title: c.getAttribute('title') || ''
            }}));
            return {{ success: false, reason: 'day-not-found', targetDay: {day}, targetTitle: '{target_iso}', total: cells.length, sample }};
        }}""")

        log(f"日期选择结果: {select_result}")

        if select_result and select_result.get('success'):
            log(f"成功选择 {day} 日 (title={select_result.get('title')})")
            page.wait_for_timeout(1500)
            return True
        else:
            log(f"选择 {day} 日失败: {select_result}")
            return False

    except Exception as e:
        log(f"选择日期失败: {e}")
        import traceback
        log(traceback.format_exc())
        return False


# statusId → (字段名, 中文名)
_ITEM_STATUS_MAP = {
    0: ('zichan_zongliang', '资产总量'),
    8001: ('qian_zhongcao', '浅种草'),
    8002: ('shen_zhongcao', '深种草'),
    8003: ('shougou', '首购'),
    8004: ('fugou', '复购'),
    8005: ('liandai', '连带'),
}


def extract_item_data_by_dom(page):
    """从页面DOM中提取单品资产数据（备选方案）

    当API拦截失败时使用此方法直接从DOM提取数据

    Returns:
        dict: 包含资产数据的字典，失败返回None
    """
    try:
        # 执行JavaScript提取资产数据
        result = page.evaluate("""() => {
            const data = {};

            // 查找资产卡片区域
            const cardLabels = ['资产总量', '浅种草', '深种草', '首购', '复购', '连带'];
            const fieldMap = {
                '资产总量': 'zichan_zongliang',
                '浅种草': 'qian_zhongcao',
                '深种草': 'shen_zhongcao',
                '首购': 'shougou',
                '复购': 'fugou',
                '连带': 'liandai'
            };

            // 方法1：查找包含标签的容器，然后找相邻的数字
            const allElements = document.querySelectorAll('*');

            for (const label of cardLabels) {
                for (const el of allElements) {
                    if (el.textContent && el.textContent.includes(label)) {
                        // 找到了标签，查找相邻的数字
                        let sibling = el.nextElementSibling;
                        let count = 0;
                        while (sibling && count < 5) {
                            const text = sibling.textContent || '';
                            // 匹配数字（可能有逗号）
                            const match = text.match(/([\\d,]+)/);
                            if (match) {
                                const num = parseInt(match[1].replace(/,/g, ''), 10);
                                if (num >= 1000) {  // 资产数据通常大于1000
                                    data[fieldMap[label]] = num;
                                    break;
                                }
                            }
                            sibling = sibling.nextElementSibling;
                            count++;
                        }
                        if (data[fieldMap[label]]) break;
                    }
                }
            }

            // 方法2：备用 - 通过特定的class或结构查找
            if (Object.keys(data).length < 3) {
                const nums = [];
                // 尝试多种选择器
                const selectors = ['.font-tahoma', 'strong', '[class*="number"]', '[class*="num"]'];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => {
                        const v = (el.textContent || '').trim().replace(/,/g, '');
                        if (/^\\d{4,}$/.test(v)) {
                            nums.push(parseInt(v, 10));
                        }
                    });
                }
                // 按数值大小排序，假设最大的是资产总量
                nums.sort((a, b) => b - a);
                if (nums.length >= 6) {
                    data.zichan_zongliang = data.zichan_zongliang || nums[0];
                    data.qian_zhongcao = data.qian_zhongcao || nums[1];
                    data.shen_zhongcao = data.shen_zhongcao || nums[2];
                    data.shougou = data.shougou || nums[3];
                    data.fugou = data.fugou || nums[4];
                    data.liandai = data.liandai || nums[5];
                }
            }

            return {
                success: Object.keys(data).length >= 3,
                data: data,
                debug: {
                    extractedFields: Object.keys(data).length
                }
            };
        }""")

        if result and result.get('success'):
            log(f"[DOM提取] 成功提取 {result.get('debug', {}).get('extractedFields', 0)} 个字段")
            return result.get('data')
        else:
            log(f"[DOM提取] 失败，debug: {result.get('debug', {})}")
            return None
    except Exception as e:
        log(f"[DOM提取] 异常: {e}")
        return None


class _ItemAssetCollector:
    """通过API拦截收集单品资产数据"""

    def __init__(self, target_item_id=None, min_valid_total=None):
        """
        Args:
            target_item_id: 目标商品ID，只有包含此ID的API响应才被接受
            min_valid_total: 最小有效资产总量阈值（低于此值视为benchmark数据），默认20000
        """
        self.assets = {}
        self.all_urls = []  # 诊断：记录所有拦截到的URL
        self.target_item_id = str(target_item_id) if target_item_id else None
        self.captured_count = 0  # 统计捕获次数
        # 使用配置的阈值或默认20000
        self.min_valid_total = min_valid_total if min_valid_total is not None else 20000

    def on_response(self, resp):
        url = resp.url

        # 诊断：记录所有dmp相关API
        if 'dmp.taobao.com' in url and 'api' in url.lower():
            self.all_urls.append(url)
            # 只打印goods相关的API（减少日志噪音）
            if 'goods/view/overview/v2' in url:
                log(f"[API-诊断] 拦截到: {url[:150]}...")

        if 'goods/view/overview/v2' not in url:
            return

        # ========== 关键修复：跳过无效请求 ==========
        # 从诊断日志发现：
        # - 第一个请求 (subjectType=1&subjectId=): subjectId为空时返回错误数据
        # - 第二个请求 (&benchmarkId=xxx&subject): 返回正确数据
        # 过滤策略：跳过 subjectId 为空的请求
        has_empty_subject_id = 'subjectId=' in url and '&benchmarkId=' not in url
        if has_empty_subject_id:
            import re
            match = re.search(r'subjectId=([^&]*)', url)
            if match:
                subject_value = match.group(1)
                if subject_value == '' or subject_value is None:
                    log("[API-过滤] 跳过（subjectId为空）")
                    return
        # ========== 修复结束 ==========

        try:
            body = resp.json()
        except Exception:
            return
        data = body.get('data', {})
        items = data.get('list', [])

        self.captured_count += 1
        log(f"[API] 第{self.captured_count}次捕获 goods/view/overview/v2，{len(items)} 条数据")

        # 收集本次数据
        current_data = {}
        for item in items:
            status_id = item.get('statusId')
            if status_id in _ITEM_STATUS_MAP:
                field_key, field_name = _ITEM_STATUS_MAP[status_id]
                uv = item.get('uv', 0)
                current_data[field_key] = uv

        if not current_data:
            log("[API] 无有效数据")
            return

        # ========== 优化: 改进数据有效性判断（解决T+1数据延迟问题）==========
        #
        # 原始问题：API返回全0时被直接跳过，但实际上可能是因为：
        # 1. SPA还在初始化，还没发起真正的数据请求
        # 2. T+1数据还未生成
        #
        # 新策略：
        # - 记录所有API响应，不立即跳过
        # - 如果只有0数据，持续等待（让SPA有更多时间）
        # - 只有当有非零数据时才接受
        #
        # 计算总资产（用于判断数据质量）
        current_total = current_data.get('zichan_zongliang', 0)
        log(f"[API] 本次资产总量: {current_total:,}")

        # ========== 数据有效性验证（改进版）==========
        # 规则1：资产总量为0时，不立即跳过，而是记录下来让collector继续等待
        # 只有当子字段有数据时，才认为这是有效响应（即使是0，也可能是真实T+1延迟）
        sub_sum = sum([
            current_data.get('qian_zhongcao', 0),
            current_data.get('shen_zhongcao', 0),
            current_data.get('shougou', 0),
            current_data.get('fugou', 0),
            current_data.get('liandai', 0)
        ])
        
        if current_total == 0 and sub_sum == 0:
            # 全0数据：可能是SPA还没加载完，标记但不拒绝
            log("[API-注意] 全0数据，可能T+1未更新或SPA未加载完毕，记录但不拒绝")
            # 不return，继续让collector有机会接收后续数据
        
        # 规则2：资产总量小于阈值的通常是benchmark数据（除特定商品外）
        # 阈值可通过config/items.yaml中benchmark_filter.per_item为每个商品自定义
        elif current_total > 0 and current_total < self.min_valid_total:
            log(f"[API-过滤] 资产总量({current_total:,}) < {self.min_valid_total}，疑似benchmark数据，跳过")
            return
        
        # 规则3：验证数据内部一致性 - 子字段之和不应远超总资产
        elif current_total > 0 and sub_sum > current_total * 1.5:
            log(f"[API-过滤] 子字段之和({sub_sum:,}) > 总资产({current_total:,})*1.5，数据异常，跳过")
            return
        # ========== 数据有效性验证结束 ==========

        # 选择数据：如果当前数据比已保存的数据更大（更可能正确），则替换
        existing_total = self.assets.get('zichan_zongliang', 0) if self.assets else 0

        if not self.assets or current_total > existing_total:
            if self.assets:
                log(f"[API] 数据更好（{current_total:,} > {existing_total:,}），替换")
            else:
                log("[API] ✅ 使用本次数据")
            self.assets = current_data
            for item in items:
                status_id = item.get('statusId')
                if status_id in _ITEM_STATUS_MAP:
                    field_key, field_name = _ITEM_STATUS_MAP[status_id]
                    uv = item.get('uv', 0)
                    log(f"  {field_name}(statusId={status_id}): {uv:,}")
        else:
            log(f"[API] 已有更好数据（{existing_total:,} >= {current_total:,}），跳过")

    def get_data(self):
        return self.assets
    
    def diag_urls(self):
        return self.all_urls


def extract_item_data_by_api(page, item_id, target_date):
    """通过API拦截获取单品资产数据

    Args:
        page: Playwright页面对象（已经在单品洞察页面）
        item_id: 商品ID
        target_date: 目标日期（datetime对象或字符串 'YYYY/M/D' 格式）

    Returns:
        dict: 包含资产数据的字典，失败返回None
    """
    collector = _ItemAssetCollector(target_item_id=item_id)

    def response_handler(resp):
        collector.on_response(resp)

    page.on('response', response_handler)

    try:
        # 构造URL（带endDate参数）
        if isinstance(target_date, str):
            # 字符串格式 '2026/4/1' -> '2026-04-01'
            parts = target_date.split('/')
            date_str = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        else:
            date_str = target_date.strftime('%Y-%m-%d')

        spm = Config.DMP_SPM
        route = Config.DMP_ROUTE_ITEM
        url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?itemId={item_id}&endDate={date_str}"

        log(f"[API] 刷新页面: {url[:100]}...")
        # 使用 domcontentloaded 而不是 networkidle（SPA页面有长轮询，networkidle会超时）
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)  # 等待API响应（比原来多3秒，确保数据返回）

    except Exception as e:
        log(f"[API] 刷新页面失败: {e}")
    finally:
        try:
            page.remove_listener('response', response_handler)
        except Exception:
            pass

    data = collector.get_data()

    # 诊断：打印所有拦截到的API URL
    diag_urls = collector.diag_urls()
    log(f"[API-诊断] 本次共拦截到 {len(diag_urls)} 个DMP API:")
    for u in diag_urls:
        log(f"   {u[:150]}")

    if not data:
        log("[API] 未获取到数据")
        return None

    # ========== Date Sanity Check ==========
    # Bug 背景（2026-06-01 发现）：
    # date picker 月份切换失败时（"导航按钮点击失败"），span-click 备份点击的是
    # 当前可见月份里的"日"数字，但 SPA 内部 endDate 状态没真切到目标月。
    # 结果：URL endDate=2026-05-23 实际抓到 5/26 的数据（与 5/26 抓的完全相同）。
    #
    # 修复：抓完数据后读 SPA 当前显示的日期（date picker 触发器文本），
    # 跟目标日期对比，不一致 → return None 触发 run_items_fetch 的重试逻辑。
    try:
        expected = date_str  # 'YYYY-MM-DD' 格式
        expected_norm = expected.replace('-', '/')
        trigger = page.locator(".mxgc-calendar-datepicker .mx-trigger").first
        if trigger.count() > 0:
            trigger_text = (trigger.text_content() or '').strip()
            if expected in trigger_text or expected_norm in trigger_text:
                log(f"[API-Sanity] ✅ SPA 日期匹配: {trigger_text}")
            else:
                log(f"[API-Sanity] ❌ SPA 日期({trigger_text}) ≠ 目标({expected})，"
                    f"endDate 可能被忽略，数据作废触发重试")
                return None
        else:
            log("[API-Sanity] ⚠️ 找不到 date trigger 元素，跳过校验")
    except Exception as e:
        log(f"[API-Sanity] 校验异常（不阻塞主流程）: {e}")

    log(f"[API] 获取成功: {data}")
    return data


def extract_item_data(page):
    """从页面提取单品资产数据（多路径fallback版）
    
    核心改造（多路径fallback策略）：
    - 路径1：精确文本匹配（最准确）- 中文标签包含字段名
    - 路径2：模糊class匹配 - [class*="keyword"] 模糊定位
    - 路径3：备用方法 - 全局数字排序按位置分配
    
    每个字段提取时按优先级尝试，任意路径成功即停止并记录日志。

    Returns:
        dict: 包含资产数据的字典（含 _extract_path 记录各字段使用的路径）
    """
    data = {}
    extract_paths = {}  # 记录每个字段使用的提取路径

    try:
        # 首先滚动到"单品资产分析"区域
        page.evaluate("""() => {
            const elements = document.querySelectorAll('*');
            for (let el of elements) {
                if (el.textContent && el.textContent.includes('单品资产分析')) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    return true;
                }
            }
            return false;
        }""")
        time.sleep(random.uniform(0.5, 1))
        
        # ============================================================
        # 路径1：锚点定位法（认知/兴趣/购买/忠诚 唯一关键词）
        # 页面6个卡片布局：
        #   [单品资产总量] [浅种草(认知)] [深种草(兴趣)] [首购(购买)] [复购(忠诚)] [连带(忠诚右边)]
        # 前4个用唯一锚点词定位，单品保持文本匹配，连带用相对位置
        # ============================================================
        js_result = page.evaluate("""() => {
            const result = {};
            const resultPaths = {};

            // ============================================================
            // 锚点卡片法（2026-04-07）
            // DOM结构：
            //   - 每个卡片容器: div.dKqGwkpmaoK (大小270x210)
            //   - 锚点标签: span.mxgc-effects-icon + div.pa ("认知"类文本在x=736/1014/1292/1570)
            //   - 数字在卡片innerText中，如"1,154,057"
            // 策略：从卡片容器提取innerText → 用正则提取最大数字
            // ============================================================

            // 工具函数：从元素innerText提取最大数字
            function extractMaxNumber(el) {
                if (!el) return null;
                const text = (el.innerText || '').trim();
                // 匹配5位以上的数字（带或不带逗号）
                const matches = text.match(/(\\d{5,}[,\\d]*)/g);
                if (!matches) return null;
                let best = null;
                for (const m of matches) {
                    const v = parseInt(m.replace(/,/g, ''));
                    if (v > 0 && (!best || v > best)) best = v;
                }
                return best;
            }

            // 工具函数：找包含特定文本且在y=1100-1300范围内的卡片容器
            function findCardByAnchorKeyword(keyword) {
                const allEls = document.querySelectorAll('*');
                let bestCard = null;
                let bestDist = Infinity;

                for (const el of allEls) {
                    const text = (el.innerText || '').trim();
                    // 精确匹配锚点词（避免匹配到大容器）
                    if (!text.includes(keyword)) continue;

                    const lr = el.getBoundingClientRect();
                    if (lr.width === 0 || lr.height === 0) continue;
                    if (lr.top < 0 || lr.left < 0) continue;

                    // 锚点词必须在合理范围内（小元素）
                    if (lr.width > 100 || lr.height > 50) continue;

                    // 在y=1100-1300范围（卡片区域）
                    if (lr.top < 1100 || lr.top > 1300) continue;

                    // 取最近的
                    const dist = Math.abs(lr.top - 1181) + Math.abs(lr.left - 800);
                    if (dist < bestDist) {
                        bestDist = dist;
                        bestCard = el;
                    }
                }
                return bestCard;
            }

            // ---- 1. 单品资产总量 ----
            {
                // 从"单品资产总量"文本元素向上找到卡片容器
                const allEls = document.querySelectorAll('*');
                for (const el of allEls) {
                    const text = (el.innerText || '').trim();
                    if (text.includes('单品资产总量') || text === '单品资产') {
                        const lr = el.getBoundingClientRect();
                        if (lr.width > 10 && lr.height > 10 && lr.top > 1000) {
                            // 向上找卡片容器
                            let card = el;
                            while (card && card !== document.body) {
                                const cr = card.getBoundingClientRect();
                                if (cr.width >= 200 && cr.height >= 100) break;
                                card = card.parentElement;
                            }
                            if (card && card !== document.body) {
                                const num = extractMaxNumber(card);
                                if (num) {
                                    result.zichan_zongliang = num;
                                    resultPaths.zichan_zongliang = 'card:单品资产';
                                    console.log('[单品-锚点] 单品资产总量 =', num);
                                }
                            }
                            break;
                        }
                    }
                }
            }

            // ---- 2-5. 锚点定位：认知/兴趣/购买/忠诚 ----
            const anchorMap = {
                'qian_zhongcao': '认知',
                'shen_zhongcao': '兴趣',
                'shougou': '购买',
                'fugou': '忠诚'
            };

            for (const [field, keyword] of Object.entries(anchorMap)) {
                // 找锚点元素
                const anchorEl = findCardByAnchorKeyword(keyword);
                if (!anchorEl) {
                    console.warn('[单品-锚点] ⚠️ 未找到锚点:', keyword);
                    continue;
                }

                // 向上找卡片容器
                let card = anchorEl;
                while (card && card !== document.body) {
                    const cr = card.getBoundingClientRect();
                    // 卡片特征：宽度200-300，高度150-250
                    if (cr.width >= 200 && cr.width <= 350 &&
                        cr.height >= 150 && cr.height <= 300) {
                        break;
                    }
                    card = card.parentElement;
                }

                if (!card || card === document.body) {
                    console.warn('[单品-锚点] ⚠️ 锚点', keyword, '未找到卡片容器');
                    continue;
                }

                const num = extractMaxNumber(card);
                if (num) {
                    result[field] = num;
                    resultPaths[field] = 'anchor:' + keyword;
                    console.log('[单品-锚点]', field, '(', keyword, ') =', num,
                        'card rect:', JSON.stringify({
                            x: Math.round(card.getBoundingClientRect().left),
                            y: Math.round(card.getBoundingClientRect().top)
                        }));
                } else {
                    console.warn('[单品-锚点] ⚠️ 锚点', keyword, '卡片内未找到数字');
                }
            }

            // ---- 6. 连带：在忠诚卡片右边 ----
            {
                // 找"忠诚"锚点所在的卡片
                const loyaltyCard = findCardByAnchorKeyword('忠诚');
                if (loyaltyCard) {
                    let card = loyaltyCard;
                    while (card && card !== document.body) {
                        const cr = card.getBoundingClientRect();
                        if (cr.width >= 200 && cr.width <= 350 &&
                            cr.height >= 150 && cr.height <= 300) break;
                        card = card.parentElement;
                    }

                    if (card && card !== document.body) {
                        const loyaltyRect = card.getBoundingClientRect();
                        // 找忠诚右边最近的小卡片
                        let bestCard = null;
                        let bestDist = Infinity;

                        document.querySelectorAll('*').forEach(el => {
                            const cr = el.getBoundingClientRect();
                            if (cr.width < 150 || cr.width > 350) return;
                            if (cr.height < 100 || cr.height > 300) return;
                            if (cr.top < 1100 || cr.top > 1300) return;
                            // 必须在忠诚卡片右边
                            if (cr.left <= loyaltyRect.right - 30) return;
                            // 同一行
                            if (Math.abs(cr.top - loyaltyRect.top) > 80) return;
                            const dist = cr.left - loyaltyRect.right;
                            if (dist >= 0 && dist < bestDist) {
                                bestDist = dist;
                                bestCard = el;
                            }
                        });

                        if (bestCard) {
                            const num = extractMaxNumber(bestCard);
                            if (num) {
                                result.liandai = num;
                                resultPaths.liandai = 'pos:忠诚右边';
                                console.log('[单品-锚点] 连带(忠诚右边) =', num, 'dist:', Math.round(bestDist));
                            }
                        } else {
                            console.warn('[单品-锚点] ⚠️ 未在忠诚右边找到连带卡片');
                        }
                    }
                }
            }

            // ---- 数据完整性校验 ----
            if (result.zichan_zongliang) {
                const subFields = ['qian_zhongcao','shen_zhongcao','shougou','fugou','liandai'];
                const maxSub = Math.max(...subFields.map(k => result[k]||0));
                if (result.zichan_zongliang < maxSub) {
                    console.warn('[单品-锚点] ⚠️ 数据异常: 资产总量('+result.zichan_zongliang+') < 子字段最大值('+maxSub+')');
                    result._integrity_check = 'zichan_too_small';
                }
                // 检测复购/连带是否异常等于首购
                if (result.fugou && result.shougou && result.fugou === result.shougou) {
                    console.warn('[单品-锚点] ⚠️ 复购('+result.fugou+') = 首购('+result.shougou+')');
                    result._integrity_check = 'fugou_equals_shougou';
                }
                if (result.liandai && result.shougou && result.liandai === result.shougou) {
                    console.warn('[单品-锚点] ⚠️ 连带('+result.liandai+') = 首购('+result.shougou+')');
                    result._integrity_check = 'liandai_equals_shougou';
                }
            }

            result._paths = resultPaths;
            console.log('[单品-锚点] 最终结果:', JSON.stringify(result));
            return result;
        }""")

        log(f"智能扫描提取结果: {js_result}")

        if js_result and any(k not in ['_paths', '_integrity_check'] and js_result.get(k, 0) > 0 for k in ['zichan_zongliang', 'qian_zhongcao', 'shen_zhongcao', 'shougou', 'fugou', 'liandai']):
            data['zichan_zongliang'] = js_result.get('zichan_zongliang', 0)
            data['qian_zhongcao'] = js_result.get('qian_zhongcao', 0)
            data['shen_zhongcao'] = js_result.get('shen_zhongcao', 0)
            data['shougou'] = js_result.get('shougou', 0)
            data['fugou'] = js_result.get('fugou', 0)
            data['liandai'] = js_result.get('liandai', 0)
            
            # 记录各字段的提取路径
            paths = js_result.get('_paths', {})
            for field in ['zichan_zongliang', 'qian_zhongcao', 'shen_zhongcao', 'shougou', 'fugou', 'liandai']:
                extract_paths[field] = paths.get(field, 'text-match')
            
            # 传递数据完整性标志
            if js_result.get('_integrity_check'):
                data['_integrity_check'] = js_result['_integrity_check']
        else:
            log("智能扫描未能提取到足够数据，尝试备用方法...")
            
        # ============================================================
        # 路径3：备用方法（class引导的字段区分 + 智能数字匹配）
        # ============================================================
        if not data or data.get('zichan_zongliang', 0) == 0:
            log("主方法失败，尝试备用方法（class引导字段区分）...")
            js_backup = page.evaluate("""() => {
                const result = {};
                const resultPaths = {};
                
                // 字段class关键词
                const fieldClasses = {
                    'zichan_zongliang': ['total', 'zongliang', 'asset', 'sum'],
                    'qian_zhongcao': ['qian', 'zhongcao', 'light'],
                    'shen_zhongcao': ['shen', 'zhongcao', 'deep'],
                    'shougou': ['shougou', 'first'],
                    'fugou': ['fugou', 'repurchase'],
                    'liandai': ['liandai', 'bundle']
                };
                
                // 通过class尝试直接匹配各字段数字
                const assignedFields = new Set();
                
                for (const [fieldKey, keywords] of Object.entries(fieldClasses)) {
                    for (const kw of keywords) {
                        try {
                            const els = document.querySelectorAll(`[class*="${kw}"]`);
                            for (const el of els) {
                                const text = (el.innerText || '').trim();
                                if (/^\\d{5,}[,\\d]*$/.test(text.replace(/,/g, ''))) {
                                    const v = parseInt(text.replace(/,/g, ''));
                                    if (v > 0 && !assignedFields.has(fieldKey)) {
                                        result[fieldKey] = v;
                                        assignedFields.add(fieldKey);
                                        resultPaths[fieldKey] = 'backup-class:'+kw;
                                        console.log('[单品-backup] 通过class找到', fieldKey, '=', v, 'kw:', kw);
                                        break;
                                    }
                                }
                            }
                        } catch(e) {}
                        if (assignedFields.has(fieldKey)) break;
                    }
                }
                
                // 如果通过class只找到了部分字段，用智能匹配填充
                // 1. 限制数字收集范围：只在资产卡片区域内收集
                // 2. 增加数字范围过滤（100-10000000）
                // 3. 按字段预期范围匹配数字，而不是固定顺序分配
                
                // 首先找到资产卡片区域
                let assetCard = null;
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const text = (el.innerText || '');
                    if (text.includes('单品资产分析') || text.includes('资产总量')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 50) {
                            assetCard = el;
                            break;
                        }
                    }
                }
                
                // 如果没找到资产卡片，使用整个页面但限制范围
                if (!assetCard) {
                    // 尝试查找包含资产数据的容器
                    const containers = document.querySelectorAll('[class*="asset"], [class*="card"], [class*="item"]');
                    for (const container of containers) {
                        const text = (container.innerText || '');
                        if (text.includes('资产') && text.length < 500) {
                            assetCard = container;
                            break;
                        }
                    }
                }
                
                // 收集数字：只在资产卡片区域内
                const allNums = [];
                const searchRoot = assetCard || document.body;
                const maxRect = assetCard ? assetCard.getBoundingClientRect() : {left: 0, right: window.innerWidth, top: 0, bottom: window.innerHeight};
                
                searchRoot.querySelectorAll('.font-tahoma, strong, [class*="number"], [class*="value"]').forEach(el => {
                    const v = (el.innerText||'').trim().replace(/,/g,'');
                    if(/^\\d{4,}$/.test(v)) {
                        const num = parseInt(v);
                        // 数字范围过滤：100-10000000
                        if (num >= 100 && num <= 10000000) {
                            // 位置过滤：只收集在资产卡片区域内的数字
                            const rect = el.getBoundingClientRect();
                            if (rect.left >= maxRect.left - 50 && rect.right <= maxRect.right + 50 &&
                                rect.top >= maxRect.top - 50 && rect.bottom <= maxRect.bottom + 50) {
                                allNums.push(num);
                            }
                        }
                    }
                });
                
                // 去重并排序（降序）
                const uniqueNums = [...new Set(allNums)].sort((a,b) => b-a);
                
                console.log('[单品-backup] 收集到', uniqueNums.length, '个有效数字:', uniqueNums.slice(0, 10));
                
                // 按字段预期范围匹配数字
                // 预期范围：资产总量 > 浅种草 > 深种草 > 首购 > 复购/连带
                // 但实际数据中，深种草可能小于首购，复购和连带可能相近
                
                // 为每个未分配的字段寻找最合适的数字
                const fieldOrder = ['zichan_zongliang', 'qian_zhongcao', 'shen_zhongcao', 'shougou', 'fugou', 'liandai'];
                const usedNums = new Set();
                
                for (const field of fieldOrder) {
                    if (result[field]) continue; // 已经通过class找到的跳过
                    
                    // 根据字段预期范围选择数字
                    let bestNum = null;
                    let bestIdx = -1;
                    
                    for (let i = 0; i < uniqueNums.length; i++) {
                        if (usedNums.has(i)) continue;
                        
                        const num = uniqueNums[i];
                        
                        // 根据字段类型进行合理性检查
                        if (field === 'zichan_zongliang') {
                            // 资产总量应该是最大的
                            if (!bestNum || num > bestNum) {
                                bestNum = num;
                                bestIdx = i;
                            }
                        } else if (field === 'qian_zhongcao') {
                            // 浅种草应该小于资产总量
                            const total = result['zichan_zongliang'] || bestNum;
                            if (total && num < total) {
                                if (!bestNum || num > bestNum) {
                                    bestNum = num;
                                    bestIdx = i;
                                }
                            }
                        } else if (field === 'shen_zhongcao') {
                            // 深种草应该小于浅种草
                            const qian = result['qian_zhongcao'] || bestNum;
                            if (qian && num < qian) {
                                if (!bestNum || num > bestNum) {
                                    bestNum = num;
                                    bestIdx = i;
                                }
                            }
                        } else if (field === 'shougou') {
                            // 首购应该小于资产总量，通常小于深种草
                            const total = result['zichan_zongliang'];
                            const shen = result['shen_zhongcao'];
                            if (total && num < total) {
                                if (!bestNum || num > bestNum) {
                                    bestNum = num;
                                    bestIdx = i;
                                }
                            }
                        } else if (field === 'fugou') {
                            // 复购应该小于首购
                            const shougou = result['shougou'];
                            if (shougou && num < shougou) {
                                if (!bestNum || num > bestNum) {
                                    bestNum = num;
                                    bestIdx = i;
                                }
                            }
                        } else if (field === 'liandai') {
                            // 连带应该小于首购
                            const shougou = result['shougou'];
                            if (shougou && num < shougou) {
                                if (!bestNum || num > bestNum) {
                                    bestNum = num;
                                    bestIdx = i;
                                }
                            }
                        }
                    }
                    
                    if (bestNum && bestIdx >= 0) {
                        result[field] = bestNum;
                        usedNums.add(bestIdx);
                        resultPaths[field] = 'backup-smart:' + bestIdx;
                        console.log('[单品-backup] 智能匹配找到', field, '=', bestNum, 'idx:', bestIdx);
                    }
                }
                
                // 数据合理性校验
                if (result.zichan_zongliang) {
                    const subFields = ['qian_zhongcao','shen_zhongcao','shougou','fugou','liandai'];
                    const subSum = subFields.reduce((sum, k) => sum + (result[k]||0), 0);
                    
                    // 校验1：资产总量应 >= 子字段之和（允许10%误差）
                    if (subSum > result.zichan_zongliang * 1.1) {
                        console.warn('[单品-backup] ⚠️ 数据异常: 子字段之和('+subSum+') > 资产总量('+result.zichan_zongliang+')');
                        result._integrity_check = 'sub_sum_too_large';
                    }
                    
                    // 校验2：首购不应超过资产总量的50%
                    if (result.shougou && result.shougou > result.zichan_zongliang * 0.5) {
                        console.warn('[单品-backup] ⚠️ 数据异常: 首购('+result.shougou+') > 资产总量的50%('+result.zichan_zongliang*0.5+')');
                        result._integrity_check = 'shougou_too_large';
                    }
                    
                    // 校验3：复购不应超过首购
                    if (result.fugou && result.shougou && result.fugou > result.shougou) {
                        console.warn('[单品-backup] ⚠️ 数据异常: 复购('+result.fugou+') > 首购('+result.shougou+')');
                        result._integrity_check = 'fugou_larger_than_shougou';
                    }
                }
                
                result._paths = resultPaths;
                return result;
            }""")
            
            if js_backup and js_backup.get('zichan_zongliang', 0) > 0:
                data = js_backup
                paths = js_backup.get('_paths', {})
                for field in ['zichan_zongliang', 'qian_zhongcao', 'shen_zhongcao', 'shougou', 'fugou', 'liandai']:
                    extract_paths[field] = paths.get(field, 'backup-fallback')
                
                # 检查数据完整性标志
                if js_backup.get('_integrity_check'):
                    data['_integrity_check'] = js_backup['_integrity_check']
                
                log(f"备用方法提取: {data}")

    except Exception as e:
        log(f"提取单品数据失败: {e}")

    # 添加提取路径信息到返回数据
    if data:
        data['_extract_paths'] = extract_paths
        log(f"各字段提取路径: {extract_paths}")
    
    return data


# parse_number函数已在公共模块中定义，独立模式需要单独定义


# ============ 数据校验 ============
def validate_item_data(data):
    """校验单品数据的合理性，异常数据不写入
    
    Args:
        data: 包含单品资产数据的字典
    
    Returns:
        tuple: (is_valid: bool, reason: str)
    """
    if not data:
        return False, "数据为空"
    
    total = data.get('zichan_zongliang', 0)
    shougou = data.get('shougou', 0)
    qian = data.get('qian_zhongcao', 0)
    shen = data.get('shen_zhongcao', 0)
    
    # 资产总量为0
    if total <= 0:
        return False, "资产总量为0，数据未刷新"
    
    # 资产总量 < 首购（不合逻辑）
    if total < shougou:
        return False, f"资产总量({total}) < 首购({shougou})，数据异常"
    
    # 浅种草+深种草 > 资产总量*1.5
    if qian + shen > total * 1.5:
        return False, f"种草({qian}+{shen}={qian+shen}) > 资产总量({total})*1.5，异常"
    
    # 各层级数值应在合理范围内（正数且不过于悬殊）
    if shougou < 0 or shougou > total:
        return False, f"首购({shougou})超出合理范围"
    
    return True, "OK"


# ============ 断点续传缓存 ============

def _get_completed_cache_path():
    """获取已完成任务缓存文件路径"""
    data_file = Config.ITEM_DATA_FILE if USING_COMMON else DATA_FILE
    return str(Path(data_file).parent / 'completed_items.json')

def _load_completed_items():
    """从缓存加载已完成的(item_id, date)组合集合

    同时验证CSV中是否真正存在该数据，如果CSV中不存在则清理缓存
    """
    completed = set()
    cache_file = _get_completed_cache_path()

    if Path(cache_file).exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            # 同时加载CSV中的实际数据，用于验证缓存有效性
            csv_existing = set()
            if Path(DATA_FILE).exists():
                encoding = detect_encoding(DATA_FILE)
                with open(DATA_FILE, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        item_id = row.get('ID', '').strip()
                        date_str = row.get('时间', '').strip()
                        if item_id and date_str:
                            csv_existing.add((item_id, date_str))

            # 验证每个缓存记录是否在CSV中真实存在
            valid_cache = {}
            removed_count = 0
            for key in cache:
                parts = key.rsplit('_', 1)
                if len(parts) == 2:
                    item_id = parts[0]
                    date_str = parts[1].replace('-', '/')
                    if (item_id, date_str) in csv_existing:
                        completed.add((item_id, date_str))
                        valid_cache[key] = cache[key]
                    else:
                        removed_count += 1

            # 如果有无效缓存，清理并重写
            if removed_count > 0:
                log(f"清理了 {removed_count} 条无效缓存（CSV中已不存在）")
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(valid_cache, f, ensure_ascii=False, indent=2)

            log(f"从缓存加载了 {len(completed)} 条已完成记录（已验证CSV有效性）")
        except Exception as e:
            log(f"读取完成缓存失败: {e}")

    return completed


def _cleanup_completed_cache(cache, max_age_days=60):
    """清理 completed_items.json 中超过 max_age_days 的老旧记录

    同时检查 CSV 中对应记录是否真实存在——如果 CSV 里没有（被删除或未写入），
    也清理掉，避免"completed 缓存说已完成但 CSV 里没数据"的矛盾。
    """
    now = datetime.now()
    cutoff = now - timedelta(days=max_age_days)
    csv_file = Config.ITEM_DATA_FILE

    # 建立 CSV 中所有 item_id+日期 的集合
    csv_keys = set()
    if os.path.exists(csv_file):
        try:
            enc = detect_encoding(csv_file)
            with open(csv_file, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item = row.get('ID', '').strip()
                    date = row.get('时间', '').strip()
                    if item and date:
                        csv_keys.add(f"{item}_{date.replace('/', '-')}")
        except Exception:
            pass

    before = len(cache)
    cleaned_keys = []
    for key, info in list(cache.items()):
        completed_at_str = info.get('completed_at', '')
        try:
            completed_at = datetime.strptime(completed_at_str, '%Y-%m-%d %H:%M:%S')
            if completed_at < cutoff:
                cleaned_keys.append(key)
                continue
        except Exception:
            pass
        # CSV 中不存在该记录，说明数据从未真正写入，清理掉
        if key not in csv_keys:
            cleaned_keys.append(key)

    for key in cleaned_keys:
        del cache[key]

    after = len(cache)
    removed = before - after
    if removed > 0:
        log(f"🧹 completed缓存清理: {before}条 → {after}条，移除{removed}条")


def _mark_completed(item_id, date_str):
    """标记任务已完成（写入缓存）"""
    cache_file = _get_completed_cache_path()
    cache = {}
    if Path(cache_file).exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            pass

    # key格式: item_id_YYYY-MM-DD（将/转为-）
    key = f"{item_id}_{date_str.replace('/', '-')}"
    cache[key] = {
        'item_id': item_id,
        'date': date_str,
        'completed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 缓存超过200条时触发清理（删除60天前的老旧记录）
    if len(cache) > 200:
        _cleanup_completed_cache(cache, max_age_days=60)

    try:
        # 原子写入：先写.tmp再rename，避免崩溃导致缓存文件损坏
        tmp_file = cache_file + '.tmp'
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, cache_file)
    except Exception as e:
        log(f"写入完成缓存失败: {e}")

def _get_latest_row_for_item(csv_file, item_id):
    """获取某商品在CSV中的最新一条记录（按日期最晚）

    Returns:
        dict or None: 最新一条记录的字段字典，或None（如不存在）
    """
    if not os.path.exists(csv_file):
        return None
    try:
        encoding = detect_encoding(csv_file)
        latest_row = None
        latest_date = None
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ID', '') == item_id:
                    date_str = row.get('时间', '')
                    try:
                        row_date = datetime.strptime(date_str, '%Y/%m/%d')
                    except ValueError:
                        continue
                    if latest_date is None or row_date > latest_date:
                        latest_date = row_date
                        latest_row = row
        return latest_row
    except Exception:
        return None


# ============ CSV操作 ============
def parse_date_for_sort(date_str):
    """解析日期字符串用于排序"""
    try:
        # 处理格式：2026/3/25
        parts = date_str.split('/')
        if len(parts) == 3:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass
    return datetime.min


def get_previous_day_total(csv_file, item_id, current_date):
    """从CSV读取同一商品前一天的资产总量"""
    if not os.path.exists(csv_file):
        return None
    try:
        encoding = detect_encoding(csv_file)
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ID', '') == item_id and row.get('时间', '') == current_date:
                    # 处理CSV中带逗号的数值格式（如"1,259,242"）
                    total_str = row.get('资产总量', '0') or '0'
                    total_str = total_str.replace(',', '')
                    return int(float(total_str))
    except Exception:
        pass
    return None


def validate_cross_day(csv_file, data, max_drop_ratio=0.5, max_jump_ratio=2.0):
    """跨日期对比校验：与前一天数据对比，异常则跳过

    Args:
        csv_file: CSV文件路径
        data: 当前数据字典
        max_drop_ratio: 最大允许跌幅（如0.5表示跌幅不能超过50%）
        max_jump_ratio: 最大允许涨幅（如2.0表示涨幅不能超过100%）

    Returns:
        tuple: (is_valid: bool, reason: str)
    """
    from datetime import datetime, timedelta

    item_id = data.get('item_id', '')
    current_date_str = data.get('date', '')  # 格式: 2026/05/18

    # 解析当前日期，计算前一天
    try:
        current_date = datetime.strptime(current_date_str, '%Y/%m/%d')
    except ValueError:
        return True, "OK"  # 日期格式不对，跳过校验

    prev_date = current_date - timedelta(days=1)
    prev_date_str = prev_date.strftime('%Y/%m/%d')

    prev_total = get_previous_day_total(csv_file, item_id, prev_date_str)
    if prev_total is None or prev_total == 0:
        return True, "OK"  # 没有前一天数据，跳过校验

    current_total = data.get('zichan_zongliang', 0)
    if current_total == 0:
        return False, f"资产总量从{prev_total:,}跌至0，跌幅100%，疑似T+1未生成数据"

    change_ratio = current_total / prev_total

    # 跌幅过大
    if change_ratio < (1 - max_drop_ratio):
        drop_pct = (1 - change_ratio) * 100
        return False, f"资产总量从{prev_total:,}降至{current_total:,}（-{drop_pct:.1f}%），超过阈值"

    # 涨幅过大
    if change_ratio > max_jump_ratio:
        jump_pct = (change_ratio - 1) * 100
        return False, f"资产总量从{prev_total:,}升至{current_total:,}（+{jump_pct:.1f}%），超过阈值"

    return True, "OK"


# ========== Item Gate 共享辅助函数 ==========
_ITEM_CSV_FIELDS = ['资产总量', '浅种草', '深种草', '首购资产', '复购资产', '连带资产']


def _strip_val(v):
    """统一数值解析：从CSV单元格值（可能有引号/逗号）转为int"""
    return int(str(v).replace('"', '').replace(',', '')) if str(v).strip() else 0


def _is_data_essentially_same(prev_row, curr_data, threshold=0.0001):
    """判断新品数据和历史数据是否"实质相同"

    相同条件（二选一）：
    1. 所有字段完全相等（字节级相同）
    2. 变化率 < threshold（0.01%），视为T+1噪声

    Args:
        prev_row: 历史记录的字段字典（来自CSV DictReader）
        curr_data: 当前抓取的数据字典
        threshold: 变化率阈值，默认0.01%

    Returns:
        bool: True=实质相同，应跳过写入；False=有新数据，应写入
    """
    prev_vals = [_strip_val(prev_row.get(f, 0)) for f in _ITEM_CSV_FIELDS]
    curr_vals = [int(curr_data.get(f, 0)) for f in
                 ['zichan_zongliang', 'qian_zhongcao', 'shen_zhongcao',
                  'shougou', 'fugou', 'liandai']]

    # 快速路径：完全相等
    if prev_vals == curr_vals:
        return True

    # 逐一字段检查变化率（以最大值为分母，避免除零）
    all_within_threshold = True
    for p, c in zip(prev_vals, curr_vals):
        denom = max(abs(p), abs(c), 1)
        if abs(c - p) / denom > threshold:
            all_within_threshold = False
            break

    return all_within_threshold


# ========== 门禁 1: 业务平滑性校验 ==========
# 背景（2026-06-01）：用户反馈"正常数据线应平滑，悬崖式下跌是异常"
# 阈值：单日资产规模环比 > 30% 视为异常（不阻塞，仅告警）
def _check_business_smoothness(csv_file, data, threshold=0.30):
    """业务平滑性校验：检查环比涨跌是否超过阈值

    Args:
        csv_file: CSV文件路径
        data: 当前数据字典（含 item_id, date, zichan_zongliang）
        threshold: 环比涨跌阈值（默认 0.30 = 30%）

    Returns:
        str or None: 警告信息（None = 通过）
    """
    from datetime import datetime as dt, timedelta

    try:
        current_date = dt.strptime(data.get('date', ''), '%Y/%m/%d')
    except Exception:
        return None

    prev_date_str = (current_date - timedelta(days=1)).strftime('%Y/%m/%d')
    prev_total = get_previous_day_total(csv_file, data.get('item_id', ''), prev_date_str)
    if prev_total is None or prev_total == 0:
        return None

    current_total = data.get('zichan_zongliang', 0)
    if current_total == 0:
        return None

    change_ratio = (current_total - prev_total) / prev_total
    if abs(change_ratio) > threshold:
        direction = "上涨" if change_ratio > 0 else "下跌"
        return (f"商品 {data['item_id']} 日期 {data['date']} "
                f"资产总量从 {prev_total:,} {direction}到 {current_total:,} "
                f"({change_ratio*100:+.1f}%)，超过 {threshold*100:.0f}% 阈值")
    return None


# ========== 门禁 3: 复制日检测 ==========
# 背景（2026-06-01）：5/27 = 5/26 复制 6/15 商品，5/23 = 5/21 复制 6/15 商品
# 根因：T+1 数据未生成，API 返回最近有效日数据
# 检测：与前一日 6 字段完全相同
def _detect_copy_day(csv_file, data):
    """复制日检测：当前数据 6 字段是否与前一日完全相同

    Args:
        csv_file: CSV文件路径
        data: 当前数据字典

    Returns:
        tuple: (is_copy: bool, reason: str or None)
    """
    from datetime import datetime as dt, timedelta

    try:
        current_date = dt.strptime(data.get('date', ''), '%Y/%m/%d')
    except Exception:
        return False, None

    prev_date_str = (current_date - timedelta(days=1)).strftime('%Y/%m/%d')

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get('ID', '') == data.get('item_id', '')
                        and row.get('时间', '') == prev_date_str):
                    # 比较 6 字段
                    fields = [
                        ('资产总量', 'zichan_zongliang'),
                        ('浅种草', 'qian_zhongcao'),
                        ('深种草', 'shen_zhongcao'),
                        ('首购资产', 'shougou'),
                        ('复购资产', 'fugou'),
                        ('连带资产', 'liandai'),
                    ]
                    for csv_field, data_field in fields:
                        csv_val = row.get(csv_field, '').replace(',', '').strip()
                        data_val = str(data.get(data_field, 0)).strip()
                        if csv_val != data_val:
                            return False, None
                    return True, (f"商品 {data['item_id']} 日期 {data['date']} "
                                  f"6 字段与 {prev_date_str} 完全相同，疑似 T+1 延迟复制")
    except Exception:
        pass

    return False, None


# ========== 门禁 4: API 健康检查 ==========
# 背景：API 响应可能因 T+1 延迟返回错误数据
# 检查：浅+深+首+复+连 之和是否 < 总资产（子字段不能超过总量）
def _check_api_health(data):
    """API 健康检查：子字段和不应超过总资产

    Returns:
        tuple: (is_healthy: bool, reason: str or None)
    """
    total = data.get('zichan_zongliang', 0)
    sub_sum = (data.get('qian_zhongcao', 0)
               + data.get('shen_zhongcao', 0)
               + data.get('shougou', 0)
               + data.get('fugou', 0)
               + data.get('liandai', 0))
    if total > 0 and sub_sum > total * 1.5:
        return False, f"子字段和({sub_sum:,}) > 总资产({total:,})*1.5，API 异常"
    if total == 0 and sub_sum == 0:
        return False, "全 0 数据，T+1 未生成或 SPA 抓取失败"
    return True, None


def append_tocsv(csv_file, data):
    """追加数据到CSV - 追加模式（性能优化版）

    改为追加模式写入，避免每次全量读写+排序（O(n²) → O(1)）。
    排序由调用方在抓取结束后统一执行（sortcsv_by_date）。

    Args:
        csv_file: CSV文件路径
        data: 包含item_id, date, 和6个资产数据的字典

    Returns:
        bool: True表示保存成功，False表示保存失败
    """
    # 数据校验 - 异常数据不写入
    is_valid, reason = validate_item_data(data)
    if not is_valid:
        log(f"⚠️ 数据校验失败，跳过写入: {reason}")
        return False

    # 跨日期对比校验：与前一天数据对比，异常则跳过
    is_valid, reason = validate_cross_day(csv_file, data)
    if not is_valid:
        log(f"⚠️ 跨日期校验失败，跳过写入: {reason}")
        return False

    # ========== 门禁 4: API 健康检查（子字段和 vs 总资产）==========
    is_healthy, health_reason = _check_api_health(data)
    if not is_healthy:
        log(f"⚠️ 门禁 4 API 健康检查: {health_reason}，跳过写入")
        return False

    # ========== 门禁 3: 复制日检测（连续 2 天 6 字段全相同）==========
    # 背景（2026-06-01）：5/27 = 5/26 复制 6/15 商品，5/23 = 5/21 复制 6/15 商品
    # 根因：T+1 数据未生成，API 返回最近有效日数据
    # 修复：写入前检查前一日同商品 6 字段是否完全相同，全相同则标 likely-wrong 但仍写入
    is_copy, copy_reason = _detect_copy_day(csv_file, data)
    if is_copy:
        log(f"⚠️ 门禁 3 复制日检测: {copy_reason}，标记为 likely-wrong 但仍写入")
        data['_sanity'] = 'likely-wrong'
    else:
        data['_sanity'] = data.get('_sanity', 'verified')

    # ========== 门禁 1: 业务平滑性校验（环比 > 30% 报警）==========
    # 背景：正常 DMP 数据线应平滑，单日资产规模涨跌 > 30% 极不寻常
    # 不阻止写入，但记录到日志供后续 review
    smoothness_warn = _check_business_smoothness(csv_file, data)
    if smoothness_warn:
        log(f"⚠️ 门禁 1 业务平滑性: {smoothness_warn}")

    fieldnames = ['ID', '时间', '资产总量', '浅种草', '深种草', '首购资产', '复购资产', '连带资产', 'data_quality_flag']
    encoding = detect_encoding(csv_file)

    # 检查是否已存在（去重扫描）
    file_exists = os.path.exists(csv_file)
    if file_exists:
        try:
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('ID', '') == data['item_id'] and row.get('时间', '') == data['date']:
                        log(f"⏭️ 数据已存在: 商品{data['item_id']} 日期{data['date']}，跳过")
                        _mark_completed(data['item_id'], data['date'])
                        return True  # 已存在不算失败
        except Exception as e:
            log(f"去重扫描失败: {e}")

    # ========== Gate 1: 与最新一条实质相同则跳过（T+1未更新）==========
    # 判断标准：完全相同 OR 所有字段变化率 < 0.01%（微小噪声）
    try:
        latest_row = _get_latest_row_for_item(csv_file, data['item_id'])
        if latest_row is not None and _is_data_essentially_same(latest_row, data):
            total = int(data.get('zichan_zongliang', 0))
            log(f"⏭️ 商品 {data['item_id']} {data['date']} 数据实质相同（资产总量={total:,}），"
                f"判定为T+1未更新，跳过写入")
            _mark_completed(data['item_id'], data['date'])
            return True
    except Exception as e:
        log(f"Gate 1 校验失败: {e}")

    # 追加写入（不排序，跑完后统一排序）
    try:
        with open(csv_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            # data_quality_flag: 'verified' (通过 sanity check + 跨日期校验)
            #                   'legacy'  (本字段已写入历史数据，回填标识)
            # 上层可读取 data['_sanity'] 决定本次写入的 flag
            quality_flag = data.get('_sanity', 'verified')
            writer.writerow({
                'ID': data['item_id'],
                '时间': data['date'],
                '资产总量': str(data.get('zichan_zongliang', 0)),
                '浅种草': str(data.get('qian_zhongcao', 0)),
                '深种草': str(data.get('shen_zhongcao', 0)),
                '首购资产': str(data.get('shougou', 0)),
                '复购资产': str(data.get('fugou', 0)),
                '连带资产': str(data.get('liandai', 0)),
                'data_quality_flag': quality_flag,
            })

        log(f"已追加商品 {data['item_id']} {data['date']} 的数据到CSV（追加模式）")
        
        # 标记为已完成（断点续传）
        _mark_completed(data['item_id'], data['date'])
        
        return True
    except Exception as e:
        log(f"追加CSV失败: {e}")
        return False


def sortcsv_by_date(csv_file):
    """按日期升序对整个CSV文件排序（在抓取结束后调用）"""
    if not os.path.exists(csv_file):
        return
    
    encoding = detect_encoding(csv_file)
    fieldnames = ['ID', '时间', '资产总量', '浅种草', '深种草', '首购资产', '复购资产', '连带资产', 'data_quality_flag']

    try:
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return
        
        sorted_rows = sorted(rows, key=lambda x: parse_date_for_sort(x.get('时间', '')))
        
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted_rows)
        
        log(f"CSV已按日期排序: {csv_file} ({len(sorted_rows)} 行)")
    except Exception as e:
        log(f"排序CSV失败: {e}")


# ============ 主程序 ============
def main():
    """独立运行入口"""
    # 确定配置
    if USING_COMMON:
        data_file = Config.ITEM_DATA_FILE
        item_ids = Config.ITEM_IDS
        debug_dir = Config.DEBUG_DIR
    
    log("=" * 50)
    log("达摩盘单品洞察数据抓取工具启动")
    log("=" * 50)
    
    # 读取账号
    username, password = read_account()
    if not username or not password:
        log("错误：无法读取账号密码")
        return False
    log(f"读取到账号: {username}")
    
    # 获取目标日期
    t_minus_1, t_minus_2 = get_target_dates()
    log(f"目标日期 T-1: {format_date_for_csv(t_minus_1)}, T-2: {format_date_for_csv(t_minus_2)}")
    
    # 分析欠缺日期
    log("\n" + "=" * 50)
    log("分析CSV中欠缺的日期...")
    log("=" * 50)
    
    if USING_COMMON:
        missing_dates = get_missing_dates_item(data_file, item_ids, max_days_to_fill=90)
    
    if not missing_dates:
        log("所有商品最近7天的数据都已齐全，无需抓取")
        return True
    
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
    
    log(f"\n共需抓取 {len(tasks)} 条数据")
    for task in tasks[:5]:
        log(f"  - 商品 {task['item_id']} 日期 {task['date_str']}")
    if len(tasks) > 5:
        log(f"  ... 还有 {len(tasks)-5} 个任务")
    
    # 启动浏览器
    log("\n启动浏览器...")
    
    if USING_COMMON:
        # 使用公共模块的浏览器管理
        with BrowserManager(headless=False) as browser:
            page = browser.new_page()
            page.set_viewport_size({'width': 1920, 'height': 1080})
            
            try:
                # 登录
                log("\n" + "=" * 50)
                log("步骤1：登录千牛/淘宝")
                log("=" * 50)
                
                if not login_qianniu(page, username, password, debug_name="item_login"):
                    log("千牛登录失败，退出")
                    return False
                
                log("\n[OK] 登录成功！")
                
                # 注入反检测脚本（公共模块模式）
                if HAS_ANTI_DETECT:
                    log("注入反检测脚本...")
                    apply_anti_detect(page)
                    log("反检测措施已启用")
                
                # 抓取数据
                success_count, fail_tasks = run_items_fetch(page, tasks, data_file)
                
            except Exception as e:
                log(f"运行出错: {e}")
    else:
        # 独立模式启动浏览器
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        os.makedirs(debug_dir, exist_ok=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            page = browser.new_page()
            page.set_viewport_size({'width': 1920, 'height': 1080})
            
            try:
                # 登录
                log("\n" + "=" * 50)
                log("步骤1：登录千牛/淘宝")
                log("=" * 50)
                
                if not login_qianniu(page, username, password):
                    log("千牛登录失败，退出")
                    browser.close()
                    return False
                
                log("\n[OK] 登录成功！")
                
                # 注入反检测脚本（独立模式）
                if HAS_ANTI_DETECT:
                    log("注入反检测脚本...")
                    apply_anti_detect(page)
                    log("反检测措施已启用")
                
                # 抓取数据
                success_count, fail_tasks = run_items_fetch(page, tasks, data_file)
                
            except Exception as e:
                log(f"运行出错: {e}")
            
            finally:
                browser.close()
    
    return True


def run_items_fetch(page, tasks, data_file):
    """执行单品数据抓取（供主程序或统一入口调用）"""
    log("\n" + "=" * 50)
    log(f"步骤2：开始抓取 {len(tasks)} 条数据...")
    log("=" * 50)
    
    # === 断点续传：加载已完成的任务 ===
    completed_items = _load_completed_items()
    log(f"已完成缓存中已有 {len(completed_items)} 条记录")
    
    # 反检测：频率限制
    if HAS_ANTI_DETECT:
        rate_limiter = RateLimiter(
            max_items_per_run=CONFIG.get('anti_detect', {}).get('max_items_per_run', 5),
            min_delay=CONFIG.get('anti_detect', {}).get('item_delay_min', 10),
            max_delay=CONFIG.get('anti_detect', {}).get('item_delay_max', 30),
            max_requests_per_day=CONFIG.get('anti_detect', {}).get('max_requests_per_day', 50)
        )
        
        # 检查每日请求限制
        if not rate_limiter.can_request():
            log(f"⚠️ 今日请求数已达上限({rate_limiter.max_requests_per_day})，停止抓取")
            return 0, tasks
        
        # 限制单次运行数量
        original_count = len(tasks)
        limited_count = rate_limiter.should_limit(original_count)
        if limited_count < original_count:
            log(f"⚠️ 单次运行限制：从{original_count}条缩减到{limited_count}条")
            tasks = tasks[:limited_count]
        
        log(f"频率限制器已启用 | 今日剩余请求: {rate_limiter.remaining_requests()}")
    
    success_count = 0
    fail_tasks = []
    
    for i, task in enumerate(tasks, 1):
        item_id = task['item_id']
        target_date = task['target_date']
        date_str = task['date_str']
        
        # === 断点续传检查：跳过已完成的 ===
        if (item_id, date_str) in completed_items:
            log(f"[{i}/{len(tasks)}] 商品 {item_id} 日期 {date_str} 已完成，跳过")
            continue
        
        log(f"\n{'='*30}")
        log(f"[{i}/{len(tasks)}] 商品 {item_id} 日期 {date_str}")
        log(f"{'='*30}")
        
        try:
            # 为该日期构造T-1和T-2
            t1 = target_date
            t2 = target_date - timedelta(days=1)
            
            data = fetch_item_data(page, item_id, t1, t2)
            
            if data and data.get('zichan_zongliang', 0) > 0:
                if append_tocsv(data_file, data):
                    success_count += 1
                    log(f"[OK] 商品 {item_id} 日期 {date_str} 抓取成功")
                    
                    # 记录请求
                    if HAS_ANTI_DETECT:
                        rate_limiter.record_request()
                else:
                    log(f"[FAIL] 商品 {item_id} 日期 {date_str} 保存失败")
                    fail_tasks.append(task)
            else:
                log(f"[FAIL] 商品 {item_id} 日期 {date_str} 数据为空")
                fail_tasks.append(task)
            
            # 每个任务间隔 - 反检测：随机延迟替代固定5秒
            if i < len(tasks):
                if HAS_ANTI_DETECT:
                    delay = human_delay(
                        CONFIG.get('anti_detect', {}).get('item_delay_min', 10),
                        CONFIG.get('anti_detect', {}).get('item_delay_max', 30)
                    )
                    log(f"随机延迟 {delay:.1f}秒后处理下一个商品...")
                else:
                    delay = random.uniform(5, 10)
                    log(f"等待 {delay:.1f}秒后处理下一个...")
                    time.sleep(delay)
                
        except Exception as e:
            error_msg = str(e)
            log(f"[FAIL] 商品 {item_id} 日期 {date_str} 出错: {e}")
            fail_tasks.append(task)
            
            # 检测浏览器是否崩溃，如果是则标记需要重启
            if 'closed' in error_msg.lower() or 'target' in error_msg.lower():
                log("⚠️ 检测到浏览器可能已崩溃！")
                raise  # 向上层抛出，由调用方决定是否重启浏览器
    
    # 输出结果
    log("\n" + "=" * 50)
    log(f"单品洞察完成: 成功 {success_count}/{len(tasks)}")
    if fail_tasks:
        log(f"失败任务数: {len(fail_tasks)}")
    log("=" * 50)
    
    return success_count, fail_tasks


# ============ 统一入口支持 ============
def run_with_page(page, missing_dates=None):
    """
    供 dmp_master.py 统一入口调用
    
    Args:
        page: 已登录的Playwright页面对象
        missing_dates: 需要抓取的日期字典 {item_id: [date1, date2, ...]}，为None则自动检测
    
    Returns:
        tuple: (success_count, total_count)
    """
    data_file = Config.ITEM_DATA_FILE if USING_COMMON else DATA_FILE
    item_ids = Config.ITEM_IDS if USING_COMMON else ITEM_IDS
    
    if missing_dates is None:
        if USING_COMMON:
            missing_dates = get_missing_dates_item(data_file, item_ids, max_days_to_fill=90)
    
    if not missing_dates:
        log("单品洞察数据已是最新，无需补齐")
        return 0, 0
    
    # 构建任务列表
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
    
    log(f"单品洞察共需抓取 {len(tasks)} 条数据")
    
    success_count, fail_tasks = run_items_fetch(page, tasks, data_file)
    
    return success_count, len(tasks)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
