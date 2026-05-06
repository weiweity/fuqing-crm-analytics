# Week 4 技术实现计划

**版本**: v1.0
**日期**: 2026-04-02
**作者**: Week 4 PM
**状态**: 初稿待评审

---

## 1. 技术架构

### 1.1 整体架构

```
frontend/
├── pages/
│   ├── profile_page.py      # 人群画像主页面（新增）
│   ├── geo_page.py          # 地域分析子页面（新增）
│   └── category_page.py     # 品类分析子页面（新增）
├── components/
│   ├── geo_charts.py        # 地域图表组件（新增）
│   └── category_charts.py   # 品类图表组件（新增）
└── utils/
    ├── geo_data.py          # 地域数据获取（新增）
    ├── category_data.py     # 品类数据获取（新增）
    └── export_data.py       # 导出数据获取（新增）

backend/
└── services/
    ├── geo_service.py       # 地域分析服务（新增）
    ├── category_service.py  # 品类分析服务（新增）
    ├── export_service.py    # PPT导出服务（新增）
    └── report_service.py    # 报告汇总服务（新增）
```

### 1.2 目录结构

```
docs/week4/
├── HANDOFF.md               # Week 3 交接文档
├── requirements.md          # 业务需求规格
├── api-contract.md          # API 接口契约
└── tech-plan.md            # 技术实现计划（本文档）
```

---

## 2. 服务层实现

### 2.1 geo_service.py

**文件路径**：`backend/services/geo_service.py`

**功能**：
- `get_geo_distribution()`: 获取地域分布
- `get_geo_segment_matrix()`: 获取地域×象限交叉分析
- `get_geo_trend()`: 获取地域趋势

**核心 SQL 模式**：

```python
def _get_base_order_query(date: str, lookback_days: int) -> str:
    """
    地域分析基础查询

    SQL 模式：
    1. 禁止 SELECT *
    2. 使用 CTE 而非嵌套子查询
    3. 参数化查询
    """
    return """
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    filtered_orders AS (
        SELECT
            o.user_id,
            o.province,
            o.city,
            o.actual_amount,
            o.order_id,
            o.order_time
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.order_time >= p.start_date
          AND o.order_time < DATE(?) + INTERVAL '1' DAY
          AND o.order_status LIKE '%成功%'
          AND o.actual_amount > 0
    )
    """
```

**关键实现点**：

1. **省份/城市切换**：通过 `level` 参数控制
   - level="省份": 按 `province` 聚合
   - level="城市": 按 `province, city` 聚合，取 TOP 50

2. **RFM 象限筛选**：复用 `flow_service.py` 中的 `_compute_user_segments_sql()`
   - 先计算用户象限，再 JOIN 订单数据

3. **NULL 处理**：城市为空的订单标记为"未知城市"

---

### 2.2 category_service.py

**文件路径**：`backend/services/category_service.py`

**功能**：
- `get_category_distribution()`: 获取品类分布
- `get_category_segment_matrix()`: 获取品类×象限交叉分析
- `get_category_user_profile()`: 获取品类用户画像

**核心 SQL 模式**：

```python
def _get_base_order_query_with_spu(date: str, lookback_days: int) -> str:
    """
    品类分析基础查询

    注意：SPU 字段可能为 NULL，需处理
    """
    return """
    WITH base_params AS (
        SELECT
            DATE(?) AS analysis_date,
            DATE(?) AS start_date
    ),
    filtered_orders AS (
        SELECT
            o.user_id,
            o.order_id,
            o.actual_amount,
            o.order_time,
            COALESCE(o.spu_category, '未知') AS spu_category,
            COALESCE(o.spu_type, '未知') AS spu_type,
            COALESCE(o.spu_tier, '未知') AS spu_tier,
            COALESCE(o.spu_product_class, '未知') AS spu_product_class,
            COALESCE(o.spu_product_subclass, '未知') AS spu_product_subclass,
            COALESCE(o.spu_cosmetic, '未知') AS spu_cosmetic,
            COALESCE(o.spu_spec, '未知') AS spu_spec
        FROM orders o
        CROSS JOIN base_params p
        WHERE o.order_time >= p.start_date
          AND o.order_time < DATE(?) + INTERVAL '1' DAY
          AND o.order_status LIKE '%成功%'
          AND o.actual_amount > 0
    )
    """
```

**关键实现点**：

1. **SPU 字段 NULL 处理**：使用 `COALESCE(field, '未知')`
2. **层级切换**：通过 `level` 参数控制聚合维度
3. **与 RFM 象限 JOIN**：复用 `_compute_user_segments_sql()` 计算结果

---

### 2.3 export_service.py

**文件路径**：`backend/services/export_service.py`

