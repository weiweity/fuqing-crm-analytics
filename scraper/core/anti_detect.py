#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
达摩盘反爬虫检测模块
提供浏览器反检测、人类行为模拟、请求头伪装等功能
"""

import random
import time
from datetime import datetime

# 尝试导入 numpy 支持正态分布
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ============ 用户代理池 ============
USER_AGENTS = [
    # Chrome 120+ (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome 120+ (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Edge 120+
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


def randomize_user_agent():
    """随机选择一个User-Agent"""
    return random.choice(USER_AGENTS)


# ============ 环境指纹固定脚本 ============
def get_environment_fingerprint_scripts():
    """
    获取环境指纹固定脚本列表
    这些脚本通过 page.add_init_script() 注入到浏览器上下文
    使浏览器指纹固定为"真实用户"特征，避免每次不同被检测

    Returns:
        list: JS脚本字符串列表
    """
    fingerprint_scripts = [
        # 1. Canvas 指纹固定
        """
        // 固定 Canvas 指纹，避免每次不同
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const ctx = originalGetContext.call(this, type, ...args);
            if (type === '2d') {
                const originalFillText = ctx.fillText;
                ctx.fillText = function(...args) {
                    // 添加微小的随机噪声，但保持一致性
                    return originalFillText.apply(this, args);
                };
            }
            return ctx;
        };
        """,

        # 2. WebGL 指纹固定
        """
        // 固定 WebGL 参数
        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {
            if (param === 37445) return 'Intel Inc.'; // UNMASKED_VENDOR
            if (param === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER
            return originalGetParameter.call(this, param);
        };
        """,

        # 3. Navigator 属性模拟
        """
        Object.defineProperty(navigator, 'languages', {
            get: function() { return ['zh-CN', 'zh', 'en-US', 'en']; }
        });
        Object.defineProperty(navigator, 'platform', {
            get: function() { return 'MacIntel'; }
        });
        """,

        # 4. 时区固定
        """
        Date.prototype.getTimezoneOffset = function() { return -480; }; // 北京时间
        """,
    ]

    return fingerprint_scripts


# ============ 反检测脚本注入 ============
def inject_stealth_scripts(page):
    """
    注入反检测脚本到页面
    隐藏webdriver特征、修改浏览器指纹、模拟真实浏览器行为
    
    Args:
        page: Playwright页面对象
    """
    stealth_scripts = [
        # 1. 隐藏 navigator.webdriver
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        """,
        
        # 2. 修改 Chrome 自动化特征
        """
        window.navigator.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        """,
        
        # 3. 修改 plugins 长度（真实浏览器通常有5-10个插件）
        """
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
                { name: 'Widevine Content Decryption Module', filename: 'widevinecdm' },
                { name: 'Microsoft Edge PDF Plugin', filename: 'edge-pdf-viewer' },
            ],
        });
        """,
        
        # 4. languages 已在环境指纹中统一定义（4语言），此处不再重复覆盖
        #    如需调整语言列表，请修改 get_environment_fingerprint_scripts() 中的 Navigator 部分
        
        # 5. 修改 permissions
        """
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission });
            }
            return originalQuery(parameters);
        };
        """,
        
        # 6. WebGL 渲染器信息已在环境指纹中统一定义（Intel Iris OpenGL Engine），此处不再重复覆盖
        #    如需调整渲染器名称，请修改 get_environment_fingerprint_scripts() 中的 WebGL 部分
        
        # 7. 修改 iframe contentWindow
        """
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        const originalContentWindow = iframe.contentWindow;
        iframe.remove();
        Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
            get: function() {
                return originalContentWindow;
            }
        });
        """,
        
        # 8. 修改 toString 修复
        """
        const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
        Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {
            ...elementDescriptor,
            get: function() {
                if (this.id === 'modernizr') {
                    return 1;
                }
                return elementDescriptor.get.apply(this);
            }
        });
        """,
        
        # 9. 修改 console.debug（防止通过console检测）
        """
        const originalDebug = console.debug;
        console.debug = function(...args) {
            if (args[0] && args[0].includes('webdriver')) return;
            return originalDebug.apply(console, args);
        };
        """,
        
        # 10. 修改媒体设备枚举
        """
        const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
        navigator.mediaDevices.enumerateDevices = async function() {
            const devices = await originalEnumerateDevices.call(this);
            return devices.filter(d => d.kind !== 'audiooutput');
        };
        """,
    ]
    
    for script in stealth_scripts:
        try:
            page.evaluate(script)
        except Exception:
            # 某些脚本可能在特定页面状态下失败，静默处理
            pass
    
    # 注入 CDP 级别的反检测（通过 Playwright CDP session）
    try:
        cdp_session = page.context.new_cdp_session(page)
        cdp_session.send('Page.addScriptToEvaluateOnNewDocument', {
            'source': """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            """
        })
    except Exception:
        pass  # CDP session 可能不可用（如非Chromium浏览器）


