# Week 4 API 接口契约 - 人群画像

**版本**: v1.0
**日期**: 2026-04-02
**状态**: 初稿待评审

---

## 概述

本文档定义 Week 4 人群画像模块的 API 接口契约，包括：
1. 地域分析 API（3个）
2. 品类分析 API（3个）
3. PPT 导出 API（2个）
4. 报告汇总 API（1个）

**总计：9 个 API**

---

## 通用规范

### 路径前缀
- 地域分析：`/api/v1/geo/`
- 品类分析：`/api/v1/category/`
- 导出相关：`/api/v1/export/`
- 报告汇总：`/api/v1/report/`

### 请求参数规范
- 日期格式：`YYYY-MM-DD`
- 字符串参数：URL 编码
- 数字参数：直接传递

### 响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 错误码
| code | 说明 |
|------|------|
| 0 | 成功 |
| 400 | 参数错误 |
| 404 | 数据不存在 |
| 500 | 服务器内部错误 |

---

## 1. 地域分析 API

### 1.1 GET /api/v1/geo/distribution

**功能**：获取用户地域分布

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| level | string | 否 | 省份/城市，默认"省份" |
| top_n | int | 否 | 返回数量，默认 50 |
| segment_id | int | 否 | RFM 象限筛选，1-9，不传表示全部 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-03-31",
    "lookback_days": 90,
    "level": "省份",
    "total_users": 500000,
    "distribution": [
      {
        "region": "广东省",
        "user_count": 85000,
        "gmv": 15000000,
        "占比": 0.17,
        "客单价": 176.47
      },
      {
        "region": "浙江省",
        "user_count": 65000,
        "gmv": 12000000,
        "占比": 0.13,
        "客单价": 184.62
      }
    ],
    "map_data": {
      "广东": {"user_count": 85000, "gmv": 15000000},
      "浙江": {"user_count": 65000, "gmv": 12000000}
    }
  }
}
```

---

### 1.2 GET /api/v1/geo/segment

**功能**：获取地域×RFM象限交叉分析

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| top_n | int | 否 | 返回省份数量，默认 10 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-03-31",
    "lookback_days": 90,
    "segments": [
      {"id": 1, "name": "钻石会员", "en": "Diamond"},
      {"id": 2, "name": "潜力新贵", "en": "Rising Star"},
      {"id": 3, "name": "忠实金主", "en": "Loyal VIP"},
      {"id": 4, "name": "频次买家", "en": "Frequent Buyer"},
      {"id": 5, "name": "豪气新客", "en": "High-spending New"},
      {"id": 6, "name": "清新路人", "en": "Casual Browser"},
      {"id": 7, "name": "沉睡土豪", "en": "Sleeping Whale"},
      {"id": 8, "name": "流失用户", "en": "Lost Customer"},
      {"id": 9, "name": "其他", "en": "Others"}
    ],
    "cross_matrix": [
      {
        "region": "广东省",
        "segments": {
          "1": 5000,
          "2": 8000,
          "3": 12000,
          "4": 15000,
          "5": 10000,
          "6": 20000,
          "7": 5000,
          "8": 10000
        },
        "total": 85000
      }
    ],
    "summary": {
      "广东省": {"钻石会员占比": 0.059, "流失用户占比": 0.118}
    }
  }
}
```

---

### 1.3 GET /api/v1/geo/trend

**功能**：获取地域分布趋势

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 是 | 起始日期 (YYYY-MM-DD) |
| end_date | string | 是 | 终止日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| top_n | int | 否 | 返回省份数量，默认 5 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "lookback_days": 90,
    "trend_data": [
      {
        "month": "2026-01",
        "regions": {
          "广东省": {"user_count": 80000, "gmv": 14000000},
          "浙江省": {"user_count": 60000, "gmv": 11000000}
        }
      },
      {
        "month": "2026-02",
        "regions": {
          "广东省": {"user_count": 82000, "gmv": 14500000},
          "浙江省": {"user_count": 62000, "gmv": 11500000}
        }
      }
    ]
  }
}
```

---

## 2. 品类分析 API

### 2.1 GET /api/v1/category/distribution

**功能**：获取品类分布

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| level | string | 否 | 品类级别：category/type/tier/class/subclass，默认"category" |
| segment_id | int | 否 | RFM 象限筛选，1-9 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-03-31",
    "lookback_days": 90,
    "level": "category",
    "total_orders": 500000,
    "total_gmv": 80000000,
    "distribution": [
      {
        "category": "护肤",
        "order_count": 200000,
        "gmv": 35000000,
        "user_count": 150000,
        "占比": 0.40,
        "客单价": 175.00
      },
      {
        "category": "彩妆",
        "order_count": 150000,
        "gmv": 25000000,
        "user_count": 120000,
        "占比": 0.30,
        "客单价": 166.67
      }
    ]
  }
}
```

