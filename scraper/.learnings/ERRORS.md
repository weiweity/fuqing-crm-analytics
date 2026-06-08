# DMP 项目错误日志

> 记录所有抓取失败、选择器失效、异常退出等错误事件
> 格式：ERR-YYYYMMDD-XXX

---

## [ERR-20260608-001] 单品洞察 API 拦截在 headless=False 模式下失败

**Logged**: 2026-06-08T11:00:00Z
**Priority**: high
**Status**: resolved
**Area**: scraper/infrastructure

### Summary
`dmp_master.py` 一直用 `headless=False` (有头模式)。单品洞察模块在有头模式下,
API 拦截 `goods/view/overview/v2` 12 秒内 0 响应, 同时日期选择器找不到 (no-mxgc-calendar-datepicker),
最终 `api_data = {}` 被跳过。

### Symptom
- 23/24 商品失败, 唯一成功的是我单独用 `headless=True` 测的那个
- 错误日志: `⚠️ 12秒内未捕获到有效API数据, 尝试备用方案`
- `日期选择失败` + `API拦截未获取到有效数据, 跳过该商品`

### Root Cause
有头模式下 (可见 Chrome 窗口), 达摩盘 SPA 页面有额外的渲染/检测逻辑
(可能涉及 `window.navigator.webdriver` 在有头/无头下的不同表现),
导致 `goods/view/overview/v2` API 请求没被发出或没被 Playwright response 事件捕获。
而 `asset/deeplink/transfer` (流转) 和 DOM 解析 (资产诊断) 不受影响。

### Fix
`dmp_master.py:625, 735` `headless=False` → `True` (含浏览器崩溃重建分支)。

### Verified
- 单品洞察 15/15 商品成功 (总计 75 行 6/2→6/6 数据)
- 资产诊断/流转在无头模式也正常, 不需要分开

---

## [ERR-20260608-002] Gate 1 误判导致 6/2~6/5 单品数据被跳过

**Logged**: 2026-06-08T11:30:00Z
**Priority**: high
**Status**: resolved
**Area**: scraper/logic

### Summary
`dmp_item_insight_scraper.py` 的 Gate 1 (L2471-2482) 比较"当前抓取数据"与
"CSV 中最新一条历史数据", 变化率 <0.01% 视为 T+1 未更新, 跳过写入。
6/2~6/5 的单品数据与 6/1 实质相同 → 全部被跳过, 看板缺 4 天。

### Symptom
- `data3.csv` 最新日期 2026/6/1, 但缺 6/2~6/5
- 达摩盘页面上 6/6 显示资产总量 236,314, 与 6/1 完全相同
- Gate 1 判定: `⏭️ 商品 587053192746 2026/06/03 数据实质相同（资产总量=236,314）, 判定为T+1未更新, 跳过写入`

### Root Cause
Gate 1 设计目的: 避免写入重复的 T+1 数据 (节省 IO)。
但达摩盘单品数据变化极小 (资产总量常常几天不变), 即使有新数据也会被误判跳过。
**真实数据 = 应该是按日期区分, 不应该按数值区分**。

### Fix
删除 Gate 1 (`dmp_item_insight_scraper.py:2471-2482`) 整个数值比较逻辑。
同日去重由 `append_tocsv` 的 L2465 处理 (同商品同日期才跳过)。

### Verified
- 6/2~6/6 全部 15 商品写入 (75 行)

---

## [ERR-20260608-003] Gate 2 (Date级) 同样按数值跳过整个日期

**Logged**: 2026-06-08T11:35:00Z
**Priority**: high
**Status**: resolved
**Area**: scraper/logic

### Summary
`dmp_master.py:348-375` 的 Gate 2 (Date级) 在所有商品数据都与前一天相同时跳过整个日期。
是 Gate 1 的"日期级"版本, 同样问题, 一起修。

### Fix
删除 `dmp_master.py:348-375` 整个 Gate 2 块。

---

## [ERR-20260608-004] 达摩盘 T+1 跨日更新: 6/7 数据 6/8 下午 15:00 才出

**Logged**: 2026-06-08T11:40:00Z
**Priority**: high
**Status**: resolved (临时) + 待长期监控
**Area**: scraper/scheduling

### Summary
跑批时 (6/8 早上 10:19) 抓 6/7, 达摩盘返回的是 6/6 旧值。
对 11 个商品对比: `6/6=1398056 == 6/7=1398056` 完全相同 = 复制。

