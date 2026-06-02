#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMP公共模块 - 所有子模块共享的基础设施
提供配置管理、浏览器管理、登录、日志、CSV工具、日期工具等

重建时间: 2026-04-05
重建依据: 从 dmp_master.py / dmp_flow_scraper.py / dmp_item_insight_scraper.py 的
          import 语句和 fallback 代码中反推完整接口
"""

import csv
import os
import time
from datetime import datetime, timedelta


# ============ 脚本目录常量 ============
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_SCRIPT_DIR, 'del')
LOG_FILE = os.path.join(LOG_DIR, f'dmp_run_{datetime.now().strftime("%Y%m%d")}.log')

# [优化] 日志初始化：模块加载时一次性创建目录，避免每次 log() 调用都执行 os.makedirs
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    pass  # 创建失败不影响后续 log() 兜底


# ============ 日志函数 ============
def log(msg):
    """统一日志函数（带时间戳）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)  # flush=True 确保 nohup 下立即输出

    # 追加文件日志
    # [优化] 移除每次调用的 os.makedirs，目录已由模块初始化时创建
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{now}] {msg}\n")
    except Exception:
        pass


# ============ 配置类 ============
class Config:
    """集中管理所有路径和配置参数"""
    
    # 脚本所在目录（供外部引用）
    _SCRIPT_DIR = _SCRIPT_DIR
    
    # 数据文件路径
    ASSETS_DATA_FILE = os.path.join(_SCRIPT_DIR, "data2.csv")
    FLOW_DATA_FILE = os.path.join(_SCRIPT_DIR, "data.csv")
    ITEM_DATA_FILE = os.path.join(_SCRIPT_DIR, "data3.csv")
    
    # 调试目录
    DEBUG_DIR = os.path.join(_SCRIPT_DIR, "del")
    
    # 浏览器用户数据目录（保持登录态）
    USER_DATA_DIR = os.path.join(_SCRIPT_DIR, "chrome_profile")
    
    # 账号文件
    ACCOUNT_FILE = os.path.join(_SCRIPT_DIR, "account.txt")
    
    # 商品ID列表（与 config/items.yaml 保持一致）
    ITEM_IDS = [
        "587051744204", "597655781410", "587053192746", "683395365107", "654390297284",
        "803474428381", "870597889980", "621639424901", "601760206476", "612503357090",
        "803417397714", "994162104051", "933524395698", "900975734816",
        "1010458880710"  # 传明酸面膜（2026-04-21新增）
    ]

    # 达摩盘 URL 配置
    DMP_BASE_URL = "https://dmp.taobao.com/index_new.html"
    # spm 参数（从浏览器地址栏复制，当前有效值，变动时需更新）
    DMP_SPM = "a2e3k.28338430.c0d46757f.de019e68a.1d1125ebOCRO8L"
    # 各模块路由路径
    DMP_ROUTE_ASSETS = "#!/deeplink-new/assets-diagnose"
    DMP_ROUTE_FLOW = "#!/deeplink/flow"
    DMP_ROUTE_ITEM = "#!/items/item-insight"