# ============ 人类行为模拟 ============
def human_delay(min_sec=2, max_sec=5):
    """
    随机延迟，模拟人类操作节奏
    
    Args:
        min_sec: 最小延迟秒数
        max_sec: 最大延迟秒数
    """
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def human_delay_normal(mean, std, min_val=None, max_val=None):
    """正态分布人类延迟，更像真实操作节奏
    
    Args:
        mean: 均值（秒）
        std: 标准差（秒）
        min_val: 最小值截断（秒）
        max_val: 最大值截断（秒）
    
    Returns:
        float: 延迟秒数
    """
    if HAS_NUMPY:
        delay = np.random.normal(mean, std)
    else:
        # Fallback: 使用 random.gauss 模拟正态分布
        delay = random.gauss(mean, std)
    
    if min_val is not None:
        delay = max(min_val, delay)
    if max_val is not None:
        delay = min(max_val, delay)
    
    time.sleep(delay)
    return delay


def human_hesitate():
    """模拟人类操作前的犹豫行为
    
    行为模式：
    - 10% 概率：鼠标悬停超过 2 秒再点（模拟犹豫）
    - 20% 概率：点击后轻微回退再重新点击（模拟怀疑）
    - 70% 概率：正常操作（无额外延迟）
    
    Returns:
        str: 行为模式标识 'hover', 'retry', 或 'normal'
    """
    rand = random.random()
    
    if rand < 0.1:
        # 10% 概率：悬停超过 2 秒
        hover_time = random.uniform(2.0, 3.5)
        time.sleep(hover_time)
        return 'hover'
    elif rand < 0.3:
        # 20% 概率：点击后回退再点（模拟怀疑后重新点击）
        # 这个需要在调用处配合 mouse.move 回退使用
        return 'retry'
    else:
        # 70% 概率：正常操作
        return 'normal'


def human_move_to(page, x, y, duration=0.5, steps=10):
    """
    模拟人类鼠标移动轨迹（贝塞尔曲线）
    
    Args:
        page: Playwright页面对象
        x: 目标X坐标
        y: 目标Y坐标
        duration: 移动持续时间（秒）
        steps: 移动步数（越多越平滑）
    """
    try:
        # 获取当前位置（如果没有则从左上角开始）
        current_x, current_y = 0, 0
        
        # 生成贝塞尔曲线轨迹点
        points = _generate_bezier_curve(current_x, current_y, x, y, steps)
        
        # 逐步移动鼠标
        for px, py in points:
            page.mouse.move(px, py)
            time.sleep(duration / steps)
        
        return True
    except Exception:
        return False


def _generate_bezier_curve(x1, y1, x2, y2, steps):
    """
    生成贝塞尔曲线轨迹点，加入随机扰动模拟人类行为
    
    Args:
        x1, y1: 起点坐标
        x2, y2: 终点坐标
        steps: 生成点数
        
    Returns:
        list: [(x, y), ...] 轨迹点列表
    """
    # 随机控制点（产生曲线弯曲）
    cp1_x = x1 + (x2 - x1) * random.uniform(0.2, 0.4) + random.uniform(-30, 30)
    cp1_y = y1 + (y2 - y1) * random.uniform(0.1, 0.3) + random.uniform(-20, 20)
    cp2_x = x1 + (x2 - x1) * random.uniform(0.6, 0.8) + random.uniform(-30, 30)
    cp2_y = y1 + (y2 - y1) * random.uniform(0.7, 0.9) + random.uniform(-20, 20)
    
    points = []
    for i in range(steps + 1):
        t = i / steps
        # 三次贝塞尔曲线公式
        x = (1-t)**3 * x1 + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * x2
        y = (1-t)**3 * y1 + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * y2
        
        # 加入微小随机扰动
        x += random.uniform(-2, 2)
        y += random.uniform(-2, 2)
        
        points.append((x, y))
    
    return points


def human_click(page, x, y, delay_before=0.3, delay_after=0.5):
    """
    模拟人类点击行为（犹豫判断 + 移动 + 短暂停留 + 点击 + 延迟）
    
    集成 human_hesitate() 模拟点击前的犹豫行为：
    - 10% 概率：悬停犹豫超过 2 秒再点
    - 20% 概率：标记为 retry（调用方可选择回退重试）
    - 70% 概率：正常操作
    
    Args:
        page: Playwright页面对象
        x: 点击X坐标
        y: 点击Y坐标
        delay_before: 点击前延迟
        delay_after: 点击后延迟
        
    Returns:
        str: 行为模式 'hover', 'retry', 或 'normal'
    """
    # 先判断本次操作的犹豫模式
    hesitate_mode = human_hesitate()
    
    # 移动到目标位置
    human_move_to(page, x, y, duration=0.4, steps=8)
    
    # hover模式下已额外延迟，正常/retry模式走原有逻辑
    if hesitate_mode != 'hover':
        # 短暂停留（人类会看一下再点）
        time.sleep(random.uniform(delay_before, delay_before + 0.3))
    
    # 点击
    page.mouse.click(x, y)
    
    # 点击后延迟
    time.sleep(random.uniform(delay_after, delay_after + 0.5))
    
    return hesitate_mode


