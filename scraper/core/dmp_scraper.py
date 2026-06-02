#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMP资产诊断数据抓取模块
流程：千牛登录 -> 跳转达摩盘资产诊断页面 -> 提取各层级人群资产数据

被 dmp_master.py 的 run_assets_module() 调用：
    data = dmp_scraper.fetch_data_for_date(page, date_obj)
    dmp_scraper.append_to_csv(Config.ASSETS_DATA_FILE, date_obj, data)

重建时间: 2026-04-05
重建依据：从 dmp_master.py 第74/77行的调用接口反推
          + dmp_flow_scraper.py 的 append_flow_to_csv 作为结构参考
"""

import csv
import os
import sys
import time
import random

# 导入公共模块
from dmp_common import (
    log, Config, detect_encoding, format_date_for_csv,
    parse_number
)

# 导入反检测（可选）
# [修复] anti_detect 模块未定义 HAS_ANTI_DETECT，原代码 import HAS_ANTI_DETECT 导致
# 整个 try 块因 ImportError 失败，human_delay/human_delay_normal 永远使用 fallback。
# 改为分开导入：先导入函数，再单独设置标志位。
try:
    from anti_detect import human_delay, human_delay_normal
    _HAS_AD = True  # anti_detect 模块可用
except ImportError:
    _HAS_AD = False

    def human_delay(a, b):
        t = random.uniform(a, b)
        time.sleep(t)
        return t

    def human_delay_normal(m, s, mn=None, mx=None):
        d = random.gauss(m, s)
        if mn:
            d = max(mn, d)
        if mx:
            d = min(mx, d)
        time.sleep(d)
        return d


# ============ 资产诊断数据抓取（Y轴锚定 + DOM 提取）============
def fetch_data_for_date(page, date_obj):
    """
    抓取指定日期的资产诊断数据（人群资产总量）

    达摩盘资产诊断页面URL格式：
    https://dmp.taobao.com/index_new.html#!/assets

    数据结构（返回列表）：
    index 0: TOTAL (人群资产总量)
    index 1: 发现 人数
    index 2: 种草 人数
    index 3: 互动 人数
    index 4: 行动 人数
    index 5: 首购 人数
    index 6: 复购 人数
    index 7: 至爱 人数

    Args:
        page: 已登录的Playwright页面对象
        date_obj: datetime.date 对象，目标日期

    Returns:
        list: [TOTAL, 发现, 种草, 互动, 行动, 首购, 复购, 至爱]
               失败返回 None 或长度不足5的列表
    """
    debug_dir = Config.DEBUG_DIR
    os.makedirs(debug_dir, exist_ok=True)

    target_str = date_obj.strftime('%Y-%m-%d')
    spm = Config.DMP_SPM
    route = Config.DMP_ROUTE_ASSETS
    url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?bizDate={target_str}"

    log(f"访问资产诊断页面: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)

        # 验证页面是否正常加载（检测404/错误页）
        page_title = page.title() or ""
        page_content = page.content() or ""
        if "404" in page_title or "not found" in page_title.lower() or "找不到" in page_content:
            log("⚠️ 检测到页面404，尝试备用URL格式...")
            fallback_url = f"https://dmp.taobao.com/index_new.html{Config.DMP_ROUTE_ASSETS}?bizDate={target_str}"
            log(f"访问备用URL: {fallback_url}")
            page.goto(fallback_url, wait_until="domcontentloaded", timeout=120000)

        # ========== 智能等待：轮询检测大数字元素 ==========
        num_appeared = False
        max_wait = 15
        waited = 0
        while waited < max_wait:
            try:
                num_count = page.evaluate("""() => {
                    const allEls = document.querySelectorAll('*');
                    let found = 0;
                    for (const el of allEls) {
                        const text = (el.innerText || '').trim().replace(/,/g, '');
                        if (/^\\d{6,}$/.test(text) && text.length <= 15) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.height < 200) found++;
                        }
                    }
                    return found;
                }""")
                if num_count >= 5:
                    log(f"✅ 数据已渲染（检测到{num_count}个大数字，{waited}s）")
                    num_appeared = True
                    break
            except Exception:
                pass
            time.sleep(1)
            waited += 1

        if not num_appeared:
            if _HAS_AD:
                extra_delay = human_delay_normal(5, 1.5, 3, 8)
            else:
                extra_delay = random.uniform(5, 8)
            log(f"⚠️ 数字未渲染，继续等待 {extra_delay:.1f}s...")
            time.sleep(extra_delay)

        # 反检测延迟
        if _HAS_AD:
            delay = human_delay_normal(3, 1, 2, 5)
        else:
            delay = random.uniform(2, 4)
        time.sleep(delay)

        # 截图保存
        screenshot_path = os.path.join(debug_dir, f"assets_{date_obj}.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            log(f"已保存资产诊断截图: {screenshot_path}")
        except Exception:
            pass

        # 提取资产数据（Y轴锚定法 + 水平排序兜底）
        data = extract_assets_data(page, date_obj)

        if data and len(data) >= 5:
            total_val = data[0] if data else 0
            log(f"✓ {date_obj} 资产诊断数据抓取成功: TOTAL={total_val:,}")
            return data
        else:
            log(f"✗ {date_obj} 资产诊断数据不足 (len={len(data) if data else 0})")
            return None

    except Exception as e:
        log(f"抓取资产诊断数据失败 {date_obj}: {e}")
        import traceback
        log(traceback.format_exc())
        return None


def extract_assets_data(page, date_obj):
    """
    从资产诊断页面提取各层级人数数据
    
    策略（2026-05-26重写）：
    1. 收集所有数字候选（支持带逗号格式如'121,515,086'）
    2. 通过TreeWalker找到各层级标签文字
    3. 找标签下方最近的大数字（Y轴对齐法）
    4. 如果标签法失败，用水平位置排序兜底
    
    Args:
        page: Playwright页面对象
        date_obj: 日期对象（用于日志）
    
    Returns:
        list: [TOTAL, 发现, 种草, 互动, 行动, 首购, 复购, 至爱]
               或 None（提取失败时）
    """
    level_order = ['TOTAL', 'faxian', 'zhongcao', 'hudong', 'xingdong',
                   'shougou', 'fugou', 'zhiai', 'xinzeng']

    try:
        js_result = page.evaluate("""() => {
            const result = {};
            
            // 标签 -> key 映射（支持中英文混合页面）
            const nameMap = {
                'TOTAL': ['TOTAL', '资产总量', '总量', '总资产', '全部'],
                'faxian': ['Discover', '发现'],
                'zhongcao': ['Engage', '种草'],
                'hudong': ['Enthuse', '互动'],
                'xingdong': ['Perform', '行动'],
                'shougou': ['Initial', '首购'],
                'fugou': ['Numerous', '复购'],
                'zhiai': ['Keen', '至爱'],
                'xinzeng': ['新增']
            };
            
            // ========== 步骤1: 收集所有数字候选（支持带逗号格式） ==========
            const numCandidates = [];
            const _allEls = document.querySelectorAll('*');
            let checked = 0;
            for (const el of _allEls) {
                checked++;
                if (checked > 50000) break;
                const rawText = (el.innerText || '').trim();
                // 去掉逗号后匹配：'121,515,086' -> '121515086'
                const text = rawText.replace(/,/g, '');
                // 匹配：去掉逗号后是6位以上纯数字（资产级别）
                if (/^\\d{6,}$/.test(text) && text.length <= 15) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.height < 200) {
                        numCandidates.push({
                            value: parseInt(text, 10),
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2,
                            rawText: rawText
                        });
                    }
                }
            }
            
            // 去重（同一个数字可能出现在相邻的div和strong里）
            const seen = new Set();
            const uniqueNums = [];
            for (const c of numCandidates) {
                if (!seen.has(c.value)) {
                    seen.add(c.value);
                    uniqueNums.push(c);
                }
            }
            
            console.log('[资产] 检查了', checked, '个元素，数字候选:', uniqueNums.length);
            for (const n of uniqueNums) {
                console.log('[资产-数字]', n.value, 'x:', Math.round(n.x), 'y:', Math.round(n.y));
            }
            
            // ========== 步骤2: 按X坐标从左到右排序数字 ==========
            uniqueNums.sort((a, b) => a.x - b.x);
            
            // ========== 步骤3: 找标签 -> 找标签下方最近的数字 ==========
            // 观察：标签在y≈370，数字在y=388，同列对齐
            for (const [key, names] of Object.entries(nameMap)) {
                if (result[key]) continue;
                
                let bestMatch = null;
                let bestDistY = Infinity;
                
                for (const name of names) {
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null, false
                    );
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        // 标签名必须是文本节点的主要内容（支持混排如'TOTAL 资产总量'）
                        if (text.includes(name) && text.length < 50) {
                            const parent = node.parentElement;
                            if (parent) {
                                const rect = parent.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0 && rect.height < 100) {
                                    const anchorX = rect.left + rect.width / 2;
                                    const anchorY = rect.top + rect.height;
                                    // 找同一列（x坐标接近）且在标签下方（y更大）的数字
                                    for (const cand of uniqueNums) {
                                        const dx = Math.abs(cand.x - anchorX);
                                        const dy = cand.y - anchorY;
                                        // X偏移<50px（同一列），Y正向（下方），取最近的
                                        if (dx < 80 && dy > 0 && dy < bestDistY) {
                                            bestDistY = dy;
                                            bestMatch = cand;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                if (bestMatch) {
                    result[key] = bestMatch.value;
                    console.log('[资产-锚定]', key, '=', bestMatch.value,
                                '(x:', Math.round(bestMatch.x), 'y:', Math.round(bestMatch.y),
                                'dy:', Math.round(bestDistY), ')');
                }
            }
            
            // ========== 步骤4: 兜底 - 水平位置顺序分配 ==========
            const foundCount = Object.keys(result).length;
            console.log('[资产] 锚定法找到', foundCount, '个字段');
            
            if (foundCount < 5 && uniqueNums.length >= 5) {
                console.log('[资产-兜底] 使用水平位置顺序分配...');
                // 按X从左到右取前N个数字，依次分配给缺失的key
                const orderedKeys = ['TOTAL', 'faxian', 'zhongcao', 'hudong', 'xingdong',
                                    'shougou', 'fugou', 'zhiai', 'xinzeng'];
                let numIdx = 0;
                for (const key of orderedKeys) {
                    if (!result[key] && numIdx < uniqueNums.length) {
                        result[key] = uniqueNums[numIdx].value;
                        console.log('[资产-兜底]', key, '=', uniqueNums[numIdx].value,
                                    'x:', Math.round(uniqueNums[numIdx].x));
                        numIdx++;
                    }
                }
            }
            
            return result;
        }""")
        
        log(f"资产诊断提取原始结果: {js_result}")
        
        # 组装结果列表
        result_list = []
        for key in level_order:
            val = js_result.get(key, 0) if js_result else 0
            if val is None:
                val = 0
            result_list.append(parse_number(val))
        
        # ========== 优化2: 智能重试机制 ==========
        # 过滤掉全0的情况（说明页面没加载完），最多重试3次
        non_zero_count = sum(1 for v in result_list if v > 0)
        retry_count = 0
        max_retries = 3
        while non_zero_count < 3 and retry_count < max_retries:
            retry_count += 1
            # 递增等待时间：8s, 12s, 16s（更激进）
            wait_time = 6 + retry_count * 4
            log(f"⚠️ 资产诊断有效数据太少 ({non_zero_count}/{len(result_list)})，等待{wait_time}秒后重试 ({retry_count}/{max_retries})...")
            
            # ========== 优化3: 智能等待 - 轮询检测数字元素是否出现 ==========
            # 检查页面上是否有6位以上的大数字（资产数据特征）
            elapsed = 0
            interval = 2
            while elapsed < wait_time:
                try:
                    num_count = page.evaluate("""() => {
                        const allEls = document.querySelectorAll('*');
                        let found = 0;
                        for (const el of allEls) {
                            const text = (el.innerText || '').trim().replace(/,/g, '');
                            if (/^\\d{6,}$/.test(text) && text.length <= 15) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0 && rect.height < 200) found++;
                            }
                        }
                        return found;
                    }""")
                    if num_count >= 5:
                        log(f"✅ 重试前检测到{num_count}个大数字，页面已准备好")
                        break
                except Exception:
                    pass
                time.sleep(interval)
                elapsed += interval
            
            try:
                js_result = page.evaluate("""
                (() => {
                    const result = {};
                    const nameMap = {
                        'TOTAL': ['TOTAL', '资产总量', '总量', '总资产', '全部'],
                        'faxian': ['Discover', '发现'],
                        'zhongcao': ['Engage', '种草'],
                        'hudong': ['Enthuse', '互动'],
                        'xingdong': ['Perform', '行动'],
                        'shougou': ['Initial', '首购'],
                        'fugou': ['Numerous', '复购'],
                        'zhiai': ['Keen', '至爱'],
                        'xinzeng': ['新增']
                    };
                    // 收集数字候选（支持带逗号格式）
                    const numCandidates = [];
                    const seen = new Set();
                    const allEls = document.querySelectorAll('*');
                    let checked = 0;
                    for (const el of allEls) {
                        checked++;
                        if (checked > 50000) break;
                        const rawText = (el.innerText || '').trim();
                        const text = rawText.replace(/,/g, '');
                        if (/^\\d{6,}$/.test(text) && text.length <= 15) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.height < 200) {
                                if (!seen.has(text)) {
                                    seen.add(text);
                                    numCandidates.push({value: parseInt(text, 10), x: rect.left + rect.width / 2, y: rect.top + rect.height / 2});
                                }
                            }
                        }
                    }
                    numCandidates.sort((a, b) => a.x - b.x);
                    
                    // 锚定法：找标签下方最近的数字
                    for (const [key, names] of Object.entries(nameMap)) {
                        if (result[key]) continue;
                        let bestMatch = null;
                        let bestDistY = Infinity;
                        for (const name of names) {
                            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                            let node;
                            while (node = walker.nextNode()) {
                                const text = node.textContent.trim();
                                if (text.includes(name) && text.length < 50) {
                                    const parent = node.parentElement;
                                    if (parent) {
                                        const rect = parent.getBoundingClientRect();
                                        if (rect.width > 0 && rect.height > 0 && rect.height < 100) {
                                            const anchorX = rect.left + rect.width / 2;
                                            const anchorY = rect.top + rect.height;
                                            for (const cand of numCandidates) {
                                                const dx = Math.abs(cand.x - anchorX);
                                                const dy = cand.y - anchorY;
                                                if (dx < 80 && dy > 0 && dy < bestDistY) {
                                                    bestDistY = dy;
                                                    bestMatch = cand;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        if (bestMatch) result[key] = bestMatch.value;
                    }
                    
                    // 兜底：水平位置顺序分配
                    const foundCount = Object.keys(result).length;
                    if (foundCount < 5 && numCandidates.length >= 5) {
                        const orderedKeys = ['TOTAL', 'faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai', 'xinzeng'];
                        let numIdx = 0;
                        for (const key of orderedKeys) {
                            if (!result[key] && numIdx < numCandidates.length) {
                                result[key] = numCandidates[numIdx].value;
                                numIdx++;
                            }
                        }
                    }
                    return result;
                })()
            """)
                result_list = []
                for key in level_order:
                    val = js_result.get(key, 0) if js_result else 0
                    if val is None:
                        val = 0
                    result_list.append(parse_number(val))
                non_zero_count = sum(1 for v in result_list if v > 0)
            except Exception as e:
                error_msg = str(e).lower()
                if 'closed' in error_msg or 'target' in error_msg:
                    log("⚠️ 重试期间浏览器上下文已崩溃，中断资产诊断并向上传播")
                    raise  # 重新抛出 TargetClosedError，让上层处理
                else:
                    log(f"⚠️ 重试 evaluate 异常: {e}，继续下次重试")
                    continue  # 非崩溃错误，继续下一轮重试
        
        # 循环结束后判断最终结果
        if non_zero_count < 3:
            log(f"⚠️ 重试{max_retries}次后资产诊断有效数据仍然太少 ({non_zero_count}/{len(result_list)})，页面可能未加载完成或数据结构变化")
            return None
        log(f"✅ 资产诊断数据获取成功 ({non_zero_count}个有效字段)")
        
        log(f"资产诊断最终数据: {result_list}")
        return result_list
        
    except Exception as e:
        log(f"提取资产诊断数据失败: {e}")
        import traceback
        log(traceback.format_exc())
        return None


# ============ CSV写入 ============
def append_to_csv(csv_file, date_obj, data):
    """
    追加单日资产诊断数据到CSV文件

    CSV格式（与前端data.js期望格式一致）：
    time,TOTAL资产总量,Discover发现,Engage种草,Enthuse互动,Perform行动,Initial首购,Numerous复购,Keen至爱

    Args:
        csv_file: data2.csv路径
        date_obj: 日期对象
        data: fetch_data_for_date返回的列表 [TOTAL, 发现, ..., 至爱]

    Returns:
        bool: 是否成功写入
    """
    if not data or len(data) < 4:
        log("数据不足，跳过写入")
        return False

    fieldnames = ['time', 'TOTAL资产总量', 'Discover发现', 'Engage种草', 'Enthuse互动',
                  'Perform行动', 'Initial首购', 'Numerous复购', 'Keen至爱']
    
    # 读取现有数据（用于去重）
    existing_rows = []
    encoding = detect_encoding(csv_file)
    date_str = format_date_for_csv(date_obj)

    # 数据校验：TOTAL <= 0 说明未刷新
    total_val = parse_number(data[0]) if len(data) > 0 else 0
    if total_val <= 0:
        log(f"⚠️ TOTAL={total_val}，数据未刷新或异常，跳过写入")
        return False

    if os.path.exists(csv_file):
        try:
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 兼容新旧字段名：旧版用'date'，新版用'time'
                    date_col = row.get('time') or row.get('date') or ''
                    if date_col != date_str:
                        existing_rows.append(row)
        except Exception as e:
            log(f"读取现有CSV失败: {e}")

    # 构建新行
    # 确保 data 有足够的字段（不足补0）
    # 内部顺序: [TOTAL, faxian, zhongcao, hudong, xingdong, shougou, fugou, zhiai, xinzeng]
    level_order = ['TOTAL', 'faxian', 'zhongcao', 'hudong', 'xingdong',
                   'shougou', 'fugou', 'zhiai', 'xinzeng']
    while len(data) < len(level_order):
        data.append(0)

    new_row = {
        'time': date_str,
        'TOTAL资产总量': str(parse_number(data[0])) if len(data) > 0 else '0',
        'Discover发现': str(parse_number(data[1])) if len(data) > 1 else '0',
        'Engage种草': str(parse_number(data[2])) if len(data) > 2 else '0',
        'Enthuse互动': str(parse_number(data[3])) if len(data) > 3 else '0',
        'Perform行动': str(parse_number(data[4])) if len(data) > 4 else '0',
        'Initial首购': str(parse_number(data[5])) if len(data) > 5 else '0',
        'Numerous复购': str(parse_number(data[6])) if len(data) > 6 else '0',
        'Keen至爱': str(parse_number(data[7])) if len(data) > 7 else '0',
    }

    # ========== Gate: 资产诊断数据实质相同则跳过（T+1未更新）==========
    _ASSET_FIELDS = ['TOTAL资产总量', 'Discover发现', 'Engage种草', 'Enthuse互动',
                      'Perform行动', 'Initial首购', 'Numerous复购', 'Keen至爱']

    def _sv(v):
        return int(str(v).replace(',', '').strip()) if str(v).strip() else 0

    if existing_rows:
        prev_vals = [_sv(existing_rows[-1].get(f, 0)) for f in _ASSET_FIELDS]
        curr_vals = [_sv(new_row.get(f, 0)) for f in _ASSET_FIELDS]
        if prev_vals == curr_vals:
            log(f"⏭️ 资产诊断 {date_str} 与最新一条完全相同，判定为T+1未更新，跳过写入")
            return True
        # 变化率<0.01%也视为无新数据
        all_within = all(
            abs(p - c) / max(abs(p), abs(c), 1) <= 0.0001
            for p, c in zip(prev_vals, curr_vals)
        )
        if all_within:
            log(f"⏭️ 资产诊断 {date_str} 变化率<0.01%，判定为T+1噪声，跳过写入")
            return True

    # 合并并写回
    all_rows = existing_rows + [new_row]
    
    # 确保目录存在
    file_dir = os.path.dirname(csv_file)
    if file_dir:
        os.makedirs(file_dir, exist_ok=True)
    
    try:
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        
        log(f"已保存 {date_str} 的资产诊断数据到CSV (TOTAL={new_row['TOTAL资产总量']})")
        return True
    except Exception as e:
        log(f"保存资产诊断CSV失败: {e}")
        return False


# ============ 主程序（独立运行支持）============
def main():
    """独立运行入口（供直接执行 python dmp_scraper.py 使用）"""
    from dmp_common import read_account, BrowserManager, login_qianniu, get_missing_dates_assets
    
    log("=" * 50)
    log("达摩盘资产诊断数据抓取工具启动")
    log("=" * 50)
    
    # 读取账号
    username, password = read_account()
    if not username or not password:
        log("错误：无法读取账号密码")
        return False
    log(f"读取到账号: {username}")
    
    # 检查需要补齐的日期
    missing_dates = get_missing_dates_assets(Config.ASSETS_DATA_FILE)
    
    if not missing_dates:
        log("资产诊断数据已是最新，无需补齐")
        return True
    
    log(f"需要补齐 {len(missing_dates)} 天: {[str(d) for d in missing_dates]}")
    
    success_count = 0
    fail_dates = []
    
    # 启动浏览器
    with BrowserManager(headless=False) as browser:
        page = browser.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})
        
        try:
            # 登录
            log("\n" + "=" * 50)
            log("步骤1：登录千牛/淘宝")
            log("=" * 50)
            
            if not login_qianniu(page, username, password, debug_name="assets_login"):
                log("千牛登录失败，退出")
                return False
            
            log("\\n✓ 登录成功！")
            
            # 循环抓取
            for date_obj in missing_dates:
                log(f"\\n{'='*40}")
                log(f"正在处理: {date_obj}")
                log(f"{'='*40}")
                
                try:
                    data = fetch_data_for_date(page, date_obj)
                    
                    if data and len(data) >= 4:
                        if append_to_csv(Config.ASSETS_DATA_FILE, date_obj, data):
                            success_count += 1
                            log(f"✓ {date_obj} 数据抓取成功")
                        else:
                            log(f"✗ {date_obj} 数据保存失败")
                            fail_dates.append(date_obj)
                    else:
                        log(f"✗ {date_obj} 数据抓取失败或数据不足")
                        fail_dates.append(date_obj)
                    
                    # 间隔
                    if date_obj != missing_dates[-1]:
                        time.sleep(3)
                        
                except Exception as e:
                    log(f"✗ {date_obj} 抓取出错: {e}")
                    fail_dates.append(date_obj)
                    
        except Exception as e:
            log(f"运行出错: {e}")
            import traceback
            log(traceback.format_exc())
    
    log(f"\\n资产诊断完成: 成功 {success_count}/{len(missing_dates)}")
    if fail_dates:
        log(f"失败日期: {[str(d) for d in fail_dates]}")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
