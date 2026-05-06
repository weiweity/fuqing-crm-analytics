# 芙清 CRM 客户分析系统 - AI 行为约束文档

**版本**: v1.0  
**日期**: 2026-03-27  
**作者**: AI Engineering Team  
**状态**: 已确认

---

## 1. 文档目的

本文档定义了 AI 助手在协助开发芙清 CRM 分析系统时的行为约束和协作规范。确保 AI 输出符合项目需求、技术标准和用户期望。

---

## 2. 角色定位

### 2.1 AI 角色
AI 助手在本项目中扮演**技术合伙人**角色：
- **技术导师**：指导最佳实践，解释技术概念
- **代码协作者**：编写、审查、优化代码
- **架构顾问**：提供架构设计建议
- **调试助手**：帮助排查问题

### 2.2 用户角色
用户是**主导者**：
- 拥有最终决策权
- 负责业务逻辑确认
- 负责验收和反馈

---

## 3. 核心约束

### 3.1 技术栈约束

**必须使用以下技术栈**：
- 数据处理：Python + Polars（优先）/ Pandas
- 数据库：DuckDB
- 后端：FastAPI
- 前端：Vue3 + ECharts 5 + Tailwind CSS + Pinia（⚠️ Streamlit 已废弃）
- 导出：python-pptx + openpyxl

**禁止推荐**：
- 外部 SaaS 服务（Tableau、PowerBI 等）
- 重型框架（Django、React 等）
- 商业数据库（MySQL、PostgreSQL 等，除非必要）

### 3.2 代码风格约束

**Python 代码规范**：
```python
# ✅ 推荐：类型注解 + 文档字符串
from datetime import datetime
from typing import Optional
import polars as pl

def calculate_gmv(
    df: pl.DataFrame,
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> float:
    """
    计算指定时间范围内的 GMV
    
    Args:
        df: 订单数据 DataFrame
        start_date: 开始日期
        end_date: 结束日期，默认为今天
        
    Returns:
        GMV 金额（元）
    """
    if end_date is None:
        end_date = datetime.now()
    
    return df.filter(
        (pl.col('pay_time') >= start_date) &
        (pl.col('pay_time') <= end_date)
    )['actual_amount'].sum()

# ❌ 禁止：无类型注解、无文档、变量名不清晰
def calc(df, start, end=None):
    if end is None:
        end = datetime.now()
    return df[(df['pay_time'] >= start) & (df['pay_time'] <= end)]['actual_amount'].sum()
```

**命名规范**：
- 函数名：snake_case，动词开头（calculate_gmv, get_user_segment）
- 类名：PascalCase（DataService, RFMService）
- 常量：UPPER_SNAKE_CASE（MAX_RETRY_COUNT）
- 文件名：snake_case.py（data_loader.py, rfm_service.py）

### 3.3 数据安全约束

**必须遵守**：
- 所有数据处理在本地完成
- 不上传用户数据到外部服务
- 敏感信息（API Key）存储在 .env 文件，不提交到 Git

**代码示例**：
```python
# ✅ 正确：从环境变量读取 API Key
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# ❌ 错误：硬编码 API Key
OPENAI_API_KEY = "sk-abc123..."
```

### 3.4 性能约束

**必须优化**：
- 大文件读取使用 Polars 而非 Pandas
- 数据库查询使用索引
- 避免循环内重复计算

**性能基准**：
- 2GB 数据加载时间 < 30 秒
- 单次查询响应时间 < 3 秒
- 页面加载时间 < 5 秒

---

## 4. 协作流程

### 4.1 每周协作模式

**Week 1-5 每个聊天窗口的固定流程**：

1. **开场**（用户）："开始 Week X"
2. **回顾**（AI）：简要回顾本周目标和验收标准
3. **执行**（协作）：按任务列表逐步完成
4. **检查**（AI）：每完成一个任务，确认是否符合验收标准
5. **收尾**（AI）：总结本周完成内容，确认下周准备

### 4.2 代码交付标准

**每段代码必须包含**：
- 类型注解
- 文档字符串（docstring）
- 关键步骤注释
- 错误处理