---

### 2.2 GET /api/v1/category/segment

**功能**：获取品类×RFM象限交叉分析

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| level | string | 否 | 品类级别，默认"type" |
| top_n | int | 否 | 返回数量，默认 10 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-03-31",
    "lookback_days": 90,
    "level": "type",
    "segments": [
      {"id": 1, "name": "钻石会员"},
      {"id": 2, "name": "潜力新贵"},
      {"id": 3, "name": "忠实金主"},
      {"id": 4, "name": "频次买家"},
      {"id": 5, "name": "豪气新客"},
      {"id": 6, "name": "清新路人"},
      {"id": 7, "name": "沉睡土豪"},
      {"id": 8, "name": "流失用户"},
      {"id": 9, "name": "其他"}
    ],
    "cross_matrix": [
      {
        "category": "精华",
        "segments": {
          "1": 3000,
          "2": 5000,
          "3": 8000,
          "4": 10000,
          "5": 7000,
          "6": 15000,
          "7": 3000,
          "8": 6000
        },
        "total_orders": 57000,
        "total_gmv": 15000000
      }
    ]
  }
}
```

---

### 2.3 GET /api/v1/category/user-profile

**功能**：获取品类用户画像

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |
| category | string | 否 | 一级品类，默认"护肤" |
| type | string | 否 | 二级品类，不传表示全部 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-03-31",
    "lookback_days": 90,
    "category": "护肤",
    "type": "精华",
    "user_count": 50000,
    "gmv": 15000000,
    "avg_order_amount": 300.00,
    "avg_frequency": 2.5,
    "top_regions": [
      {"region": "广东省", "user_count": 10000, "占比": 0.20},
      {"region": "浙江省", "user_count": 8000, "占比": 0.16},
      {"region": "江苏省", "user_count": 6000, "占比": 0.12}
    ],
    "hourly_distribution": {
      "0": 100, "1": 50, ..., "23": 200
    },
    "weekly_distribution": {
      "0": 5000, "1": 8000, ..., "6": 9000
    },
    "segment_distribution": {
      "1": 3000,
      "2": 5000,
      ...
    }
  }
}
```

---

## 3. PPT 导出 API

### 3.1 POST /api/v1/export/ppt

**功能**：生成 PPT 报告

**请求体**：
```json
{
  "report_type": "monthly_review",
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "modules": ["cover", "metrics", "segments", "geo", "category", "actions"],
  "template": "default"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| report_type | string | 是 | monthly_review / insights |
| start_date | string | 是 | 报告起始日期 |
| end_date | string | 是 | 报告终止日期 |
| modules | array | 否 | 包含的模块，默认全部 |
| template | string | 否 | 模板名称，默认"default" |

**modules 可选值**：
- `cover`: 封面
- `metrics`: 核心指标
- `segments`: 人群象限
- `geo`: 地域分析
- `category`: 品类分析
- `actions`: 行动建议

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "rpt_20260331",
    "file_name": "芙清CRM月度复盘报告_2026-03.pptx",
    "download_url": "/api/v1/export/download/rpt_20260331",
    "created_at": "2026-04-02 10:00:00"
  }
}
```

---

### 3.2 GET /api/v1/export/templates

**功能**：获取可用的 PPT 模板列表

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "templates": [
      {
        "id": "default",
        "name": "默认模板",
        "description": "适合月度复盘会议的标准模板",
        "pages": ["cover", "metrics", "segments", "geo", "category"]
      },
      {
        "id": "insights",
        "name": "洞察报告模板",
        "description": "适合专题分析的精简模板",
        "pages": ["cover", "metrics", "segments", "geo", "category"]
      }
    ]
  }
}
```

---

### 3.3 GET /api/v1/export/download/{report_id}

**功能**：下载生成的 PPT 文件

**路径参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| report_id | string | 报告ID |

**响应**：
- Content-Type: `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- Content-Disposition: `attachment; filename="xxx.pptx"`