# ============ 编码检测 ============
def detect_encoding(file_path):
    """检测文件编码（按优先级尝试）"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)
            return encoding
        except Exception:
            continue
    return 'utf-8'


# ============ CSV写入公共函数 ============
def safe_write_csv(csv_file, new_rows, dedup_key_fn=None):
    """
    安全写入CSV：先读取现有数据，去重，再写入
    
    Args:
        csv_file: CSV文件路径
        new_rows: 新数据行列表（字典列表）
        dedup_key_fn: 去重键函数，接收row返回key（可选）
    
    Returns:
        bool: 是否成功写入
    """
    import csv
    existing_rows = []
    if os.path.exists(csv_file):
        try:
            encoding = detect_encoding(csv_file)
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                existing_rows = list(reader)
        except Exception as e:
            log(f"读取现有CSV失败: {e}")
    
    if dedup_key_fn and existing_rows:
        existing_keys = {dedup_key_fn(r) for r in existing_rows}
        new_rows = [r for r in new_rows if dedup_key_fn(r) not in existing_keys]
    
    all_rows = existing_rows + new_rows
    if not all_rows:
        return True
    
    fieldnames = list(all_rows[0].keys())
    file_dir = os.path.dirname(csv_file)
    if file_dir:
        os.makedirs(file_dir, exist_ok=True)
    
    try:
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        return True
    except Exception as e:
        log(f"写入CSV失败: {e}")
        return False


# ============ 日期工具 ============
def parse_date(date_str):
    """解析多种格式的日期字符串"""
    if not date_str:
        return None
    formats = ['%Y/%m/%d', '%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            continue
    return None


def format_date_for_csv(dt):
    """将datetime或date格式化为CSV用的日期字符串 (2026/4/1)
    
    注意：CSV中存储的是不带前导零的格式，如 2026/5/21
    而 strftime('%Y/%m/%d') 生成带前导零的格式如 2026/05/21
    必须去掉前导零以保持一致，否则 get_missing_dates_* 函数无法正确比对
    """
    if isinstance(dt, datetime):
        s = dt.strftime('%Y/%m/%d')
    elif isinstance(dt, __import__('datetime').date):
        s = dt.strftime('%Y/%m/%d')
    else:
        return str(dt)
    # 去掉前导零：2026/05/21 -> 2026/5/21
    parts = s.split('/')
    return f"{parts[0]}/{int(parts[1])}/{int(parts[2])}"


def normalize_date_str(date_str):
    """标准化日期字符串，处理各种格式不一致 (2026/1/16 -> 2026/01/16)"""
    if not date_str:
        return date_str
    dt = parse_date(date_str.strip())
    if dt:
        return format_date_for_csv(dt)
    return date_str.strip()


def parse_number(value):
    """解析数字字符串（去除逗号）"""
    if not value:
        return 0
    try:
        return int(str(value).replace(',', '').strip())
    except Exception:
        return 0


# ============ 账号读取 ============
def read_account():
    """从 account.txt 读取账号密码
    
    支持多种格式：
        账号：xxx
        账号:xxx
        账号=xxx
        password:xxx
        password=xxx
    """
    try:
        with open(Config.ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) < 2:
                log("账号文件格式错误：至少需要两行（账号和密码）")
                return None, None
            
            # 解析第一行（账号）
            line1 = lines[0].strip()
            username = None
            for prefix in ['账号：', '账号:', '账号=', 'username:', 'username=', 'user:', 'user=']:
                if line1.startswith(prefix):
                    username = line1[len(prefix):].strip()
                    break
            if not username:
                # 尝试用冒号或等号分割
                if ':' in line1:
                    username = line1.split(':', 1)[1].strip()
                elif '=' in line1:
                    username = line1.split('=', 1)[1].strip()
                else:
                    username = line1
            
            # 解析第二行（密码）
            line2 = lines[1].strip()
            password = None
            for prefix in ['密码：', '密码:', '密码=', 'password:', 'password=', 'pass:', 'pass=']:
                if line2.startswith(prefix):
                    password = line2[len(prefix):].strip()
                    break
            if not password:
                # 尝试用冒号或等号分割
                if ':' in line2:
                    password = line2.split(':', 1)[1].strip()
                elif '=' in line2:
                    password = line2.split('=', 1)[1].strip()
                else:
                    password = line2
            
            if username and password:
                log(f"读取到用户名: {username}")
                return username, password
            else:
                log("账号文件格式错误：无法解析用户名或密码")
                return None, None
    except Exception as e:
        log(f"读取账号文件失败: {e}")
        return None, None


# ============ 缺失日期检测 ============
def get_missing_dates_assets(csv_file, days_to_check=14):
    """获取资产诊断需要补齐的日期列表

    策略：检查最近N天内所有缺失的日期（T-2 及之前）
    自动发现并补充所有漏掉的日期，不只是最新日期之后
    """
    existing_dates = set()

    if os.path.exists(csv_file):
        encoding = detect_encoding(csv_file)
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('time', '') or row.get('date', '') or row.get('时间', '') or row.get('Date', '')
                dt = parse_date(date_str)
                if dt:
                    existing_dates.add(dt.date())

    # 目标：检查最近 days_to_check 天内所有缺失的日期
    target_date = (datetime.now() - timedelta(days=1)).date()  # T-1（原为T-2）
    start_date = target_date - timedelta(days=days_to_check - 1)

    log(f"资产诊断：检查 {start_date} ~ {target_date} 期间的缺失日期")

    # 生成目标范围内所有日期
    all_target_dates = set()
    current = start_date
    while current <= target_date:
        all_target_dates.add(current)
        current += timedelta(days=1)

    # 计算缺失日期
    missing = sorted(all_target_dates - existing_dates)

    if missing:
        log(f"资产诊断：发现 {len(missing)} 个缺失日期: {[str(d) for d in missing]}")
    else:
        log(f"资产诊断：最近 {days_to_check} 天数据已齐全")

    return missing


def get_missing_dates_flow(csv_file, max_days_to_fill=60):
    """获取流转数据需要补齐的日期列表

    策略：从最早日期到最新日期，检测所有缺失的日期
    限制最多补 max_days_to_fill 天（避免一次抓太多）
    """
    existing_dates = set()

    if os.path.exists(csv_file):
        encoding = detect_encoding(csv_file)
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('date', '')
                dt = parse_date(date_str)
                if dt:
                    existing_dates.add(dt.date())

    if len(existing_dates) < 2:
        log("警告：流转数据不足，无法确定日期范围")
        return []

    min_date = min(existing_dates)
    max_date = max(existing_dates)
    target_date = (datetime.now() - timedelta(days=1)).date()

    # 生成完整日期范围
    all_dates = set()
    current = min_date
    while current <= min(target_date, max_date + timedelta(days=max_days_to_fill)):
        all_dates.add(current)
        current += timedelta(days=1)

    # 计算缺口
    missing = sorted(all_dates - existing_dates)
    log(f"流转：已有 {len(existing_dates)} 个日期，缺失 {len(missing)} 个")
    log(f"流转：日期范围 {min_date} ~ {min(target_date, max_date + timedelta(days=max_days_to_fill))}")

    return missing[:max_days_to_fill]  # 限制数量


def get_missing_dates_item(csv_file, item_ids, max_days_to_fill=90, data_retention_days=90):
    """分析单品数据CSV，找出每个商品ID欠缺的日期
    
    策略：从最早日期到最新日期，检测所有缺失的日期
    限制最多补 max_days_to_fill 天（避免一次抓太多）
    最早只追溯到90天前（达摩盘数据保留期限）
    
    Args:
        csv_file: data3.csv路径
        item_ids: 商品ID列表
        max_days_to_fill: 最多补多少天数据（默认90天）
        data_retention_days: 数据保留天数上限（默认90天），早于此的数据无法抓取
    
    Returns:
        dict: {item_id: [date1, date2, ...]}
    """
    from datetime import datetime as dt_datetime, timedelta as tdelta
    
    # 读取CSV中已有的数据
    existing_data = {}  # {item_id: set of date strings}
    all_dates_set = set()  # 所有出现过的日期
    
    if os.path.exists(csv_file):
        try:
            encoding = detect_encoding(csv_file)
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item_id = row.get('ID', '')
                    date_str = normalize_date_str(row.get('时间', ''))
                    if item_id and date_str:
                        if item_id not in existing_data:
                            existing_data[item_id] = set()
                        existing_data[item_id].add(date_str)
                        all_dates_set.add(date_str)
            log(f"CSV中已有 {len(existing_data)} 个商品的数据，共 {len(all_dates_set)} 个日期")
        except Exception as e:
            log(f"读取单品CSV分析欠缺日期失败: {e}")
    
    if len(all_dates_set) < 2:
        log("警告：单品数据不足，无法确定日期范围")
        return {}
    
    # 解析所有日期，找到最早和最晚
    parsed_dates = []
    for d in all_dates_set:
        dt = parse_date(d)
        if dt:
            parsed_dates.append(dt.date())
    
    if not parsed_dates:
        log("警告：无法解析任何日期")
        return {}
    
    min_date = min(parsed_dates)
    max_date = max(parsed_dates)
    today = dt_datetime.now().date()
    
    # 数据保留期限：最多只能追溯到 N 天前
    retention_boundary = today - tdelta(days=data_retention_days)
    # 取CSV中最早日期和保留期限的较大值（不早于保留期限）
    effective_min_date = max(min_date, retention_boundary)
    
    target_end = min(today - tdelta(days=1), max_date + tdelta(days=max_days_to_fill))
    
    log(f"单品洞察：CSV日期范围 {min_date} ~ {max_date}")
    log(f"单品洞察：有效追溯范围 {effective_min_date} ~ {target_end}（保留期限{data_retention_days}天）")
    
    # 生成完整日期范围内的所有日期字符串
    all_target_dates = []
    current = effective_min_date
    while current <= target_end:
        all_target_dates.append(format_date_for_csv(current))
        current += tdelta(days=1)
    
    log(f"单品洞察：需要检查 {len(all_target_dates)} 个日期")
    
    # 对每个商品ID，找出缺失的日期
    missing_dates = {}
    for item_id in item_ids:
        existing_dates_set = existing_data.get(item_id, set())
        missing = [d for d in all_target_dates if d not in existing_dates_set]
        if missing:
            missing_dates[item_id] = missing
            log(f"商品 {item_id} 欠缺 {len(missing)} 天数据")
    
    total_missing = sum(len(v) for v in missing_dates.values())
    log(f"单品洞察：共 {len(missing_dates)} 个商品有缺失，总计 {total_missing} 条待补数据")
    
    return missing_dates


# ============ 浏览器管理器 ============
class BrowserManager:
    """Playwright 浏览器上下文管理器（支持复用chrome_profile保持登录态）
    
    用法:
        with BrowserManager(headless=False) as browser:
            page = browser.new_page()
            ...
    """
    
    def __init__(self, headless=False, user_data_dir=None):
        """
        Args:
            headless: 是否无头模式
            user_data_dir: 用户数据目录（默认使用 Config.USER_DATA_DIR）
        """
        self.headless = headless
        self.user_data_dir = user_data_dir or Config.USER_DATA_DIR
        self._playwright = None
        self._browser = None
        
        # 确保用户数据目录存在
        os.makedirs(self.user_data_dir, exist_ok=True)
    
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            channel="chrome",
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1920,1080',
            ]
        )

        # ========== 反爬虫注入：navigator.webdriver 覆写 ==========
        # 达摩盘/Taobao 会检查 window.navigator.webdriver === true 来检测自动化
        # add_init_script 在每个新 page 创建时自动执行，早于任何页面 JS
        self._browser.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true
            });
        """)

        return self._browser
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        return False


