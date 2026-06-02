# DMP 项目学习日志

> 记录用户纠正、知识缺口、最佳实践发现
> 格式：LRN-YYYYMMDD-XXX

---

## [LRN-20260403-001] DMP项目技术栈全景

**Logged**: 2026-04-03T18:10:00Z
**Priority**: medium
**Status**: pending
**Area**: infra

### Summary
完成 DMP 数据抓取项目的技术栈和代码审查，记录项目全貌供后续快速上手。

### Details
项目核心架构：
- **浏览器方案**: Playwright + Chromium launch_persistent_context()（保持登录态）
- **数据源**: 千牛/淘宝达摩盘 SPA 页面（dmp.taobao.com）
- **三个模块**: 资产诊断(AIPL) / 流转数据(7层漏斗) / 单品洞察(14个商品)
- **选择器机制**: CSS类名(mxa属性) → selectors.json 配置 → current + fallbacks 兜底
- **提取策略**: 三层降级 — CSS选择器 → 语义文本匹配 → AI分析(MiniMax API)
- **增量逻辑**: 读取CSV最新日期 → 计算到T-1/T-2的缺失日期 → 只补缺失的
- **前端看板**: 纯静态HTML(index.html)，需手动同步CSV

关键文件：
- 统一入口: core/dmp_master.py (--assets/--flow/--items)
- 公共模块: core/dmp_common.py (Config/BrowserManager/login/日期/CSV工具)
- 选择器: core/selectors.json (三套: assets/flow/item)
- AI引擎: core/selector_engine.py (SelectorEngine + AIAgent)
- 语义引擎: core/semantic_selector.py
- 数据文件: core/data.csv(流转1753行) / data2.csv(资产703行) / data3.csv(单品6032行)

已知问题：
1. selector_engine.py 有 Windows 硬编码路径（Mac 上 save_config 不生效）
2. AIAgent API Key 明文写在代码中
3. 前端 CSV 需手动同步，无自动备份

### Suggested Action
按优先级逐步修复：路径硬编码 → API Key 环境化 → 自动同步脚本 → 定时任务

### Metadata
- Source: code_review
- Related Files: 所有 .py 文件, HANDOVER.md
- Tags: project-overview, architecture, dmp
- **Status**: ✅ 大部分已修复 (2026-04-03)

---

## [LRN-20260403-002] 达摩盘元素变异的应对策略

**Logged**: 2026-04-03T18:40:00Z
**Area**: architecture

### 核心发现

达摩盘页面每天更新 CSS class 名（如 `dKqGwkoRade` → 其他随机值），mxa 属性也会变。但以下东西**永远不变**：

1. **中文标签文本**："发现"、"种草"、"互动"、"资产总量" — 达摩盘不可能改这些业务术语
2. **数字字体class**：`.font-tahoma` — 达摩盘统一的数据展示字体，相对稳定
3. **DOM 位置关系**：标签和数字总是在同一个卡片容器内

### 已验证有效的策略

| 策略 | 原理 | 效果 |
|------|------|------|
| 文本关键词匹配 | 靠"发现"/"种草"等中文识别卡片 | ✅ 100%稳定 |
| 距离优先数字提取 | 找到标签后选最近的font-tahoma数字 | ✅ 7/8准确 |
| 全同值检测 | 所有字段一样时拒绝保存 | ✅ 有效拦截脏数据 |
| ESC+多重选择器关弹窗 | 弹窗遮挡是数据异常主因之一 | ✅ 有效 |

### 不要做的事
- ❌ 硬编码 `dKqGw` 开头的 class 名
- ❌ 硬编码 mxa 属性值  
- ❌ 在父级搜索时取最大数字（应取最近距离的）

### 相关文件
- core/dmp_scraper.py (extract_aipl_data - 已改造)
- core/dmp_flow_scraper.py (extract_flow_data - 已改造)

---

## [LRN-20260518-001] 单品洞察T-1数据回填未完成导致跨天抓取异常

**Logged**: 2026-05-18T14:02:00Z
**Priority**: high
**Status**: fixed
**Area**: data-quality

### Summary
单品洞察模块（模块3）在跨天抓取时（如5/17抓5/16数据），T-1数据尚未完全回填完成，导致抓到的资产总量异常偏低（跌幅>80%），但数据仍被直接写入CSV。

### Root Cause — 三层叠加

**Layer 1：SPA路由不读URL参数**
达摩盘 `item-insight` 路由完全忽略 URL 中的 `endDate` 参数（如 `?endDate=2026-05-16`），页面始终以**当天日期的前一天（T-1）**作为默认查询日期。

**Layer 2：T-1数据跨天回填未完成**
| 抓取时机 | T-1数据状态 |
|---------|------------|
| 当天 14:00 前 | ⚠️ 部分回填中，值偏低 |
| 当天 14:00 后 | ✅ 基本就绪 |

5/17 约14:02抓取时，5/16的T-1数据仍在回填，API返回未完成的中间值。

**Layer 3：代码无合理性校验**
```python
# 原代码：有数据就采纳，不校验历史合理性
api_data = api_collector.get_data()
if api_data and api_data.get('zichan_zongliang'):
    data = api_data  # ← 直接写入
```
`zichan_zongliang=44,614` 高于内置最小阈值20,000，被当作合法数据直接写入。

### Symptom
| 商品ID | 5/15正确值 | 5/16错误值 | 5/17正确值 |
|--------|-----------|-----------|-----------|
| 587051744204 | 1,002,503 | **44,614** | 1,280,971 |
| 587053192746 | 274,341 | **44,614** | 272,526 |
| 900975734816 | 141,782 | **27,555** | 28,460 |

### Fix（已实施）
在 `fetch_item_data` 中 `api_data` 检查后加入**历史数据合理性校验**：

```python
ratio = current_total / CSV前一日总量
if ratio < 0.20:  # 跌幅超过80%
    api_data = None  # 废弃当前数据，强制走Fallback
    selected_date = select_date_smart_v2(...)  # 手动选日期
```

### Related Files
- `core/dmp_item_insight_scraper.py`（修复文件）
- `core/data3.csv`（单品洞察数据）

### Key Insight
达摩盘SPA的URL参数机制让人误以为"带了日期就稳了"，但实际上T-1数据回填窗口是14:00前。任何跨天抓取场景都需要加历史合理性兜 net logic。