---

## 4. 报告汇总 API

### 4.1 GET /api/v1/report/summary

**功能**：获取报告汇总数据（供 PPT 使用）

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 是 | 起始日期 (YYYY-MM-DD) |
| end_date | string | 是 | 终止日期 (YYYY-MM-DD) |
| lookback_days | int | 否 | 回溯天数，默认 90 |

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_period": {
      "start_date": "2026-03-01",
      "end_date": "2026-03-31"
    },
    "metrics": {
      "total_gmv": 50000000,
      "total_orders": 200000,
      "total_users": 100000,
      "new_users": 30000,
      "old_users": 70000,
      "avg_order_amount": 250.00,
      "gmv_vs_last_month": 0.15,
      "gmv_vs_last_year": 0.25
    },
    "segments": {
      "distribution": [
        {"id": 1, "name": "钻石会员", "count": 5000, "占比": 0.05, "gmv": 10000000},
        {"id": 2, "name": "潜力新贵", "count": 8000, "占比": 0.08, "gmv": 12000000}
      ],
      "flow_summary": {
        "retention_rate": 0.65,
        "upgrade_rate": 0.15,
        "downgrade_rate": 0.20
      }
    },
    "geo": {
      "top_provinces": [
        {"region": "广东省", "user_count": 20000, "gmv": 8000000, "占比": 0.20}
      ],
      "map_data": {"广东": 20000, "浙江": 15000}
    },
    "category": {
      "top_categories": [
        {"category": "护肤", "gmv": 20000000, "占比": 0.40, "order_count": 80000}
      ]
    }
  }
}
```

---

## 5. 后端 Service 层映射

| API | 后端 Service | 方法 |
|-----|--------------|------|
| GET /api/v1/geo/distribution | `geo_service.py` | `get_geo_distribution()` |
| GET /api/v1/geo/segment | `geo_service.py` | `get_geo_segment_matrix()` |
| GET /api/v1/geo/trend | `geo_service.py` | `get_geo_trend()` |
| GET /api/v1/category/distribution | `category_service.py` | `get_category_distribution()` |
| GET /api/v1/category/segment | `category_service.py` | `get_category_segment_matrix()` |
| GET /api/v1/category/user-profile | `category_service.py` | `get_category_user_profile()` |
| POST /api/v1/export/ppt | `export_service.py` | `generate_ppt_report()` |
| GET /api/v1/export/templates | `export_service.py` | `get_available_templates()` |
| GET /api/v1/report/summary | `report_service.py` | `get_report_summary()` |

---

## 6. 数据层规范

### 6.1 SQL 编写规范（必须遵循）

1. **禁止 SELECT ***：必须显式列出目标列
2. **参数化查询**：所有外部输入必须参数化
3. **日期类型处理**：统一使用 `_normalize_date()` 转换
4. **NULL 处理**：使用 `COALESCE(value, 0)` 处理空值

### 6.2 DuckDB CTE 模式

```sql
WITH base_params AS (
    SELECT
        DATE(?) AS analysis_date,
        DATE(?) AS start_date
),
filtered_orders AS (
    SELECT
        o.user_id,
        o.province,
        o.actual_amount,
        o.spu_category
    FROM orders o
    CROSS JOIN base_params p
    WHERE o.order_time >= p.start_date
      AND o.order_time < DATE(?) + INTERVAL '1' DAY
      AND o.order_status LIKE '%成功%'
)
SELECT
    province,
    COUNT(DISTINCT user_id) AS user_count,
    SUM(actual_amount) AS gmv
FROM filtered_orders
GROUP BY province
ORDER BY user_count DESC
LIMIT ?
```

---

## 7. 错误处理

### 7.1 错误响应格式

```json
{
  "code": 400,
  "message": "参数错误: date 格式不正确",
  "data": null
}
```

### 7.2 异常场景

| 场景 | 错误码 | 消息 |
|------|--------|------|
| 日期格式错误 | 400 | date 格式不正确，应为 YYYY-MM-DD |
| 日期范围超限 | 400 | 日期范围不能超过 365 天 |
| 数据不存在 | 404 | 指定时间段内无数据 |
| 数据库连接失败 | 500 | 数据库连接失败 |
| PPT 生成失败 | 500 | PPT 生成失败 |

---

## 8. 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| v1.0 | 2026-04-02 | 初稿 |