**功能**：
- `generate_ppt_report()`: 生成 PPT 报告
- `get_available_templates()`: 获取模板列表

**PPT 生成流程**：

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RgbColor
from pptx.enum.text import PP_ALIGN

def generate_ppt_report(
    report_type: str,
    start_date: str,
    end_date: str,
    modules: List[str],
    template: str = "default"
) -> Dict[str, Any]:
    """
    生成 PPT 报告

    步骤：
    1. 收集报告数据（调用 report_service）
    2. 创建 Presentation 对象
    3. 按模块顺序添加幻灯片
    4. 保存到临时目录
    5. 返回下载链接
    """
    # 1. 收集数据
    summary = get_report_summary(start_date, end_date)

    # 2. 创建 PPT
    prs = Presentation()

    # 3. 按模块添加幻灯片
    if "cover" in modules:
        _add_cover_slide(prs, summary)

    if "metrics" in modules:
        _add_metrics_slide(prs, summary)

    if "segments" in modules:
        _add_segments_slide(prs, summary)

    if "geo" in modules:
        _add_geo_slide(prs, summary)

    if "category" in modules:
        _add_category_slide(prs, summary)

    if "actions" in modules:
        _add_actions_slide(prs, summary)

    # 4. 保存
    report_id = f"rpt_{end_date.replace('-', '')}"
    output_dir = Path(PROJECT_ROOT) / "data" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_id}.pptx"
    prs.save(str(output_path))

    # 5. 返回
    return {
        "report_id": report_id,
        "file_name": f"芙清CRM月度复盘报告_{end_date[:7]}.pptx",
        "download_url": f"/api/v1/export/download/{report_id}"
    }
```

**关键实现点**：

1. **模板系统**：支持 default/insights 两种模板
2. **模块化**：每个模块对应一个幻灯片生成函数
3. **图表嵌入**：Plotly 图表转为图片后嵌入 PPT
4. **临时文件**：PPT 保存在 `data/exports/` 目录

---

### 2.4 report_service.py

**文件路径**：`backend/services/report_service.py`

**功能**：
- `get_report_summary()`: 获取报告汇总数据

**数据来源**：
- 复用 `metrics_service.py` 的核心指标
- 复用 `flow_service.py` 的象限分布
- 复用 `geo_service.py` 的地域数据
- 复用 `category_service.py` 的品类数据

---

## 3. 前端实现

### 3.1 profile_page.py（人群画像主页）

**功能**：地域分析和品类分析的入口页面

**布局**：
```
┌─────────────────────────────────────────────────────────┐
│  🔍 人群画像分析                                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐                       │
│  │  📍 地域分析 │  │  📦 品类分析 │  ┌─────────────┐     │
│  └─────────────┘  └─────────────┘  │  📊 报告导出 │     │
│                                     └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

**导航模式**：与 cohort_page.py 一致，使用侧边栏按钮导航

---

### 3.2 geo_page.py（地域分析页面）

**功能**：地域分布热力图、省份/城市排行榜、交叉分析

**子导航**：
1. 地域分布：地图热力图 + TOP 10 排行榜
2. 象限交叉：堆叠柱状图 + 交叉表格
3. 趋势分析：折线图

**Session State Keys**：
```python
{
    "geo_from_date": date,
    "geo_to_date": date,
    "geo_level": "省份",  # 省份/城市
    "geo_segment_filter": None,  # 1-9 或 None
    "geo_nav_selected": "distribution"
}
```

---

### 3.3 category_page.py（品类分析页面）

**功能**：品类分布图、品类×象限交叉、品类画像

**子导航**：
1. 品类分布：环形图 + TOP 10 排行榜
2. 象限交叉：堆叠柱状图 + 交叉表格
3. 品类画像：用户特征雷达图

**Session State Keys**：
```python
{
    "cat_from_date": date,
    "cat_to_date": date,
    "cat_level": "category",  # category/type/class/subclass
    "cat_segment_filter": None,
    "cat_nav_selected": "distribution"
}
```

---

### 3.4 export_page.py（导出页面）

**功能**：PPT 报告生成和下载

**布局**：
```
┌─────────────────────────────────────────────────────────┐
│  📊 报告导出                                              │
├─────────────────────────────────────────────────────────┤
│  报告类型: [月度复盘报告 ▼]                                │
│  时间范围: [2026-03-01] → [2026-03-31]                   │
│                                                          │
│  包含模块:                                                │
│  ☑ 封面  ☑ 核心指标  ☑ 人群象限  ☑ 地域分析              │
│  ☑ 品类分析  ☐ 行动建议                                   │
│                                                          │
│  [预览报告]  [导出 PPT]                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 数据层函数规范

### 4.1 geo_data.py

```python
from datetime import date