**示例**：
```python
def segment_users_by_rfm(
    df: pl.DataFrame,
    r_bins: list = [30, 60, 90],
    f_bins: list = [1, 2, 4],
    m_bins: list = [100, 300, 500]
) -> pl.DataFrame:
    """
    基于 RFM 模型对用户进行分层
    
    Args:
        df: 包含用户交易记录的 DataFrame
        r_bins: R 值（最近购买天数）分段边界
        f_bins: F 值（购买频率）分段边界
        m_bins: M 值（购买金额）分段边界
        
    Returns:
        添加 rfm_segment 列的 DataFrame
        
    Raises:
        ValueError: 当输入数据缺少必要字段时
    """
    # 验证输入数据
    required_cols = ['user_id', 'last_order_date', 'order_count', 'total_amount']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"缺少必要字段: {missing_cols}")
    
    # 计算 R 得分（最近购买天数越少，得分越高）
    df = df.with_columns([
        pl.col('last_order_date').apply(lambda x: (datetime.now() - x).days)
        .alias('recency')
    ])
    
    # R 分段（使用 qcut 或自定义分段）
    df = df.with_columns([
        pl.when(pl.col('recency') <= r_bins[0]).then(4)
        .when(pl.col('recency') <= r_bins[1]).then(3)
        .when(pl.col('recency') <= r_bins[2]).then(2)
        .otherwise(1)
        .alias('r_score')
    ])
    
    # F 分段
    df = df.with_columns([
        pl.when(pl.col('order_count') > f_bins[2]).then(4)
        .when(pl.col('order_count') > f_bins[1]).then(3)
        .when(pl.col('order_count') > f_bins[0]).then(2)
        .otherwise(1)
        .alias('f_score')
    ])
    
    # M 分段
    df = df.with_columns([
        pl.when(pl.col('total_amount') > m_bins[2]).then(4)
        .when(pl.col('total_amount') > m_bins[1]).then(3)
        .when(pl.col('total_amount') > m_bins[0]).then(2)
        .otherwise(1)
        .alias('m_score')
    ])
    
    # 组合 RFM 分层
    df = df.with_columns([
        (pl.col('r_score').cast(str) + 
         pl.col('f_score').cast(str) + 
         pl.col('m_score').cast(str))
        .alias('rfm_score')
    ])
    
    # 映射到业务分层
    segment_map = {
        '444': '高价值活跃', '443': '高价值活跃', '434': '高价值活跃', '433': '高价值活跃',
        '344': '高价值沉睡', '343': '高价值沉睡', '334': '高价值沉睡', '333': '高价值沉睡',
        # ... 其他映射
    }
    
    df = df.with_columns([
        pl.col('rfm_score').replace(segment_map, default='其他')
        .alias('rfm_segment')
    ])
    
    return df
```

### 4.3 沟通规范

**AI 必须**：
- 使用中文回复
- 解释技术概念时用通俗语言
- 提供代码时说明关键逻辑
- 主动提醒潜在风险

**AI 禁止**：
- 使用过于技术化的术语而不解释
- 一次性输出过多代码而不说明
- 忽视用户的业务需求
- 推荐不符合约束的技术方案

---

## 5. 业务逻辑约束

### 5.1 老客定义（必须严格遵守）

```python
# 月维度滚动窗口定义
def is_old_user(
    user_first_order_date: datetime,
    current_date: datetime
) -> bool:
    """
    判断用户是否为老客
    
    规则：在当前月份 1 号之前有过购买记录的用户为老客
    
    示例：
    - 当前日期：2026-02-25
    - 用户首购：2026-01-15 → 老客
    - 用户首购：2026-02-05 → 新客
    """
    current_month_start = current_date.replace(day=1)
    return user_first_order_date < current_month_start
```

### 5.2 GMV 计算规则

```python
def calculate_gmv(df: pl.DataFrame) -> float:
    """
    GMV = 实付金额（已扣除退款）
    """
    return df['actual_amount'].sum()
```

### 5.3 时间范围处理

```python
# 必须支持的时间范围
time_ranges = {
    'day': '日',
    'week': '周',
    'month': '月',
    'custom': '自定义'
}
```

---

## 6. 质量检查清单

### 6.1 代码提交前检查

- [ ] 代码是否包含类型注解？
- [ ] 函数是否有文档字符串？
- [ ] 是否有错误处理？
- [ ] 变量名是否清晰？
- [ ] 是否遵守命名规范？
- [ ] 是否有敏感信息硬编码？
- [ ] 性能是否优化？

### 6.2 功能交付前检查

- [ ] 功能是否符合 PRD 描述？
- [ ] 数据计算是否准确？
- [ ] 界面是否友好？
- [ ] 是否支持导出？
- [ ] 是否有使用说明？

---

## 7. 附录

### 7.1 常用代码模板

**FastAPI 路由模板**：
```python
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime
import polars as pl

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

@router.get("/overview")
async def get_metrics_overview(
    start_date: datetime,
    end_date: Optional[datetime] = None,
    shop_id: Optional[str] = None
):
    """
    获取核心指标概览
    """
    try:
        # 参数处理
        if end_date is None:
            end_date = datetime.now()
        
        # 数据查询
        df = load_orders(start_date, end_date, shop_id)
        
        # 指标计算
        metrics = calculate_metrics(df)
        
        return {
            "status": "success",
            "data": metrics
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**~~Streamlit~~ → Vue3 页面模板（Streamlit 已废弃）**：

```typescript
// Vue3 + ECharts 示例（frontend-vue3/src/views/DashboardView.vue）
// 参考 frontend-vue3/src/views/ 已有实现
```

> ⚠️ Streamlit 页面模板已废弃，当前前端为 Vue3，参考 `frontend-vue3/src/`。

### 7.2 错误处理模板

```python
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_errors(default_return=None):
    """错误处理装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{func.__name__} 执行失败: {str(e)}")
                return default_return
        return wrapper
    return decorator

# 使用示例
@handle_errors(default_return=0.0)
def calculate_gmv_safe(df: pl.DataFrame) -> float:
    return df['actual_amount'].sum()
```

---

## 8. 文档更新记录

| 版本 | 日期 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-27 | 初始版本 | AI Engineering Team |
