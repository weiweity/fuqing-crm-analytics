#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
达摩盘流转数据抓取工具 V2
使用URL参数化方案：每个tab通过statusId参数直接访问，避免点击tab触发导航
"""

import csv
import time
import os
import re
from datetime import timedelta

# 尝试导入公共模块
try:
    from dmp_common import (
        log, Config, BrowserManager, read_account, login_qianniu,
        detect_encoding, parse_date, format_date_for_csv,
        get_missing_dates_flow
    )
    USING_COMMON = True
except ImportError:
    USING_COMMON = False

# statusId → crowd key 映射
STATUS_TO_KEY = {
    2001: 'faxian',    # Discover 发现
    2002: 'zhongcao',  # Engage 种草
    2003: 'hudong',    # Enthuse 互动
    2004: 'xingdong',  # Perform 行动
    2006: 'shougou',   # Initial 首购
    2007: 'fugou',    # Numerous 复购
    2008: 'zhiai',     # Keen 至爱
    0: 'xinzeng',      # New 新增（特殊：statusId=0）
}

# 层级顺序
CROWD_ORDER = ['faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai', 'xinzeng']


class FlowCollectorByAPI:
    """通过API拦截收集流转数据"""

    def __init__(self):
        self.initial = {}   # {crowd_key: initial_count}
        self.flows = {}     # {source_crowd: {target_crowd: flow_count}}

    def on_response(self, resp):
        """Playwright response 回调"""
        url = resp.url
        if 'dmp.taobao.com' not in url or 'transfer' not in url:
            return
        try:
            body = resp.json()
        except Exception:
            return

        data = body.get('data', {})

        # 判断API类型（两个不同的API，分工明确）
        is_overview = '/transfer/overview' in url          # asset/deeplink/transfer/overview → initial值
        is_transfer = '/asset/deeplink/transfer' in url and not is_overview  # asset/deeplink/transfer → 流转值

        # 从URL中提取statusId（transfer API有，overview没有）
        m = re.search(r'[?&]statusId=(\d+)', url)
        source_sid = int(m.group(1)) if m else None
        source_key = STATUS_TO_KEY.get(source_sid) if source_sid is not None else None

        # —— overview API：提供 initial 值（startDate 人群快照）——
        # 结构：data.initialAsset.list = [{statusId, uv}, ...]
        if is_overview:
            for item in data.get('initialAsset', {}).get('list', []):
                sid = item.get('statusId')
                crowd_key = STATUS_TO_KEY.get(sid)
                if crowd_key:
                    self.initial[crowd_key] = item.get('uv', 0)

        # —— transfer API：提供流转值（data.list[].uv 直接就是桑基图数值）——
        # statusId=source_sid → stay（留在当前层级）
        # statusId≠source_sid → 流转到该目标的人数
        if is_transfer and source_key:
            if source_key not in self.flows:
                self.flows[source_key] = {}
            for item in data.get('list', []):
                tid = item.get('statusId')
                tkey = STATUS_TO_KEY.get(tid)
                if not tkey:
                    continue
                uv = item.get('uv', 0)
                if tkey not in self.flows[source_key]:
                    self.flows[source_key][tkey] = 0
                self.flows[source_key][tkey] += uv

    def get_data(self):
        """返回标准化格式的数据"""
        result = {}
        for source_key in CROWD_ORDER:
            if source_key not in self.initial:
                self.initial[source_key] = 0
            row = {
                'initial': self.initial.get(source_key, 0),
                'faxian': self.flows.get(source_key, {}).get('faxian', 0),
                'zhongcao': self.flows.get(source_key, {}).get('zhongcao', 0),
                'hudong': self.flows.get(source_key, {}).get('hudong', 0),
                'xingdong': self.flows.get(source_key, {}).get('xingdong', 0),
                'shougou': self.flows.get(source_key, {}).get('shougou', 0),
                'fugou': self.flows.get(source_key, {}).get('fugou', 0),
                'zhiai': self.flows.get(source_key, {}).get('zhiai', 0),
                'xinzeng': self.flows.get(source_key, {}).get('xinzeng', 0),
            }
            result[source_key] = row
        return result


def extract_sankey_by_dom(page, source_crowd_key):
    """
    从桑基图DOM提取流转数据（修复版 - 动态位置检测）

    页面结构：
    - 右侧桑基图有7个目标节点（发现、种草、互动、行动、首购、复购、至爱）
    - 每条连接线上有一个流转值
    - 第一个值=留在当前层级

    策略：
    1. 找到所有目标label（如"发现"、"种草"等）的DOM位置
    2. 在每个label位置附近的连接线上找流转值
    3. 按label的top顺序分配流转值

    Returns:
        tuple: (initial, flows_dict)
    """
    result = page.evaluate("""
        () => {
            const targetLabels = ['发现', '种草', '互动', '行动', '首购', '复购', '至爱'];
            const allEls = document.querySelectorAll('*');

            // 第一步：找到所有目标label的位置（从上到下排序）
            const labelPositions = [];
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const text = (el.innerText || el.textContent || '').trim();
                const idx = targetLabels.findIndex(lab => text === lab || text.startsWith(lab + '人群') || text.startsWith(lab + '流转'));
                if (idx !== -1 && rect.left > 200) {  // label应该在左侧
                    labelPositions.push({ label: targetLabels[idx], top: rect.top, left: rect.left });
                }
            }
            labelPositions.sort((a, b) => a.top - b.top);

            // 第二步：在桑基图区域（left > 600）找所有大数字
            const sankeyNumbers = [];
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                if (rect.left < 600) continue;  // 桑基图在右侧

                const text = (el.innerText || el.textContent || '').trim();
                const numMatch = text.match(/^(\\d{1,3}(,\\d{3}){1,5})$/);
                if (!numMatch) continue;

                const num = parseInt(text.replace(/,/g, ''));
                if (num < 100) continue;  // 流转值通常较大

                sankeyNumbers.push({ num, top: rect.top, left: rect.left, text });
            }
            sankeyNumbers.sort((a, b) => a.top - b.top);

            // 第三步：对每个目标label，找最近的下方数字
            const flows = {};
            for (let i = 0; i < targetLabels.length; i++) {
                const targetKey = ['faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai'][i];

                if (i < labelPositions.length) {
                    const labelTop = labelPositions[i].top;
                    // 找top最接近label的大数字（在label下方30px以内）
                    let best = null;
                    let bestDist = 30;
                    for (const sn of sankeyNumbers) {
                        const dist = sn.top - labelTop;
                        if (dist >= 0 && dist < bestDist) {
                            bestDist = dist;
                            best = sn;
                        }
                    }
                    flows[targetKey] = best ? best.num : 0;
                } else {
                    flows[targetKey] = 0;
                }
            }

            // 第四步：找到桑基图左侧的源节点（当前选中阶段的initial值）
            // initial值通常在桑基图左侧，比流转值大很多
            let initial = 0;
            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                if (rect.left < 400 || rect.left > 700) continue;  // 桑基图左侧

                const text = (el.innerText || el.textContent || '').trim();
                const numMatch = text.match(/^(\\d{1,3}(,\\d{3}){1,5})$/);
                if (!numMatch) continue;

                const num = parseInt(text.replace(/,/g, ''));
                if (num > initial) {
                    initial = num;
                }
            }

            return {
                flows,
                initial,
                labelPositions,
                sankeyNumbers: sankeyNumbers.slice(0, 20)
            };
        }
    """)

    flows = result.get('flows', {})
    initial = result.get('initial', 0)

    target_keys = ['faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai']
    flows_out = {}
    for key in target_keys:
        flows_out[key] = flows.get(key, 0)

    return initial, flows_out


def extract_all_initials_from_page(page):
    """
    从页面左侧提取所有层级的initial值（修复版 - 使用label-to-number配对）

    页面结构：
    - 左侧列表显示8个层级，每个层级的标签(如"发现")和数字在一起
    - 关键修复：不再去重，而是通过找label附近的大数字来配对

    Returns:
        dict: {'faxian': 5197344, 'zhongcao': 17331343, ...}
    """
    result = page.evaluate("""
        () => {
            const crowdLabels = ['发现', '种草', '互动', '行动', '首购', '复购', '至爱', '新增'];
            const crowdKeys = ['faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai', 'xinzeng'];

            // 策略：找所有包含大数字的元素，然后看它们的父容器或邻近元素是否包含label
            const allElements = document.querySelectorAll('div, span, strong, b, p, li');

            // 建立 (label元素 → 其右侧数字) 的映射
            const labelToNumber = {};

            for (const el of allElements) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;

                const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');

                // 检查是否是label
                const labelIdx = crowdLabels.findIndex(lab => text.includes(lab));
                if (labelIdx !== -1) {
                    // 找这个label元素右侧的大数字
                    const labelRight = rect.right;  // label元素的右边界
                    const labelTop = rect.top;
                    const labelBottom = rect.bottom;

                    // 在label右侧的元素中找大数字
                    let bestNum = null;
                    let bestDist = 50;  // 距离label右边界50px内

                    for (const numEl of allElements) {
                        const numRect = numEl.getBoundingClientRect();
                        if (numRect.width === 0 || numRect.height === 0) continue;
                        if (numRect.left < labelRight) continue;  // 必须在label右边

                        const numText = (numEl.innerText || numEl.textContent || '').trim();
                        const numMatch = numText.match(/^(\\d{1,3}(,\\d{3}){1,5})$/);
                        if (!numMatch) continue;

                        const num = parseInt(numText.replace(/,/g, ''));
                        if (num < 10000) continue;

                        // 数字的垂直中心应该在label的垂直范围内
                        const numCenterY = numRect.top + numRect.height / 2;
                        if (numCenterY < labelTop - 10 || numCenterY > labelBottom + 10) continue;

                        const dist = numRect.left - labelRight;
                        if (dist < bestDist) {
                            bestDist = dist;
                            bestNum = num;
                        }
                    }

                    if (bestNum !== null) {
                        labelToNumber[crowdKeys[labelIdx]] = bestNum;
                    }
                }
            }

            // 备选方案：如果label配对失败，用右侧区域的大数字按top排序
            if (Object.keys(labelToNumber).length < 3) {
                const rightNumbers = [];
                for (const el of allElements) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    if (rect.left < 400 || rect.left > 700) continue;  // 左侧区域

                    const text = (el.innerText || el.textContent || '').trim();
                    const numMatch = text.match(/^(\\d{1,3}(,\\d{3}){1,5})$/);
                    if (!numMatch) continue;

                    const num = parseInt(text.replace(/,/g, ''));
                    if (num < 10000) continue;

                    rightNumbers.push({ num, top: rect.top });
                }

                rightNumbers.sort((a, b) => a.top - b.top);

                // 按顺序赋值（不去重！）
                const uniqueByOrder = [];
                const seen = new Set();
                for (const item of rightNumbers) {
                    if (!seen.has(item.num)) {
                        seen.add(item.num);
                        uniqueByOrder.push(item);
                    }
                }

                for (let i = 0; i < Math.min(8, uniqueByOrder.length); i++) {
                    const key = crowdKeys[i];
                    if (!(key in labelToNumber)) {
                        labelToNumber[key] = uniqueByOrder[i].num;
                    }
                }
            }

            return labelToNumber;
        }
    """)

    return result


def extract_xinzeng_flow_by_dom(page):
    """
    从DOM提取新增(xinzeng)人群的流转数据

    transfer/channel API对statusId=0不返回流转数据，
    改用DOM提取：left=1028区域，按top位置映射到各阶段

    位置映射（top值/20取整）：
      486→发现, 552→种草, 618→互动, 684→行动, 750→首购
    """
    result = page.evaluate("""
        () => {
            // 在left=1028附近区域找数字
            const allEls = document.querySelectorAll('*');
            const numbers = [];

            for (const el of allEls) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                if (rect.left < 1000 || rect.left > 1100) continue;  // left=1028附近

                const text = (el.innerText || el.textContent || '').trim();
                const numMatch = text.match(/^(\\d{1,3}(,\\d{3}){1,5})$/);
                if (!numMatch) continue;

                const num = parseInt(text.replace(/,/g, ''));
                if (num < 1000) continue;

                numbers.push({ num, top: Math.round(rect.top / 20) * 20 });
            }

            // 去重：相同num只保留一个
            const seen = new Set();
            const unique = [];
            for (const n of numbers) {
                if (!seen.has(n.num)) {
                    seen.add(n.num);
                    unique.push(n);
                }
            }

            // 按top排序
            unique.sort((a, b) => a.top - b.top);

            // 位置映射: top -> target_key
            const topToKey = {
                480: 'faxian',
                540: 'zhongcao',
                600: 'hudong',
                660: 'xingdong',
                720: 'shougou',
            };

            // 取前5个匹配的位置
            const flows = { faxian: 0, zhongcao: 0, hudong: 0, xingdong: 0, shougou: 0 };

            for (const item of unique) {
                const rounded = Math.round(item.top / 20) * 20;
                const key = topToKey[rounded];
                if (key && flows[key] === 0) {
                    flows[key] = item.num;
                }
            }

            return flows;
        }
    """)

    return result


def extract_flow_data_by_dom_v3(page, target_date, debug_dir=None):
    """
    API拦截方案：拦截两个API获取流转数据（2026-04-12最终版）

    两个API分工明确：
    - asset/deeplink/transfer/overview → initial值（startDate人群快照）
    - asset/deeplink/transfer → 桑基图流转值（data.list[].uv）
    - transfer/channel 是渠道明细表，与桑基图无关，已废弃
    """
    if debug_dir is None:
        debug_dir = Config.DEBUG_DIR

    start_date_str = target_date.strftime('%Y-%m-%d')
    biz_date_str = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

    log(f"【API方案】开始抓取 {target_date} 的流转数据...")
    log(f"  日期逻辑: {start_date_str} 的人群在 {biz_date_str} 的流转")

    # 状态ID配置
    all_status_ids = [2001, 2002, 2003, 2004, 2006, 2007, 2008, 0]
    all_crowd_keys = ['faxian', 'zhongcao', 'hudong', 'xingdong', 'shougou', 'fugou', 'zhiai', 'xinzeng']
    all_crowd_names = ['发现', '种草', '互动', '行动', '首购', '复购', '至爱', '新增']

    # 创建API拦截器
    collector = FlowCollectorByAPI()

    def on_response(resp):
        """拦截transfer相关API"""
        collector.on_response(resp)

    # 注册拦截器
    page.on('response', on_response)

    try:
        # 访问流转页面，触发API请求
        spm = Config.DMP_SPM
        route = Config.DMP_ROUTE_FLOW
        url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?statusId=2001&startDate={start_date_str}&bizDate={biz_date_str}"

        log(f"【API方案】访问页面: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        # 等待transfer API返回
        log("【API方案】等待API数据返回...")

        # 诊断：打印已拦截的数据
        collected = collector.get_data()
        log(f"【API方案】初始收集到的数据: {collected}")

            # 如果没拿到数据，尝试访问每个tab触发API
        if not collected or not collected.get('faxian', {}).get('initial'):
            log("【API方案】首次加载数据不足，尝试逐个tab触发...")

            # 访问全部8个tab（含xinzeng/statusId=0）
            for status_id, crowd_name in zip(all_status_ids, all_crowd_names):
                tab_url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?statusId={status_id}&startDate={start_date_str}&bizDate={biz_date_str}"
                page.goto(tab_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)  # 统一等2秒

        # 统一等待剩余异步响应
        log("【API方案】等待所有API响应完成...")
        time.sleep(3)

        # 再次检查
        collected = collector.get_data()
        log(f"【API方案】最终收集到的数据: {collected}")

        # xinzeng API单独处理：reload页面强制重新发起transfer请求
        if not collected.get('xinzeng', {}).get('faxian'):
            log("[API] xinzeng flow为空，强制reload页面...")
            xinzeng_url = f"{Config.DMP_BASE_URL}?spm={spm}{route}?statusId=0&startDate={start_date_str}&bizDate={biz_date_str}"
            page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(8)
            collected = collector.get_data()
            log(f"[API] xinzeng after reload: {collected.get('xinzeng')}")

        # 用API数据组装结果
        result = {}
        for crowd_key in CROWD_ORDER:
            api_data = collected.get(crowd_key, {})
            flows = {
                'faxian': api_data.get('faxian', 0),
                'zhongcao': api_data.get('zhongcao', 0),
                'hudong': api_data.get('hudong', 0),
                'xingdong': api_data.get('xingdong', 0),
                'shougou': api_data.get('shougou', 0),
                'fugou': api_data.get('fugou', 0),
                'zhiai': api_data.get('zhiai', 0),
                'xinzeng': api_data.get('xinzeng', 0),
            }

            result[crowd_key] = {
                'initial': api_data.get('initial', 0),
                **flows
            }
            log(f"【API方案】{crowd_key}: initial={result[crowd_key]['initial']:,}, 流转={flows}")

        # 截图
        if debug_dir:
            date_suffix = target_date.strftime('%Y-%m-%d')
            screenshot_path = os.path.join(debug_dir, f'api_flow_{date_suffix}.png')
            try:
                page.screenshot(path=screenshot_path)
                log(f"【API方案】截图: {screenshot_path}")
            except Exception:
                pass

        return result

    except Exception as e:
        log(f"【API方案】提取失败: {e}")
        import traceback
        log(traceback.format_exc())
        return None
    finally:
        # 注销拦截器
        page.remove_listener('response', on_response)


def fetch_flow_data_for_single_date(page, target_date):
    """兼容旧接口，内部调用新的V4 DOM方案"""
    debug_dir = Config.DEBUG_DIR if USING_COMMON else "del"
    flow_data = extract_flow_data_by_dom_v3(page, target_date, debug_dir)
    if flow_data:
        # 过滤陈旧数据：数据没更新就不写入
        if is_flow_data_stale(flow_data):
            log(f"[{target_date}] 流转数据未更新（陈旧），跳过写入")
            return "stale"
        date_str = format_date_for_csv(target_date) if USING_COMMON else target_date.strftime('%Y/%m/%d')
        append_flow_to_csv(Config.FLOW_DATA_FILE, date_str, flow_data)
        return True
    return False


def is_flow_data_stale(flow_data):
    """检查流转数据是否陈旧（未更新）。

    判断逻辑：
    1. 对于每个有 initial 人群（initial > 0），
       如果 initial == 流转给自己的值 且 流转到其他所有目标都是0，
       说明这个人流没有发生流转。
    2. 如果 xinzeng 人群的 initial == 0（没有新增），进一步确认为陈旧。

    只有当 ALL 有 initial 人群 都满足"无流转"条件，
    且 xinzeng 人群 initial == 0 时，才判定为陈旧数据。

    陈旧数据 = 数据没有更新，不需要写入表格。
    """
    # 检查 xinzeng 人群：如果 initial > 0，说明有新增，不是陈旧
    xinzeng_data = flow_data.get('xinzeng', {})
    xinzeng_initial = xinzeng_data.get('initial', 0)
    if xinzeng_initial > 0:
        return False  # 有新增，数据在更新中

    has_valid_crowd = False  # 是否有有效人群（initial > 0）
    for crowd in CROWD_ORDER:
        crowd_data = flow_data.get(crowd, {})
        initial = crowd_data.get('initial', 0)

        # 人群为0时不参与判断
        if initial == 0:
            continue

        has_valid_crowd = True
        self_flow = crowd_data.get(crowd, 0)   # 流转给自己
        other_flows_sum = sum(
            crowd_data.get(t, 0)
            for t in CROWD_ORDER
            if t != crowd
        )

        # 只要有任意人群发生了真实流转，就不是陈旧数据
        if self_flow != initial or other_flows_sum > 0:
            return False

    # 没有有效人群时，不算陈旧（让数据正常写入）
    if not has_valid_crowd:
        return False

    return True


def append_flow_to_csv(csv_file, date_str, flow_data):
    """追加流转数据到CSV"""
    fieldnames = ['date', 'crowd', 'initial', 'zhuanfaxian', 'zhuanzhongcao',
                  'zhuanhudong', 'zhuanxingdong', 'zhuanshougou', 'zhuanfugou', 'zhuanzhiai']
    _FLOW_FIELDS = ['initial', 'zhuanfaxian', 'zhuanzhongcao', 'zhuanhudong',
                     'zhuanxingdong', 'zhuanshougou', 'zhuanfugou', 'zhuanzhiai']

    def sv(v):
        return int(str(v).replace(',', '').strip()) if str(v).strip() else 0

    existing_rows = []
    encoding = detect_encoding(csv_file) if USING_COMMON else 'utf-8'

    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('date') != date_str:
                    existing_rows.append(row)

    crowds = CROWD_ORDER
    new_rows = []
    for crowd in crowds:
        crowd_data = flow_data.get(crowd, {})
        initial = crowd_data.get('initial', 0)
        new_rows.append({
            'date': date_str,
            'crowd': crowd,
            'initial': initial,
            'zhuanfaxian': crowd_data.get('faxian', 0),
            'zhuanzhongcao': crowd_data.get('zhongcao', 0),
            'zhuanhudong': crowd_data.get('hudong', 0),
            'zhuanxingdong': crowd_data.get('xingdong', 0),
            'zhuanshougou': crowd_data.get('shougou', 0),
            'zhuanfugou': crowd_data.get('fugou', 0),
            'zhuanzhiai': crowd_data.get('zhiai', 0),
        })

    # ========== Gate 3: 流转数据与上一天实质相同则跳过（兜底检查）==========
    # is_flow_data_stale() 判断"自己流转给自己100%"场景，
    # 但如果数据恰好不是100%（如99.9%自己+0.1%流转），会放行却实际与昨天几乎一样。
    # 此 Gate 对每个 crowd 与历史最新一条做实质相同判断，兜底 is_flow_data_stale()。
    if existing_rows:
        latest_by_crowd = {}
        for row in reversed(existing_rows):
            c = row.get('crowd', '')
            if c and c not in latest_by_crowd:
                latest_by_crowd[c] = row
        all_essentially_same = True
        for new_r in new_rows:
            crowd = new_r['crowd']
            prev_r = latest_by_crowd.get(crowd)
            if prev_r is None:
                all_essentially_same = False
                break
            prev_v = [sv(prev_r.get(f, 0)) for f in _FLOW_FIELDS]
            curr_v = [sv(new_r.get(f, 0)) for f in _FLOW_FIELDS]
            if prev_v != curr_v:
                # 完全不等，检查变化率
                if not all(
                    abs(p - c) / max(abs(p), abs(c), 1) <= 0.0001
                    for p, c in zip(prev_v, curr_v)
                ):
                    all_essentially_same = False
                    break
        if all_essentially_same and latest_by_crowd:
            log(f"⏭️ 流转 {date_str} 所有人群与上一天实质相同，判定为T+1未更新，跳过写入")
            return True

    all_rows = existing_rows + new_rows
    os.makedirs(os.path.dirname(csv_file) or '.', exist_ok=True)
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    log(f"已保存 {date_str} 的流转数据到CSV")


def fetch_flow_data_for_dates(page, dates):
    """抓取多个日期的流转数据"""
    success_count = 0
    stale_count = 0
    fail_count = 0
    for date_obj in dates:
        log(f"\n抓取流转数据: {date_obj}")
        try:
            result = fetch_flow_data_for_single_date(page, date_obj)
            if result is True:
                success_count += 1
                time.sleep(2)
            elif result == "stale":
                stale_count += 1
            else:
                fail_count += 1
        except Exception as e:
            log(f"流转数据抓取失败 {date_obj}: {e}")
            fail_count += 1
    return success_count, stale_count, fail_count


def get_flow_missing_dates(csv_file):
    """获取流转数据需要补齐的日期列表"""
    if USING_COMMON:
        return get_missing_dates_flow(csv_file)
    return []


def login_qianniu(page, username, password):
    """千牛/淘宝登录（公共模块版）"""
    if USING_COMMON:
        return login_qianniu(page, username, password, debug_name="flow_login")
    log("错误：dmp_common 未导入，无法登录")
    return False


def main():
    """独立运行入口"""
    log("=" * 50)
    log("达摩盘流转数据抓取工具启动")
    log("=" * 50)
    username, password = ("guest", "guest")  # placeholder
    if USING_COMMON:
        from dmp_common import read_account
        username, password = read_account()
    log("使用URL参数化方案V2抓取流转数据")

    if USING_COMMON:
        with BrowserManager(headless=False) as browser:
            page = browser.new_page()
            page.set_viewport_size({'width': 1920, 'height': 1080})
            try:
                login_qianniu(page, username, password)
                missing_dates = get_missing_dates_flow(Config.FLOW_DATA_FILE)
                if missing_dates:
                    success_count = fetch_flow_data_for_dates(page, missing_dates)
                    log(f"流转数据抓取完成: 成功 {success_count}/{len(missing_dates)}")
                else:
                    log("流转数据已是最新，无需补齐")
            except Exception as e:
                log(f"运行出错: {e}")
    return True


if __name__ == "__main__":
    main()
