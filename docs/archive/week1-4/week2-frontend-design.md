# Week 2 前端设计文档：RFM 模型与 618 人群包导出

> **⚠️ 文档状态**：已废弃（Vue3 迁移完成）
> - Streamlit 前端已完全迁移至 Vue3（`frontend-vue3/`）
> - 原 `frontend/` 目录已删除，Streamlit 代码不再适用
> - 业务逻辑（RFM计算、分层、618策略）仍然有效，仅前端实现方式变更
> - 如需参考交互设计，请访问 `frontend-vue3/src/views/` 对应页面
>
> **设计目标**：为芙清 CRM 构建 RFM 客户分层界面及 618 大促人群包导出能力
> **对接角色**：rfm-calculations（RFM计算）、rfm-segmentation-strategy（RFM分层与运营策略）
> **完成日期**：2026-03-31（文档废弃：2026-04-16）

---

## 1. 页面布局方案

### 推荐：Tab 页设计（非左侧导航）

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Tab 页**（推荐） | 一屏掌握全局、切屏快、代码易维护 | Tab 过多时拥挤 |
| 左侧导航 | 适合多页面、扩展性强 | 需路由/状态管理、切换慢 |

**选择理由**：RFM 分析本身是一个完整工作流（分布→分层→策略→导出），Tab 页更适合这种线性流程，且 Streamlit 原生支持 `st.tabs()`。

### Tab 结构

```
[总览] [RFM分布] [八象限分析] [618策略] [人群导出]
```

| Tab | 核心内容 |
|-----|---------|
| 总览 | R/F/M 三维度分布概览、关键指标卡片 |
| RFM分布 | 3D散点图、热力图、直方图 |
| 八象限分析 | 矩阵图、象限明细表 |
| 618策略 | 各象限运营策略、大促专项提示 |
| 人群导出 | 人群包配置、导出预览、下载按钮 |

---

## 2. RFM 分布图表设计

### 2.1 推荐图表组合

#### (1) 3D 散点图（R × F × M）
- **图表类型**：`plotly.express.scatter_3d`
- **用途**：直观展示用户在 R/F/M 三个维度上的综合分布
- **颜色编码**：按象限着色（8种颜色）
- **交互**：可旋转、缩放、悬停显示用户详情

#### (2) 热力图（R × F 矩阵）
- **图表类型**：`plotly.graph_objects.Heatmap`
- **用途**：展示 R-F 组合的用户密度
- **颜色**：从浅蓝（低密度）到深红（高密度）
- **悬停**：显示该组合的用户数、GMV 贡献

#### (3) 分布直方图
- **R/F/M 各一个**：展示各维度得分的分布
- **叠加参考线**：标记中位数、均值阈值位置

### 2.2 图表代码框架

```python
import plotly.express as px
import plotly.graph_objects as go

def plot_rfm_3d(df_rfm):
    """3D散点图：R×F×M"""
    fig = px.scatter_3d(
        df_rfm,
        x='r_score', y='f_score', z='m_score',
        color='segment',
        symbol='segment',
        title="RFM 3D 分布（按象限着色）"
    )
    fig.update_layout(scene=dict(xaxis_title='R(最近)', yaxis_title='F(频率)', zaxis_title='M(金额)'))
    return fig

def plot_rf_heatmap(df_rfm):
    """热力图：R×F 用户密度"""
    pivot = df_rfm.groupby(['r_tier', 'f_tier']).size().reset_index(name='count')
    # pivot table for heatmap...
    fig = go.Figure(data=go.Heatmap(...))
    return fig
```

---

## 3. 八象限可视化方案

### 3.1 象限矩阵图

```
         高频消费
           ↑
     重要发展 | 重要保持
  左─────────┼─────────右
     重要挽回 | 重要价值
           ↓
        低频消费
    ← 最近消费    最近消费 →
```

**实现方式**：`plotly.graph_objects.Figure` + `add_shape()` + 文字标注

### 3.2 象限颜色编码

| 象限 | 颜色 | 说明 |
|------|------|------|
| 重要价值 | `#2E7D32` 绿 | 高R高F高M，主力客户 |
| 重要保持 | `#1565C0` 蓝 | 低R高F高M，维系对象 |
| 重要发展 | `#F57C00` 橙 | 高R低F高M，潜力客户 |
| 重要挽回 | `#C62828` 红 | 高R低F低M，流失风险 |
| 一般价值 | `#78909C` 灰 | 低R高F低M |
| 一般发展 | `#AB47BC` 紫 | 高R低F低M |
| 一般保持 | `#26A69A` 青 | 低R高F低M |
| 一般挽回 | `#8D6E63` 棕 | 低R低F低M，沉睡用户 |

---