def human_scroll(page, distance=None, duration=None):
    """
    模拟人类滚动行为（非匀速，有停顿）
    
    Args:
        page: Playwright页面对象
        distance: 滚动距离（像素），None则随机
        duration: 滚动持续时间（秒），None则随机
    """
    if distance is None:
        distance = random.randint(200, 800)
    if duration is None:
        duration = random.uniform(0.5, 1.5)
    
    # 分段滚动，模拟人类滚动节奏
    steps = random.randint(3, 6)
    step_distance = distance // steps
    
    for _ in range(steps):
        page.mouse.wheel(0, step_distance + random.randint(-50, 50))
        time.sleep(duration / steps + random.uniform(0.05, 0.2))


# ============ 请求头伪装 ============
def get_random_headers():
    """
    生成随机请求头
    
    Returns:
        dict: 请求头字典
    """
    ua = randomize_user_agent()
    
    # 从UA推断平台
    if 'Windows' in ua:
        platform = '"Windows"'
        model = '""'
        bitness = '64' if 'Win64' in ua else '32'
    elif 'Macintosh' in ua:
        platform = '"macOS"'
        model = '""'
        bitness = '64'
    else:
        platform = '"Linux"'
        model = '""'
        bitness = '64'
    
    # 提取Chrome版本号
    chrome_version = ua.split('Chrome/')[1].split(' ')[0].split('.')[0] if 'Chrome/' in ua else '120'
    
    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': f'"Chromium";v="{chrome_version}", "Not(A:Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': platform,
        'Sec-Ch-Ua-Platform-Version': '"10.0.0"' if 'Windows' in ua else '"13.0.0"',
        'Sec-Ch-Ua-Model': model,
        'Sec-Ch-Ua-Bitness': bitness,
        'Sec-Ch-Ua-Full-Version-List': f'"Chromium";v="{chrome_version}.0.0.0", "Not(A:Brand";v="24.0.0.0"',
        'Sec-Ch-Ua-Full-Version': f'"{chrome_version}.0.0.0"',
    }
    
    return headers


# ============ 频率控制 ============
class RateLimiter:
    """
    请求频率限制器
    控制每日请求数量、单次运行商品数量、请求间隔等
    """
    
    def __init__(self, max_items_per_run=None, min_delay=None, max_delay=None, max_requests_per_day=None):
        """
        Args:
            max_items_per_run: 单次运行最多抓取商品数
            min_delay: 商品间最小延迟（秒）
            max_delay: 商品间最大延迟（秒）
            max_requests_per_day: 每日最大请求数
        """
        self.max_items_per_run = max_items_per_run or 5
        self.min_delay = min_delay or 10
        self.max_delay = max_delay or 30
        self.max_requests_per_day = max_requests_per_day or 50
        
        self._today = datetime.now().strftime('%Y-%m-%d')
        self._request_count = 0
    
    def should_limit(self, current_count):
        """
        检查是否应该限制本次运行数量
        
        Args:
            current_count: 当前待抓取商品数
            
        Returns:
            int: 实际允许抓取的数量
        """
        return min(current_count, self.max_items_per_run)
    
    def get_delay(self):
        """
        获取随机延迟时间
        
        Returns:
            float: 延迟秒数
        """
        return random.uniform(self.min_delay, self.max_delay)
    
    def can_request(self):
        """
        检查今日是否还可以请求
        
        Returns:
            bool: 是否可以继续请求
        """
        # 检查日期是否变化
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self._today:
            self._today = today
            self._request_count = 0
        
        return self._request_count < self.max_requests_per_day
    
    def record_request(self):
        """记录一次请求"""
        self._request_count += 1
    
    def remaining_requests(self):
        """获取今日剩余请求数"""
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self._today:
            return self.max_requests_per_day
        return max(0, self.max_requests_per_day - self._request_count)


# ============ 便捷函数 ============
def apply_anti_detect(page, extra_headers=None):
    """
    一键应用所有反检测措施
    
    Args:
        page: Playwright页面对象
        extra_headers: 额外请求头（会合并到默认请求头）
    """
    # 注入反检测脚本
    inject_stealth_scripts(page)
    
    # 设置请求头
    headers = get_random_headers()
    if extra_headers:
        headers.update(extra_headers)
    
    # 通过CDP设置请求头（如果可用）
    try:
        cdp_session = page.context.new_cdp_session(page)
        cdp_session.send('Network.setExtraHTTPHeaders', {'headers': headers})
    except Exception:
        pass
    
    return headers
