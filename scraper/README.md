# DMP 数据采集项目

> 芙清旗舰店达摩盘（DMP）数据自动采集工具
> 最后更新：2026-06-07

---

## 项目概述

从千牛后台自动抓取三类数据，用于运营决策：

| 数据类型 | 脚本 | 数据文件 | 目标日期 | 说明 |
|----------|------|----------|----------|------|
| 资产诊断 | `dmp_scraper.py` | `data2.csv` | T-1（昨天） | AIPL 7阶段人群资产总量 |
| 流转数据 | `dmp_flow_scraper.py` | `data.csv` | T-2（前天） | 发现→至爱 7大人群流转漏斗 |
| 单品洞察 | `dmp_item_insight_scraper.py` | `data3.csv` | 每日 | 14个核心商品的每日资产数据 |

**技术栈**：Python 3 + Playwright（浏览器自动化）

---

## 快速开始

```bash
# 进入核心目录
cd scraper/core

# 交互式菜单（推荐）
./run.sh

# 直接运行指定模块
python3 dmp_master.py --assets      # 仅资产诊断
python3 dmp_master.py --flow        # 仅流转数据
python3 dmp_master.py --items       # 仅单品洞察
python3 dmp_master.py               # 运行所有模块
```

---

## 目录结构

```
scraper/
├── CLAUDE.md                          ← AI 操作手册
├── README.md                          ← 你正在读的文件
├── KB-数据采集-SPA接口拦截.md          ← 知识库
├── .env.example                       ← 环境变量示例
├── requirements.txt                   ← Python 依赖
├── START.sh                           ← 快速启动脚本
├── CLEANUP_FINAL.md                   ← 清理完成说明
├── core/                              ← 核心脚本
│   ├── dmp_master.py                 ← 统一入口
│   ├── dmp_common.py                 ← 公共模块
│   ├── dmp_scraper.py                ← 资产诊断抓取
│   ├── dmp_flow_scraper.py           ← 流转数据抓取
│   ├── dmp_item_insight_scraper.py   ← 单品洞察抓取
│   ├── anti_detect.py                ← 反检测模块
│   ├── sanity_check.py               ← 数据质量检查
│   ├── run.sh                        ← 交互式菜单
│   ├── account.txt                   ← 千牛账号密码（⚠️ 不要泄露）
│   ├── data.csv                      ← 流转数据（⚠️ 只追加不覆盖）
│   ├── data2.csv                     ← 资产诊断数据
│   ├── data3.csv                     ← 单品洞察数据
│   ├── config/                       ← 配置目录
│   ├── BUGFIX_2026-04-06.md          ← Bug 修复报告
│   ├── MEMO_2026-05-26.md            ← 改动记录
│   ├── MEMO_2026-06-01.md            ← 改动记录
│   └── MEMO_2026-06-02.md            ← 改动记录
├── chrome_profile/                    ← 浏览器配置（⚠️ 不要删除！）
├── .learnings/                        ← 经验日志
└── workflows/                         ← 工作流
    ├── dmp-daily-run.js              ← 每日数据采集
    ├── dmp-data-sync.js              ← 数据同步
    ├── dmp-data-fix.js               ← 数据修复
    ├── dmp-data-verify.js            ← 数据验证
    └── dmp-monitor.js                ← 监控告警
```

---

## 文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| AI 操作手册 | `CLAUDE.md` | 项目约束、修改决策树、已知问题 |
| 项目说明 | `README.md` | 项目概述和快速开始 |
| SPA 拦截知识库 | `KB-数据采集-SPA接口拦截.md` | Network 拦截方法论 |
| Bug 修复报告 | `core/BUGFIX_2026-04-06.md` | 新增人群数据为0的修复 |
| 最新备忘 | `core/MEMO_2026-05-26.md` | 最近的修改记录 |
| 经验日志 | `.learnings/LEARNINGS.md` | 技术发现和最佳实践 |
| 错误日志 | `.learnings/ERRORS.md` | 已知错误和修复记录 |
| 功能需求 | `.learnings/FEATURE_REQUESTS.md` | 待实现功能 |
| 工作流指南 | `workflows/README.md` | 工作流使用说明 |

---

## 关键约束

### 文件操作

- CSV 数据文件：**只追加不覆盖**
- `chrome_profile/`：**绝对禁止删除**
- `account.txt`：**不要泄露**

### 代码修改

- 修改 `dmp_common.py` 前确认所有 import 依赖
- 修改 `Config.ITEM_IDS` 必须同步更新商品ID文档
- 用中文标签定位元素，不要用随机 class 名

### 增量逻辑

所有模块都是增量模式：
1. 读取现有 CSV → 2. 计算缺失日期 → 3. 只补缺失的数据

**绝对不能**：
- 重写整个 CSV 文件
- 删除已有日期的数据行
- 跳过缺失日期检测直接抓取

---

## 验证项目

**验证步骤**：
1. 确保 `chrome_profile/` 存在且登录态有效
2. 运行 `python3 dmp_master.py --assets` 验证资产诊断
3. 运行 `python3 dmp_master.py --flow` 验证流转数据
4. 运行 `python3 dmp_master.py --items` 验证单品洞察
5. 检查 `data.csv`, `data2.csv`, `data3.csv` 是否正常生成

---

## 常见问题

### 登录失效？

手动打开 Chrome 重新登录千牛 → cookie 自动保存到 chrome_profile/

### 抓取失败？

1. 检查 `chrome_profile/` 是否存在
2. 检查登录态是否有效
3. 检查 `.learnings/ERRORS.md` 中是否有已知问题

### CSV 数据异常？

1. 检查是否有多余的空行
2. 检查日期格式是否一致

---

*此文件由 AI 维护*