## 4. 交互设计

### 4.1 用户可配置的阈值

| 配置项 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| R阈值 | 中位数 | 0-100 | 最近消费天数得分 |
| F阈值 | 中位数 | 0-100 | 消费频率得分 |
| M阈值 | 中位数 | 0-100 | 消费金额得分 |
| 618专属人群 | 按规则 | - | 高R高M低F（加购/领券未购） |

**交互方式**：侧边栏 Slider + "应用阈值" 按钮（防止频繁刷新）

### 4.2 实时更新 vs 按钮触发

- **分布图表**：实时更新（数据量可控）
- **象限明细表**：按钮触发（避免 1399万 用户级查询超时）
- **导出功能**：按钮触发 + 进度条

---

## 5. 618 人群包 Excel 导出设计

### 5.1 导出字段清单

| 字段名 | 来源 | 说明 |
|--------|------|------|
| user_id | orders.user_id | 用户唯一标识 |
| user_nickname | orders.user_nickname | 用户昵称（脱敏） |
| r_score | RFM计算 | 最近消费得分 (1-5) |
| f_score | RFM计算 | 消费频率得分 (1-5) |
| m_score | RFM计算 | 消费金额得分 (1-5) |
| rfm_segment | RFM分层 | 象限名称 |
| rfm_segment_code | RFM分层 | 象限代码 (1-8) |
| total_amount | RFM计算 | 累计GMV |
| order_count | RFM计算 | 累计订单数 |
| last_order_date | RFM计算 | 最近下单日期 |
| province | orders.province | 省份（投放定向用） |
| channel | orders.channel | 渠道来源 |
| is_618_target | 规则判断 | 是否为618目标人群 |
| 618_action | 建议动作 | 618大促建议操作 |

### 5.2 Excel 格式要求

```
Sheet1: 人群包总览（全部用户，可筛选）
Sheet2: 重要价值（高R高F高M，VIP用户）
Sheet3: 重要挽回（流失风险用户）
Sheet4: 618目标人群（高潜加购用户）
...
```

**格式规范**：
- 第1行冻结（列标题）
- A1 插入筛选器（自动筛选）
- 象限列条件格式（颜色标记，8种颜色）
- `is_618_target=1` 的行高亮（黄色背景）
- 列宽自适应（中文列名自动调整）

### 5.3 文件命名规范

```
芙清CRM_618人群包_{YYYYMMDD}_{HHMMSS}.xlsx
示例：芙清CRM_618人群包_20260601_143022.xlsx
```

---

## 6. 运营策略展示设计

### 6.1 象限策略卡片

每个象限展示：
- **象限名称 + 颜色标识**
- **用户规模**：X 人（占总量 X%）
- **GMV贡献**：¥X（占总GMV X%）
- **核心特征**：2-3句话描述
- **运营建议**：3-5条具体动作

### 6.2 618 大促专项提示

**设计形式**：页面顶部 Banner + 侧边栏 618 专区

**内容**：
- 618目标人群规模预估
- 各象限在618的转化策略差异
- 预热期/正式期/返场期的差异化动作

### 6.3 策略展示组件

```python
def render_segment_card(segment_name, color, user_count, gmv_contribution, features, actions):
    """渲染单个象限策略卡片"""
    import streamlit as st
    st.markdown(f"""
    <div style="border-left: 5px solid {color}; padding: 10px; margin: 10px 0;">
        <h4>{segment_name}</h4>
        <p>👥 用户规模：{user_count:,} (占比 {占比}%)</p>
        <p>💰 GMV贡献：¥{gmv_contribution:,.0f} (贡献 {贡献率}%)</p>
        <p>📝 特征：{features}</p>
        <p>🎯 运营动作：{actions}</p>
    </div>
    """, unsafe_allow_html=True)
```

---

## 7. 性能考量

### 7.1 1399万用户级别的挑战

| 问题 | 解决方案 |
|------|---------|
| 查询超时 | 预计算 + 分页加载 |
| 界面卡顿 | 采样展示（随机1%样本做图表） |
| 导出慢 | 后台线程 + `st.progress` |

### 7.2 推荐架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vue3 前端 (frontend-vue3)             │
├─────────────────────────────────────────────────────────┤
│  缓存层 (Pinia store + 内存缓存)                          │
│  ├── RFM分布汇总表（每日凌晨刷新）                        │
│  ├── 象限用户计数（实时）                                 │
│  └── 象限明细表（按需加载，用户ID分页）                    │
├─────────────────────────────────────────────────────────┤
│  DuckDB 查询层                                          │
│  ├── 预聚合表：rfm_user_summary（约50万行）               │
│  └── 实时查询：当日新订单的增量RFM更新                    │
└─────────────────────────────────────────────────────────┘
```

### 7.3 缓存机制

```python
@st.cache_data(ttl=3600)  # 1小时过期
def get_rfm_summary():
    """获取RFM汇总（每小时刷新）"""
    ...

