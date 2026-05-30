# Phase 3: DuckDB 原生读 xlsx 替代 openpyxl

## 1. 问题定义

### 当前状态
- ETL pipeline 使用 `openpyxl + pandas` 读取 xlsx 文件
- 全量 ETL 耗时 2-3 小时（10M+ 行数据）
- 增量 ETL 理论分钟级，但 xlsx 解析仍是瓶颈
- Phase 1（事务化 + xxhash 校验和）和 Phase 2（Parquet 缓存层）已完成

### 目标
- 用 DuckDB 原生 `read_excel()` 替代 `openpyxl + pandas` 读取 xlsx
- 预期 5-10x 加速（DuckDB C++ 引擎 vs Python openpyxl）
- 内存占用更低（流式处理）
- 代码更简洁（减少 pandas 中间层）

### 验收标准
- [ ] DuckDB `read_excel()` 能正确读取所有 xlsx 文件（含复杂格式）
- [ ] 列名映射在 SQL 层完成，不经过 pandas rename
- [ ] 数据类型与现有 pipeline 一致（日期、数字、字符串）
- [ ] 全量 ETL 时间从 2-3 小时降至 < 30 分钟
- [ ] 增量 ETL 时间 < 5 分钟
- [ ] 所有现有测试通过
- [ ] 新增 DuckDB read_excel 兼容性测试

## 2. 技术方案

### 当前流程
```
xlsx → openpyxl → pandas DataFrame → 列名 rename → DuckDB INSERT
```

### 目标流程
```
xlsx → DuckDB read_excel() → SQL 列名映射 → DuckDB INSERT
```

### 关键改动点

#### 2.1 `scripts/etl/ingest.py` — 核心改动
- 替换 `pd.read_excel()` 为 `conn.execute("SELECT * FROM read_excel(?)")`
- 列名映射从 pandas rename 改为 SQL SELECT 别名
- 保持 Parquet 缓存逻辑不变（Phase 2 已完成）

#### 2.2 `scripts/etl/config.py` — 配置调整
- 新增 DuckDB read_excel 配置选项（header、sheet_name 等）
- 保留 openpyxl 作为 fallback（兼容性降级）

#### 2.3 `scripts/etl/pipeline.py` — 流程适配
- 全量/增量模式适配新的读取方式
- 错误处理：read_excel 失败时 fallback 到 openpyxl

#### 2.4 `scripts/etl/transform.py` — 类型转换
- 确保 DuckDB read_excel 输出的类型与现有 pipeline 兼容
- 日期列：DuckDB 可能返回 TIMESTAMP vs 现有 datetime
- 数字列：DuckDB 可能返回 DECIMAL vs 现有 float

### 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| DuckDB read_excel 不支持复杂格式 | 中 | 中 | 保留 openpyxl fallback |
| 列名映射差异 | 中 | 高 | SQL 别名显式映射 |
| 数据类型不一致 | 中 | 高 | 类型转换层 + 测试验证 |
| 性能不如预期 | 低 | 中 | benchmark 对比 |
| 内存占用增加 | 低 | 低 | DuckDB 流式处理通常更低 |

## 3. 实施步骤

### Step 1: 兼容性测试（预计 2 小时）
- 测试 DuckDB read_excel 能否读取现有 xlsx 文件
- 验证列名、数据类型、空值处理
- 测试复杂格式（合并单元格、多 sheet、特殊字符）

### Step 2: 实现核心读取（预计 3 小时）
- 修改 `ingest.py` 的 `load_data_files` 函数
- 实现 SQL 列名映射
- 添加 openpyxl fallback

### Step 3: 集成测试（预计 2 小时）
- 跑全量 ETL 验证数据一致性
- 对比 xlsx vs DuckDB read_excel 输出
- 跑增量 ETL 验证增量逻辑

### Step 4: 性能基准（预计 1 小时）
- 对比 openpyxl vs DuckDB read_excel 读取速度
- 测量内存占用
- 记录全量/增量 ETL 时间

### Step 5: 测试覆盖（预计 2 小时）
- 新增 DuckDB read_excel 单元测试
- 测试 fallback 机制
- 测试边界情况（空文件、损坏文件、编码问题）

## 4. 回滚方案
- 保留 openpyxl 作为默认读取方式
- DuckDB read_excel 作为可选优化（配置开关）
- 如果生产环境出问题，一行配置回退

## 5. 依赖
- DuckDB 版本需支持 `read_excel()`（需确认当前版本）
- 可能需要安装 `xlsx` 扩展（DuckDB 社区扩展）

## 6. 时间线
- 兼容性测试：Day 1
- 核心实现：Day 1-2
- 集成测试：Day 2
- 性能基准：Day 2
- 测试覆盖：Day 3
- 总计：约 3 天（10 小时 CC 时间）
