# DMP 数据采集项目 — AI 操作手册

> **适用对象**：在此目录下工作的 AI 助手
> **最后更新**：2026-06-01
> **项目路径**：`/Users/hutou/Desktop/work plat/DMP_test_package/`

---

## 一、项目是什么

芙清旗舰店 **达摩盘（DMP）** 数据自动采集工具。从千牛后台自动抓取三类数据，用于运营决策。

**技术栈**：Python 3 + Playwright（浏览器自动化）

**三个模块**：

| 模块 | 脚本 | 数据文件 | 目标日期 | 说明 |
|------|------|----------|----------|------|
| 资产诊断 | `dmp_scraper.py` | `data2.csv` | T-1（昨天） | AIPL 7阶段人群资产总量 |
| 流转数据 | `dmp_flow_scraper.py` | `data.csv` | T-2（前天） | 发现→至爱 7大人群流转漏斗 |
| 单品洞察 | `dmp_item_insight_scraper.py` | `data3.csv` | 每日 | 14个核心商品的每日资产数据 |

---

## 二、目录结构

```
DMP_test_package/
├── CLAUDE.md                          ← 你正在读的文件
├── README.md                          ← 项目说明
├── KB-数据采集-SPA接口拦截.md          ← 知识库
├── core/                              ← 核心脚本（主要工作区）
│   ├── dmp_master.py                 ← 统一入口（--assets/--flow/--items）
│   ├── dmp_common.py                 ← 公共模块（Config/BrowserManager/login/CSV工具）
│   ├── dmp_scraper.py                ← 资产诊断抓取
│   ├── dmp_flow_scraper.py           ← 流转数据抓取（API拦截+DOM回退）
│   ├── dmp_item_insight_scraper.py   ← 单品洞察抓取
│   ├── anti_detect.py                ← 反检测模块（10层防御）
│   ├── run.sh                        ← 交互式菜单启动器
│   ├── account.txt                   ← 千牛账号密码（⚠️ 不要删除或泄露）
│   ├── data.csv                      ← 流转数据（⚠️ 只追加不覆盖）
│   ├── data2.csv                     ← 资产诊断数据（⚠️ 只追加不覆盖）
│   ├── data3.csv                     ← 单品洞察数据（⚠️ 只追加不覆盖）
│   ├── config/                       ← 配置目录
│   ├── completed_items.json          ← 断点续传缓存
│   ├── BUGFIX_2026-04-06.md          ← Bug 修复报告
│   └── MEMO_2026-05-26.md            ← 最近改动记录
├── chrome_profile/                    ← 浏览器配置（⚠️ 不要删除！含登录Cookie）
├── .learnings/                        ← 经验、错误、功能需求日志
└── workflows/                         ← 工作流
```

---

## 三、数据流

```
千牛后台 (dmp.taobao.com)
    │
    ▼
Playwright 浏览器（有登录态的 Chrome Profile）
    │
    ├── [资产诊断] → 页面DOM解析 → dmp_scraper.py → data2.csv
    │
    ├── [流转数据] → Network API拦截 → dmp_flow_scraper.py → data.csv
    │                    └── statusId=0 时回退到 DOM 提取
    │
    └── [单品洞察] → 页面DOM解析 → dmp_item_insight_scraper.py → data3.csv
    │
    ▼
core/data*.csv（源数据，只追加）
    │
    ▼
数据可视化（可接入其他 BI 工具）
```

---

## 四、关键约束（AI 必读）

### 4.1 文件操作约束

| 操作 | 约束 | 违反后果 |
|------|------|----------|
| 写 CSV | **只追加，不覆盖** | 数据丢失，不可恢复 |
| 修改 `dmp_common.py` | 先确认所有 import 依赖 | 三个模块全部崩溃 |
| 修改 `Config.ITEM_IDS` | 必须同步更新商品ID文档 | 数据不完整 |
| 删除 `chrome_profile/` | **绝对禁止** | 登录态丢失，需手动登录 |
| 修改 `selectors.json` | 先确认页面选择器确实已变 | 抓取失败 |

### 4.2 代码修改约束

```python
# ✅ 正确：追加写入 CSV
with open(csv_path, 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(new_row)

# ❌ 错误：覆盖写入 CSV
with open(csv_path, 'w', newline='', encoding='utf-8') as f:  # 会丢失历史数据！
    writer = csv.writer(f)
    writer.writerow(new_row)
```

```python
# ✅ 正确：用中文标签定位元素
label = page.locator('text="发现"')
value = label.locator('..').locator('.font-tahoma').inner_text()

# ❌ 错误：用随机 class 名定位（每天都会变）
value = page.locator('.dKqGwkoRade').inner_text()  # 明天就失效！
```

### 4.3 增量逻辑约束

所有模块都是**增量模式**：
1. 读取现有 CSV → 2. 计算缺失日期 → 3. 只补缺失的数据

**绝对不能**：
- 重写整个 CSV 文件
- 删除已有日期的数据行
- 跳过缺失日期检测直接抓取

### 4.4 API 拦截约束