@st.cache_data(ttl=86400)  # 每日刷新
def get_rfm_distribution():
    """获取RFM分布（每日刷新）"""
    ...
```

### 7.4 刷新频率建议

| 数据类型 | 推荐刷新频率 | 说明 |
|---------|------------|------|
| RFM象限分布 | 每日凌晨 | 批量计算，离线跑 |
| 当日实时预览 | 手动刷新 | 点击按钮触发 |
| 人群包导出 | 手动触发 | 618前按需导出 |

---

## 8. 前端代码设计

### 8.1 文件结构

```
frontend-vue3/src/
├── views/
│   └── RfmView.vue           # RFM分析页面
├── components/
│   ├── rfm_charts.vue         # RFM图表组件（ECharts）
│   ├── rfm_strategy.vue       # 象限策略卡片组件
│   └── rfm_export.vue        # 导出功能组件
├── api/
│   └── rfm.ts                # RFM API调用层
└── stores/
    └── rfm.ts                # RFM Pinia状态管理
```

### 8.2 与现有 app.py 的集成

**方案：多页签（推荐）**

在 `app.py` 侧边栏添加页面导航：

```python
# app.py 侧边栏
st.sidebar.title("导航")
page = st.sidebar.radio(
    "选择页面",
    ["Week 1: 核心指标", "Week 2: RFM分析", "618人群包导出"]
)

if page == "Week 1: 核心指标":
    # 现有 Week 1 代码...
elif page == "Week 2: RFM分析":
    from rfm_page import render_rfm_page
    render_rfm_page()
elif page == "618人群包导出":
    from components.rfm_export import render_export_page
    render_export_page()
```

### 8.3 组件复用建议

| 组件 | 复用场景 | 依赖 |
|------|---------|------|
| `rfm_charts.py` | Tab2/Tab3 | rfm_data.py |
| `rfm_strategy.py` | Tab4 | rfm_data.py + strategy_data.py |
| `rfm_export.py` | Tab5 | rfm_data.py |

---

## 9. 对接接口（与 rfm-calculations 协商）

### 9.1 需要的函数接口

```python
# frontend/utils/rfm_data.py

def get_rfm_scores(start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取用户RFM得分
    返回：user_id, r_score, f_score, m_score
    """

def get_rfm_segments(thresholds: dict) -> pd.DataFrame:
    """
    获取用户象限划分
    返回：user_id, rfm_segment, rfm_segment_code
    """

def get_rfm_summary() -> dict:
    """
    获取RFM汇总指标
    返回：各象限用户数、GMV贡献、占比
    """
```

### 9.2 数据流

```
rfm_calculations 计算层
       ↓ (预聚合表)
rfm_data.py 数据获取层
       ↓ (st.cache_data)
rfm_page.py 页面渲染层
       ↓
前端组件 (charts / strategy / export)
```

---

## 10. 618 大促专项功能

### 10.1 618 目标人群定义

| 人群 | 定义 | 运营价值 |
|------|------|---------|
| 加购未购 | 近30天加购但无购买，R≤30天 | 高转化潜力 |
| 领券未购 | 领取优惠券但未使用 | 刺激首购 |
| 高活沉睡 | 30-90天未购买，但F≥3 | 召回目标 |
| 高价值流失 | R>60天，但M≥5000 | VIP召回 |

### 10.2 618 导出特殊字段

```python
# 618大促专项字段
df_export['618人群类型'] = df_export.apply(classify_618_target, axis=1)
df_export['建议618动作'] = df_export['618人群类型'].map(ACTION_MAP)
df_export['618优惠券优先级'] = df_export['618人群类型'].map(COUPON_PRIORITY)
```

---

## 11. 验收标准

- [ ] Tab 页正常切换，无报错
- [ ] RFM 3D 散点图可交互（旋转/缩放/悬停）
- [ ] 热力图显示正确（R×F 矩阵）
- [ ] 八象限矩阵图颜色正确
- [ ] 阈值调整按钮触发更新
- [ ] 导出 Excel 格式正确（筛选/颜色标记）
- [ ] 1399万用户级别不超时（采样方案）
- [ ] 618 人群包字段完整

---

## 12. 后续工作

1. **rfm_calculations** 完成 RFM 得分计算函数
2. **rfm_segmentation_strategy** 完成象限运营策略设计
3. 前端对接数据接口，完成页面开发
4. 集成测试 + 性能调优

---

*设计人：rfm-frontend-export*
*日期：2026-03-31*