# ============ 登录函数 ============
def _update_spm_from_url(page):
    """
    从浏览器当前URL自动提取spm参数，并更新到Config
    
    达摩盘URL格式: https://dmp.taobao.com/...?spm=xxx#!/...
    spm参数会随登录会话变化，需要从实际访问的URL中提取最新值
    """
    import re
    try:
        current_url = page.url or ""
        # 匹配 ?spm=xxx 或 &spm=xxx
        m = re.search(r'[?&]spm=([^&]+)', current_url)
        if m:
            extracted_spm = m.group(1)
            if extracted_spm and extracted_spm != Config.DMP_SPM:
                old_spm = Config.DMP_SPM
                Config.DMP_SPM = extracted_spm
                log(f"✓ SPM自动更新: {old_spm} -> {Config.DMP_SPM}")
            else:
                log(f"✓ SPM已是最新，无需更新: {Config.DMP_SPM}")
        else:
            log(f"⚠️ 当前URL未包含spm参数，跳过更新 (URL: {current_url[:80]}...)")
    except Exception as e:
        log(f"⚠️ SPM提取失败: {e}")


def check_dmp_session(page):
    """
    快速检查达摩盘会话是否仍然有效（避免重复登录触发反爬）
    
    Returns:
        bool: True 表示已登录且会话有效，False 表示需要重新登录
    """
    try:
        log("[会话检测] 检查达摩盘登录状态...")
        page.goto("https://dmp.taobao.com/", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        
        # 检测页面是否有"立即登录"按钮（未登录标志）
        login_btns = page.query_selector_all("button:has-text('立即登录')")
        if len(login_btns) > 0:
            log("[会话检测] 检测到未登录（页面有'立即登录'按钮），需要重新登录")
            return False
        
        # 进一步检查：尝试访问资产页面，看是否被重定向到登录
        page_title = page.title() or ""
        if "登录" in page_title:
            log("[会话检测] 检测到登录页（title包含'登录'），需要重新登录")
            return False
        
        log("[会话检测] ✓ 会话仍然有效，跳过登录")
        return True
    except Exception as e:
        log(f"[会话检测] 检查异常: {e}，视为需要重新登录")
        return False


def login_qianniu(page, username, password, debug_name="default"):
    """
    千牛/淘宝登录（公共模块版）
    
    流程：
    1. 访问千牛登录页
    2. 处理可能的恢复弹窗
    3. 切换密码登录tab
    4. 填写账号密码
    5. 勾选协议并登录
    6. 处理验证码（需人工）
    7. 检测登录成功
    
    注意：必须先登录千牛再访问达摩盘，不能直接访问达摩盘登录页
    
    Args:
        page: Playwright页面对象
        username: 用户名
        password: 密码
        debug_name: 调试标识（用于截图文件名）
    
    Returns:
        bool: 是否登录成功
    """
    debug_dir = Config.DEBUG_DIR
    os.makedirs(debug_dir, exist_ok=True)
    
    log(f"[{debug_name}] 访问千牛登录页面...")
    page.goto("https://login.taobao.com/member/login.jhtml",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # 处理浏览器异常退出后的恢复弹窗
    try:
        recovery_selectors = [
            "button:has-text('恢复')",
            "button:has-text('Restore')",
            "[class*='recovery']",
            "[class*='restore']",
            ".dialog-btn:not(.dialog-btn-ok)",
        ]
        for selector in recovery_selectors:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    log(f"[{debug_name}] 检测到恢复弹窗，点击拒绝恢复...")
                    elem.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        # 拒绝恢复按钮
        try:
            refuse_btn = page.locator("button:has-text('否')").first
            if refuse_btn.is_visible(timeout=2000):
                log(f"[{debug_name}] 点击'否'拒绝恢复会话")
                refuse_btn.click()
                time.sleep(2)
        except Exception:
            pass

        # 强制关闭弹窗
        try:
            close_btn = page.locator("[class*='close'], [class*='dismiss'], .dialog-close").first
            if close_btn.is_visible(timeout=2000):
                close_btn.click()
                time.sleep(1)
        except Exception:
            pass
    except Exception as e:
        log(f"[{debug_name}] 处理恢复弹窗时出错: {e}")

    # 截图保存
    try:
        screenshot_path = os.path.join(debug_dir, f"{debug_name}_login.png")
        page.screenshot(path=screenshot_path)
        log(f"[{debug_name}] 已保存登录页面截图: {screenshot_path}")
    except Exception:
        pass

    # ===== 重要：先检测是否已登录（Chrome Profile有Cookie时可能直接跳转）=====
    try:
        login_form_selectors = [
            "#fm-login-id", "#TPL_username_1", "input[name='fm-login-id']",
            "input[placeholder*='手机号']", "input[placeholder*='用户名']"
        ]
        form_visible = False
        for selector in login_form_selectors:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    form_visible = True
                    break
            except Exception:
                continue
        
        if not form_visible:
            # 没有登录表单，说明已经是登录状态
            current_url = page.url or ""
            log(f"[{debug_name}] ✅ 检测到已登录状态（Cookie有效），无需重复登录")
            log(f"[{debug_name}] 当前页面: {current_url[:80]}")
            _update_spm_from_url(page)
            return True
    except Exception as e:
        log(f"[{debug_name}] 检测登录状态时出错: {e}，继续尝试登录...")

    try:
        # 切换密码登录
        log(f"[{debug_name}] 尝试切换到密码登录...")
        try:
            password_tab = page.locator(
                "text=密码登录, .password-login-tab, [data-spm*='password']"
            ).first
            if password_tab.is_visible():
                password_tab.click()
                time.sleep(1)
        except Exception:
            pass
        
        # 填写用户名
        log(f"[{debug_name}] 输入用户名: {username}")
        username_input = page.locator(
            "#fm-login-id, #TPL_username_1, input[name='fm-login-id'], "
            "input[placeholder*='手机号'], input[placeholder*='用户名']"
        ).first
        username_input.fill(username)
        time.sleep(1)
        
        # 填写密码
        log(f"[{debug_name}] 输入密码...")
        password_input = page.locator(
            "#fm-login-password, #TPL_password_1, input[type='password']"
        ).first
        password_input.fill(password)
        time.sleep(1)
        
        # 勾选协议
        log(f"[{debug_name}] 勾选用户协议...")
        try:
            page.wait_for_selector("#fm-agreement-checkbox", timeout=5000)
            checkbox = page.locator("#fm-agreement-checkbox").first
            if not checkbox.is_checked():
                checkbox.click()
                log(f"[{debug_name}] 已勾选协议")
            else:
                log(f"[{debug_name}] 协议已勾选")
            time.sleep(1)
        except Exception as e:
            log(f"[{debug_name}] 勾选协议失败或不需要勾选: {e}")
            try:
                checkbox = page.locator("input[type='checkbox']").first
                if checkbox.is_visible() and not checkbox.is_checked():
                    checkbox.click()
                    log(f"[{debug_name}] 已勾选协议(备用选择器)")
                    time.sleep(1)
            except Exception:
                pass
        
        # 点击登录
        log(f"[{debug_name}] 点击登录按钮...")
        login_btn = page.locator(
            ".fm-button.fm-submit, button[type='submit'], .login-btn, button:has-text('登录')"
        ).first
        login_btn.click()
        
        # 等待登录完成
        log(f"[{debug_name}] 等待登录完成...")
        time.sleep(3)
        
        # 处理同意验证框（快速检查，不阻塞）
        log(f"[{debug_name}] 检查登录后的同意验证框...")
        try:
            agree_btn = page.locator("button.dialog-btn.dialog-btn-ok").first
            if agree_btn.is_visible(timeout=3000):
                log(f"[{debug_name}] 检测到同意验证框，点击同意...")
                agree_btn.click()
                log(f"[{debug_name}] 已点击同意，等待跳转...")
                
                max_wait = 30
                waited = 0
                current_url = page.url or ""
                while "login" in current_url.lower() and waited < max_wait:
                    time.sleep(1)
                    waited += 1
                    current_url = page.url or ""
                    if waited % 5 == 0:
                        log(f"[{debug_name}] 等待中... ({waited}s), 当前URL: {current_url}")
                
                log(f"[{debug_name}] 登录后页面URL: {current_url}")
            else:
                log(f"[{debug_name}] 未检测到同意验证框（可能不需要），继续...")
        except Exception as e:
            log(f"[{debug_name}] 未检测到同意验证框: {e}")
            current_url = page.url or ""
            log(f"[{debug_name}] 当前页面URL: {current_url}")
        
        # 检查验证码
        if page.locator(".nc-container, .captcha, .verify, iframe[src*='captcha']").count() > 0:
            log(f"[{debug_name}] 【需要人工干预】检测到验证码，请在浏览器中完成验证...")
            input("完成验证后按回车继续...")
        
        # 等待跳转
        log(f"[{debug_name}] 等待页面跳转...")
        time.sleep(5)
        
        current_url = page.url or ""
        log(f"[{debug_name}] 当前页面: {current_url}")
        
        # 登录成功判断（修复：AND逻辑）
        url_lower = current_url.lower()
        not_in_login = "login" not in url_lower
        is_valid_target = "qianniu" in url_lower or "amr" in url_lower or "taobao.com" in url_lower
        
        if not_in_login and is_valid_target:
            log(f"[{debug_name}] 千牛登录成功！")
            # 自动从当前URL提取spm参数（下次请求达摩盘需要用到）
            _update_spm_from_url(page)
            return True
        else:
            log(f"[{debug_name}] ⚠️ 仍在登录页面或目标异常，可能需要人工确认")
            log(f"[{debug_name}] 请在浏览器中确认是否已登录，然后按回车继续...")
            input()
            final_url = (page.url or "").lower()
            if "login" not in final_url:
                # 人工确认后也尝试提取spm
                _update_spm_from_url(page)
                return True
            else:
                return False
                
    except Exception as e:
        log(f"[{debug_name}] 登录过程出错: {e}")
        import traceback
        log(traceback.format_exc())
        return False


# ============ 反检测便捷导入（可选依赖） ============
try:
    from anti_detect import (
        inject_stealth_scripts, human_delay, human_delay_normal,
        human_hesitate, human_move_to, human_click, human_scroll,
        get_random_headers, apply_anti_detect, RateLimiter
    )
    HAS_ANTI_DETECT = True
except ImportError:
    HAS_ANTI_DETECT = False
    # 提供空实现避免调用方报错
    def inject_stealth_scripts(page):
        pass

    def human_delay(min_sec=2, max_sec=5):
        import random as _r
        t = _r.uniform(min_sec, max_sec)
        time.sleep(t)
        return t

    def human_delay_normal(mean, std, min_val=None, max_val=None):
        import random as _r
        d = _r.gauss(mean, std)
        if min_val is not None:
            d = max(min_val, d)
        if max_val is not None:
            d = min(max_val, d)
        time.sleep(d)
        return d

    def human_hesitate():
        return 'normal'

    def human_move_to(page, x, y, duration=0.5, steps=10):
        return False

    def human_click(page, x, y, delay_before=0.3, delay_after=0.5):
        return 'normal'

    def human_scroll(page, distance=None, duration=None):
        pass

    def get_random_headers():
        return {}

    def apply_anti_detect(page, extra_headers=None):
        return {}
    
    class RateLimiter:
        def __init__(self, **kwargs):
            self.max_items_per_run = kwargs.get('max_items_per_run', 5)
            self.max_requests_per_day = kwargs.get('max_requests_per_day', 50)
            self._request_count = 0

        def should_limit(self, c):
            return min(c, self.max_items_per_run)

        def can_request(self):
            return self._request_count < self.max_requests_per_day

        def record_request(self):
            self._request_count += 1

        def remaining_requests(self):
            return max(0, self.max_requests_per_day - self._request_count)

        def get_delay(self):
            import random as _r
            return _r.uniform(2, 5)


if __name__ == "__main__":
    # 自检：打印关键配置信息
    log("=" * 50)
    log("dmp_common.py 自检")
    log("=" * 50)
    log(f"_SCRIPT_DIR: {_SCRIPT_DIR}")
    log(f"ASSETS_DATA_FILE: {Config.ASSETS_DATA_FILE}")
    log(f"FLOW_DATA_FILE: {Config.FLOW_DATA_FILE}")
    log(f"ITEM_DATA_FILE: {Config.ITEM_DATA_FILE}")
    log(f"DEBUG_DIR: {Config.DEBUG_DIR}")
    log(f"USER_DATA_DIR: {Config.USER_DATA_DIR}")
    log(f"ACCOUNT_FILE: {Config.ACCOUNT_FILE}")
    log(f"ITEM_IDS count: {len(Config.ITEM_IDS)}")
    log(f"HAS_ANTI_DETECT: {HAS_ANTI_DETECT}")
    
    # 测试账号读取
    u, p = read_account()
    log(f"Account: {u}, Password: {'*' * len(p) if p else 'None'}")
    
    # 测试日期函数
    log(f"Today CSV format: {format_date_for_csv(datetime.now())}")
    log(f"T-2: {format_date_for_csv(datetime.now() - timedelta(days=2))}")
    
    log("=" * 50)
    log("自检完成 ✓")