流转数据使用 Network 拦截方式获取，有两个关键 API：

| API | URL 模式 | 用途 |
|-----|----------|------|
| overview | `asset/deeplink/transfer/overview` | 人群快照（initial 值） |
| transfer | `asset/deeplink/transfer` | 流转矩阵（桑基图数值） |

**约束**：
- 拦截器必须在 `page.goto()` 之前注册
- `statusId=0`（新增人群）的 transfer API 不返回数据，需用 DOM 回退
- `statusId` 映射：2001=发现, 2002=种草, 2003=互动, 2004=行动, 2006=首购, 2007=复购, 2008=至爱, 0=新增

---

## 五、启动方式

```bash
# 进入核心目录
cd "/Users/hutou/Desktop/work plat/DMP_test_package/core"

# 交互式菜单（推荐）
./run.sh

# 直接运行指定模块
python3 dmp_master.py --assets      # 仅资产诊断
python3 dmp_master.py --flow        # 仅流转数据
python3 dmp_master.py --items       # 仅单品洞察
python3 dmp_master.py               # 运行所有模块
```

---

## 六、修改决策树

当你需要修改此项目时，按以下流程判断：

```
需要修改什么？
│
├── 抓取失败 / 选择器失效？
│   └── 先检查 selectors.json → 如果不够，修改对应 scraper 的提取逻辑
│       └── 用中文标签 + .font-tahoma 定位，不要用随机 class 名
│
├── 新增商品ID？
│   └── 修改 dmp_common.py 的 Config.ITEM_IDS 列表
│       └── 同时更新本文件第二章的商品ID文档
│
├── CSV 数据异常？
│   └── 检查 .learnings/ERRORS.md 中是否有已知问题
│
├── 登录失效？
│   └── 手动打开 Chrome 重新登录千牛 → cookie 自动保存到 chrome_profile/
│       └── 不要删除 chrome_profile/ ！
│
└── 新功能需求？
    └── 先检查 .learnings/FEATURE_REQUESTS.md 是否已有记录
        └── 新功能不应破坏现有增量逻辑
```

---

## 七、已知问题与陷阱

### 已解决（但需注意）

| 问题 | 状态 | 注意事项 |
|------|------|----------|
| selector_engine.py Windows 硬编码路径 | ✅ 已修复 | 但如重写此文件，路径要用 `os.path.dirname(__file__)` |
| 资产诊断全同值（弹窗干扰） | ✅ 已修复 | 有全同值检测保护，但新弹窗类型可能绕过 |
| 新增人群流转数据为0 | ✅ 已修复 | statusId=0 用 DOM 回退，不要依赖 API |
| API key 明文在代码中 | ⚠️ 已知 | 如处理此问题，用环境变量方案 |

### 未解决

| 问题 | 优先级 | 说明 |
|------|--------|------|
| dmp_item_insight_scraper.py 过大 | 低 | 含未使用的死代码，可清理 |

---

## 八、验证项目

**验证步骤**：
1. 确保 `chrome_profile/` 存在且登录态有效
2. 运行 `python3 dmp_master.py --assets` 验证资产诊断
3. 运行 `python3 dmp_master.py --flow` 验证流转数据
4. 运行 `python3 dmp_master.py --items` 验证单品洞察
5. 检查 `data.csv`, `data2.csv`, `data3.csv` 是否正常生成

---

## 九、相关文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 项目说明 | `README.md` | 项目概述和快速开始 |
| SPA拦截知识库 | `KB-数据采集-SPA接口拦截.md` | Network 拦截方法论 |
| Bug修复报告 | `core/BUGFIX_2026-04-06.md` | 新增人群数据为0的修复记录 |
| 最近改动记录 | `core/MEMO_2026-05-26.md` | 最近的修改记录 |
| 经验日志 | `.learnings/LEARNINGS.md` | 技术发现和最佳实践 |
| 错误日志 | `.learnings/ERRORS.md` | 已知错误和修复记录 |
| 功能需求 | `.learnings/FEATURE_REQUESTS.md` | 待实现功能 |
| 工作流指南 | `workflows/README.md` | 工作流使用说明 |

---

## 十、工作流使用指南

### 可用工作流

| 工作流 | 文件 | 用途 |
|--------|------|------|
| 项目优化 | `workflows/dmp-optimization.js` | 执行优化计划 |
| 数据采集 | `workflows/dmp-daily-run.js` | 每日数据采集 |
| 数据同步 | `workflows/dmp-data-sync.js` | 同步数据到前端 |
| 监控告警 | `workflows/dmp-monitor.js` | 监控运行状态 |

### 运行工作流

```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "workflows/dmp-optimization.js"})
Workflow({scriptPath: "workflows/dmp-daily-run.js"})
Workflow({scriptPath: "workflows/dmp-data-sync.js"})
Workflow({scriptPath: "workflows/dmp-monitor.js"})
```

### 查看工作流状态

```bash
# 使用 /workflows 命令查看工作流状态
/workflows
```

---

*此文件由 AI 维护，最后更新：2026-06-01*