### Symptom
`data3.csv` 写入 6/7 的 15 行, 但全部是 6/6 的复制 (236,314 等)。

### Root Cause
达摩盘 T+1 但跨日: 数据 15:00 更新, 早跑批拿不到。
原本"6/7 = 今天-1 = 抓 6/7"假设数据已就绪, 实际不是。

### Fix
**临时**: 删除 6/7 虚假数据 (15 行) — `grep -v ",2026/6/7," data3.csv`
**长期**: `T_OFFSET` 环境变量 + launchd 调度 (早 9 点 T+2 保险, 下午 16 点 T+1)

### Verified
- 删除后 `data3.csv` 最新回到 2026/6/6
- T_OFFSET 测试: `os.environ['T_OFFSET']='1'` → 0 缺失, `='2'` → 0 缺失

---

## [ERR-20260608-005] 淘宝风控: 6/8 多次大批量抓取触发

**Logged**: 2026-06-08T14:00:00Z
**Priority**: high
**Status**: pending
**Area**: scraper/infrastructure

### Summary
6/8 短时间内连续跑批 3 次 (流转 + 单品 ×2), 触发达摩盘反爬风控。

### Suggested Action
- 24 小时内不要重跑 (等风控标记过期)
- `chrome_profile/` 登录态应还在 (Cookie 持久化到 SQLite)
- 下次跑批前先手动打开 Chrome 验证 cookie 有效

---

## [ERR-20260403-001] selector_engine.py Windows硬编码路径

**Logged**: 2026-04-03T18:10:00Z
**Priority**: high
**Status**: pending
**Area**: config

### Summary
selector_engine.py 第18行硬编码了 Windows 路径 `C:\Users\Tyuan\Desktop\DMP test`，导致在 Mac 上 `save_config()` 和 `_append_log()` 静默失败，选择器变更无法持久化。

### Error
```
CONFIG_DIR = r"C:\Users\Tyuan\Desktop\DMP test"
SELECTORS_FILE = os.path.join(CONFIG_DIR, "selectors.json")
```
Mac 上该路径不存在，`json.dump()` 写入时不会报错（因为不会触发 os.path.exists 检查失败的分支），但配置实际未保存。

### Context
- 文件：core/selector_engine.py 第17-20行
- 影响：AI 修复选择器后无法写入 selectors.json，下次运行仍然用旧选择器

### Suggested Fix
将 `CONFIG_DIR` 改为使用 `os.path.dirname(os.path.abspath(__file__))` 动态获取，与 dmp_common.py 的 `get_script_dir()` 保持一致。

### Metadata
- Reproducible: yes (所有非Windows环境)
- Related Files: core/selector_engine.py, core/selectors.json
- **Status**: ✅ resolved (2026-04-03)

---

## [ERR-20260403-002] 资产诊断数据全同值（弹窗干扰+距离算法）

**Logged**: 2026-04-03T18:30:00Z
**Priority**: high
**Status**: resolved
**Area**: data-quality

### Summary
第一次运行抗变异版选择器时，8个AIPL指标全部提取到相同值（28150296），原因是：
1. 达摩盘"AI识人"弹窗遮挡页面，ESC键可关闭但关闭后数据区域可能未完全刷新
2. 原始的距离算法有bug：父级搜索时取到的是"最大的数字"而非"最近的数字"

### Error
```
解析后的数据: {'initial': 28150296, 'zhuanfaxian': 28150296, 'zhuanzhongcao': 28150296, ...}
⚠️ 严重警告：所有8个指标值完全相同(28150296)！
```

### Context
- 文件：core/dmp_scraper.py extract_aipl_data()
- 触发：达摩盘资产诊断页面弹出"AI识人人群纠偏"推广弹窗

### Fix Applied (已修复)
1. **增强弹窗关闭**：增加15种关闭按钮选择器 + ESC键 + 点击外部区域三重策略
2. **距离优先算法**：找到标签元素后，收集附近所有候选数字，用欧几里得距离选**最近**的那个（而非最大的）
3. **全同值检测**：如果所有字段值完全相同，自动判定为异常并拒绝保存数据

### 验证结果
修复后 8/8 字段中有 7 个完美匹配截图值，Engage(种草)仍有偏差（离TOTAL太近被抢占了），后续可优化

### Metadata
- Related Files: core/dmp_scraper.py