def _normalize_date(date_val):
    """将 date 或 datetime 转换为 YYYY-MM-DD 字符串"""
    if isinstance(date_val, date):
        return date_val.strftime("%Y-%m-%d")
    return str(date_val)

@st.cache_data(ttl=3600)
def get_geo_distribution(from_date, to_date, lookback_days=90, level="省份", top_n=50, segment_id=None):
    from backend.services.geo_service import get_geo_distribution as svc
    from_date_str = _normalize_date(from_date)
    to_date_str = _normalize_date(to_date)
    return svc(date=to_date_str, lookback_days=lookback_days, level=level, top_n=top_n, segment_id=segment_id)

@st.cache_data(ttl=3600)
def get_geo_segment_matrix(from_date, to_date, lookback_days=90, top_n=10):
    from backend.services.geo_service import get_geo_segment_matrix as svc
    from_date_str = _normalize_date(from_date)
    to_date_str = _normalize_date(to_date)
    return svc(date=to_date_str, lookback_days=lookback_days, top_n=top_n)

@st.cache_data(ttl=3600)
def get_geo_trend(start_date, end_date, lookback_days=90, top_n=5):
    from backend.services.geo_service import get_geo_trend as svc
    start_str = _normalize_date(start_date)
    end_str = _normalize_date(end_date)
    return svc(start_date=start_str, end_date=end_str, lookback_days=lookback_days, top_n=top_n)
```

### 4.2 category_data.py

```python
@st.cache_data(ttl=3600)
def get_category_distribution(from_date, to_date, lookback_days=90, level="category", segment_id=None):
    from backend.services.category_service import get_category_distribution as svc
    from_date_str = _normalize_date(from_date)
    to_date_str = _normalize_date(to_date)
    return svc(date=to_date_str, lookback_days=lookback_days, level=level, segment_id=segment_id)

@st.cache_data(ttl=3600)
def get_category_segment_matrix(from_date, to_date, lookback_days=90, level="type", top_n=10):
    from backend.services.category_service import get_category_segment_matrix as svc
    from_date_str = _normalize_date(from_date)
    to_date_str = _normalize_date(to_date)
    return svc(date=to_date_str, lookback_days=lookback_days, level=level, top_n=top_n)

@st.cache_data(ttl=3600)
def get_category_user_profile(from_date, to_date, lookback_days=90, category="护肤", type=None):
    from backend.services.category_service import get_category_user_profile as svc
    from_date_str = _normalize_date(from_date)
    to_date_str = _normalize_date(to_date)
    return svc(date=to_date_str, lookback_days=lookback_days, category=category, type=type)
```

### 4.3 export_data.py

```python
@st.cache_data(ttl=3600)
def get_report_summary(start_date, end_date, lookback_days=90):
    from backend.services.report_service import get_report_summary as svc
    start_str = _normalize_date(start_date)
    end_str = _normalize_date(end_date)
    return svc(start_date=start_str, end_date=end_str, lookback_days=lookback_days)

def generate_ppt_report(report_type, start_date, end_date, modules, template="default"):
    from backend.services.export_service import generate_ppt_report as svc
    start_str = _normalize_date(start_date)
    end_str = _normalize_date(end_date)
    return svc(report_type=report_type, start_date=start_str, end_date=end_str, modules=modules, template=template)
```

---

## 5. 图表组件

### 5.1 geo_charts.py

**图表类型**：
1. `plot_geo_map()`: 中国省份热力地图（Plotly choropleth）
2. `plot_geo_bar()`: 地域 TOP N 条形图
3. `plot_geo_segment_stacked_bar()`: 地域×象限堆叠柱状图
4. `plot_geo_trend_line()`: 地域趋势折线图

**关键实现**：
- 中国地图使用 Plotly 内置的 `china` 地理数据
- 城市级别使用散点图模式

### 5.2 category_charts.py

**图表类型**：
1. `plot_category_pie()`: 品类占比环形图
2. `plot_category_bar()`: 品类 TOP N 条形图
3. `plot_category_segment_stacked_bar()`: 品类×象限堆叠柱状图
4. `plot_category_profile_radar()`: 品类画像雷达图

---

## 6. 依赖与风险

### 6.1 依赖项

| 依赖 | 版本 | 用途 | 状态 |
|------|------|------|------|
| python-pptx | ≥0.6.21 | PPT 生成 | 需安装 |
| plotly | ≥5.0 | 地图热力图 | 已安装 |
| duckdb | ≥0.9 | 数据库查询 | 已安装 |

### 6.2 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 省份/城市字段缺失率高 | 中 | 中 | 使用 COALESCE 标记为"未知" |
| SPU 字段覆盖率 97% | 低 | 低 | 剩余 3% 归入"未知"品类 |
| PPT 生成性能 | 中 | 中 | 异步生成，避免超时 |
| 中国地图精度 | 低 | 低 | 使用 Plotly 内置地图数据 |

### 6.3 待确认事项

- [ ] PPT 模板是否需要定制化设计？
- [ ] 地图热力图是否需要支持城市级别？
- [ ] 是否需要支持导出 Word 报告？

---

## 7. 任务分解

### 7.1 后端任务（backend-dev）

| 任务 | 负责人 | 预计工时 | 依赖 |
|------|--------|---------|------|
| geo_service.py | backend-dev | 4h | - |
| category_service.py | backend-dev | 4h | - |
| export_service.py | backend-dev | 6h | PPT 模板 |
| report_service.py | backend-dev | 2h | 其他 service |
| API 路由注册 | backend-dev | 1h | - |

**总计**：约 17 小时

### 7.2 前端任务（frontend-dev）

| 任务 | 负责人 | 预计工时 | 依赖 |
|------|--------|---------|------|
| profile_page.py | frontend-dev | 1h | - |
| geo_page.py | frontend-dev | 4h | geo_charts.py |
| category_page.py | frontend-dev | 4h | category_charts.py |
| export_page.py | frontend-dev | 2h | export_service.py |
| geo_charts.py | frontend-dev | 3h | - |
| category_charts.py | frontend-dev | 3h | - |
| geo_data.py | frontend-dev | 1h | geo_service.py |
| category_data.py | frontend-dev | 1h | category_service.py |
| export_data.py | frontend-dev | 1h | export_service.py |

**总计**：约 20 小时

### 7.3 测试任务（qa-agent）

| 任务 | 负责人 | 预计工时 | 依赖 |
|------|--------|---------|------|
| SQL 规范审查 | qa-agent | 2h | geo/category service |
| API 接口测试 | qa-agent | 3h | 所有 service |
| 前端集成测试 | qa-agent | 3h | 前端页面 |
| PPT 导出验证 | qa-agent | 2h | export_service.py |

**总计**：约 10 小时

---

## 8. 时间计划

| 日期 | 后端 | 前端 | 测试 |
|------|------|------|------|
| 04-03 | geo_service | profile_page | - |
| 04-04 | category_service | geo_page + geo_charts | SQL 审查 |
| 04-05 | export_service | category_page + category_charts | API 测试 |
| 04-06 | report_service | export_page | 前端测试 |
| 04-07 | 联调 | 联调 | PPT 验证 |
| 04-08 | Bug 修复 | Bug 修复 | 回归测试 |
| 04-09 | 验收 | 验收 | 验收 |

---

## 9. 验收标准

### 9.1 后端验收
- [ ] geo_service.py 3 个 API 返回正确数据
- [ ] category_service.py 3 个 API 返回正确数据
- [ ] export_service.py 成功生成 .pptx 文件
- [ ] report_service.py 返回完整的汇总数据
- [ ] 所有 SQL 查询符合规范

### 9.2 前端验收
- [ ] 地图热力图正确显示中国省份分布
- [ ] 省份/城市切换正常工作
- [ ] 品类环形图正确显示占比
- [ ] PPT 导出预览和下载功能正常
- [ ] 所有 widget 使用前初始化 session_state

### 9.3 集成验收
- [ ] 地域分析和品类分析数据与 Week 1-3 口径一致
- [ ] PPT 报告数据与看板数据一致
- [ ] 无 SQL 注入风险
- [ ] 无 session_state KeyError

---

## 10. 附录

### 10.1 SPU 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| spu_category | 一级品类 | 护肤/彩妆/个护 |
| spu_type | 二级品类 | 精华/面霜/洁面 |
| spu_tier | 价格层级 | 高端/中端/低端 |
| spu_product_class | 产品系列 | 凉茶系列/其他系列 |
| spu_product_subclass | 产品子类 | 凉茶经典款/凉茶清新款 |
| spu_cosmetic | 妆类 | 特殊化妆品/普通化妆品 |
| spu_spec | 规格 | 20ml/30ml/50ml |

### 10.2 8 象限定义

| ID | 名称 | EN | 颜色 |
|----|------|-----|------|
| 1 | 钻石会员 | Diamond | #9B59B6 |
| 2 | 潜力新贵 | Rising Star | #3498DB |
| 3 | 忠实金主 | Loyal VIP | #1E8449 |
| 4 | 频次买家 | Frequent Buyer | #27AE60 |
| 5 | 豪气新客 | High-spending New | #E67E22 |
| 6 | 清新路人 | Casual Browser | #7F8C8D |
| 7 | 沉睡土豪 | Sleeping Whale | #E74C3C |
| 8 | 流失用户 | Lost Customer | #566573 |
| 9 | 其他 | Others | #BDC3C7 |
