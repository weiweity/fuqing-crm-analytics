# Ground-Truth-Lint (Sprint 17 #121)

> 强制新 contract 字段用 Pydantic Field 元数据, 防 LLM 写无 RatioField/PercentageField/PpField 的 contract.

## 1. 背景与动机

### 1.1 痛点历史

Sprint 13 ratio 治理后, 芙清 CRM 后端 ratio/pct/ppt 字段在 API 层无 validator. 服务端错值
(e.g. ratio 字段传 5.0, 应为 0-1 decimal) 没法在 API 入口拦截, 走 FastAPI 500 内部错误
路径, 暴露栈追踪, 体验差.

Sprint 14 A.1 拍板用 Pydantic v2 Annotated + Field(ge, le) 做 3 个自定义类型
(RatioField / PercentageField / PpField), 在 `backend/contracts/types.py` 集中定义.

但契约层 (16 个 contract 文件) 的标注定标率长期 < 50%, 主要原因:
- LLM 写新 contract 时倾向用裸 `float` (简单), 不会主动想到用 RatioField
- 旧 contract 重构时, 重构者通常只关注逻辑, 忘记 ratio/pct/ppt 字段加约束
- 缺 lint 工具强制, 错值走查靠人工 review (慢, 易漏)

### 1.2 Sprint 16.5 试点

Sprint 16.5 B2 试点扩到 category + metrics + health 3 contract, 找 9 mark 字段
(每个 contract 3 个) 补 Pydantic Field 元数据:

| Contract | 字段 | 原状态 | 修后状态 |
|----------|------|--------|----------|
| `category.py` | `CategoryDistributionItem.pct/penetration_rate/member_ratio` | `float = 0.0` | `"RatioField"` |
| `metrics.py` | `TrendData.member_ratios/ly_amounts/ly_member_ratios` | `List[float] = []` | `List[Annotated[float, Field(ge, le)]]` |
| `health.py` | `ValueTierDefinition/CustomerSegmentItem/TierFlowRow` 3 个 `gsv_ratio` | `float = 0.0` | `"RatioField"` |

修后错值在 API 入口 422 ValidationError, 不再 500.

### 1.3 Sprint 17 #121 治根

B2 试点找 9 字段治根, 但剩 13 contract 仍有 ~100 字段缺标. 同时缺工具层强制.

#121 ground-truth-lint: 写 AST 级别 lint, 扫描所有 contract 文件, 4 条规则
强制. 配套 #120 修完剩 13 contract + #122 把 B1+B2 模式写进 CLAUDE.md.

## 2. 4 条规则详细

### 2.1 R1: ratio 字段必须 RatioField (0-1)

**触发**: 字段名以 `_ratio` 结尾 (e.g. `member_ratio`, `old_ratio`, `gsv_ratio`).

**合规写法** (4 种):

```python
# 写法 1: 直接 Name 引用
from backend.contracts.types import RatioField
member_ratio: RatioField = 0.42

# 写法 2: Optional
from typing import Optional
old_ratio: Optional[RatioField] = None

# 写法 3: PEP 604 | None
member_ratio: RatioField | None = None

# 写法 4: 字符串前向引用 (Pydantic v2 解析 OK)
member_ratio: "RatioField" = 0.42

# 写法 5: Annotated[float, Field(ge=0, le=1)] 等价
from typing import Annotated
from pydantic import Field
member_ratio: Annotated[float, Field(ge=0.0, le=1.0)] = 0.42
```

**违规示例**:

```python
# BAD: 裸 float 无约束
member_ratio: float = 0.42
# BAD: 字段名以 _ratio 结尾但用 Annotated 没 ge/le
member_ratio: Annotated[float, Field(description="0-1")] = 0.42
```

### 2.2 R2: pct 字段必须 PercentageField (0-1B)

**触发**: 字段名以 `_pct` 结尾 (e.g. `yoy_pct`, `conversion_pct`, `growth_pct`).

**合规写法** (跟 R1 类似, 类型换 PercentageField):

```python
from backend.contracts.types import PercentageField
yoy_pct: PercentageField = 12.5
yoy_pct: Optional[PercentageField] = None
yoy_pct: PercentageField | None = None
yoy_pct: "PercentageField" = 12.5
yoy_pct: Annotated[float, Field(ge=-1_000_000_000.0, le=1_000_000_000.0)] = 12.5
```

**违规示例**:

```python
# BAD: 裸 float
yoy_pct: float = 12.5
```

**注意**: PercentageField 上限是 ±1B (Sprint 15 放宽), 兼容 `yoy_absolute *100` 后万倍异常值
(eg. 新品类从 0 涨到有量, 涨 1 万倍仍合理). 跟 Sprint 13 治理契约 0-100 严守不冲突, 0-1B
仅作为 yoy_absolute 兼容兜底.

### 2.3 R3: ppt 字段必须 PpField (-100~+100)

**触发**: 字段名以 `_ppt` 结尾 (e.g. `yoy_ppt`, `diff_ppt`, `churn_ppt`).

**合规写法** (跟 R1 类似, 类型换 PpField):

```python
from backend.contracts.types import PpField
yoy_ppt: PpField = 5.28
yoy_ppt: Optional[PpField] = None
yoy_ppt: PpField | None = None
yoy_ppt: "PpField" = 5.28
yoy_ppt: Annotated[float, Field(ge=-100.0, le=100.0)] = 5.28
```

**违规示例**:

```python
# BAD: 裸 float
yoy_ppt: float = 5.28
```

### 2.4 R4: List[X] 字段不许用字符串前向引用

**触发**: 字段类型是 `List["X"]` 或 `Optional[List["X"]]` (X 是字符串).

**为什么**: Pydantic v2 在解析 `List["RatioField"]` 时, 前向引用解析为 float,
Field 元数据丢失, **不会触发 element-wise 约束**. 越界值 (e.g. percentage=150) 不会被
Pydantic 拦截.

**合规写法** (用 List[Annotated[float, Field(ge, le)]):

```python
from typing import List, Annotated
from pydantic import Field

# GOOD: Annotated 触发 element-wise 约束
member_ratios: List[Annotated[float, Field(ge=0.0, le=100.0)]] = []

# GOOD: 直接引用 (Pydantic v2 解析 OK, 但要确保 RatioField 已定义)
from backend.contracts.types import RatioField
ratios: List[RatioField] = []
```

**违规示例**:

```python
# BAD: 字符串前向引用, element-wise 约束失效
ratios: List["RatioField"] = []
ratios: List["PercentageField"] = []
pcts: List["PpField"] = []
```

**已知 B2 试点反例**: Sprint 16.5 B2 试点本身在 `category.py`/`health.py` 用 `"RatioField"`
(单字段 OK) 和 `metrics.py` 用 `List[Annotated[...]]` (OK). 字符串前向引用在单字段场景下
Pydantic v2 是 OK 的, 但 List 场景下不行 — 这正是 R4 专治的反模式.

## 3. 怎么跑 lint

### 3.1 一次性扫描

```bash
# 从 project root 跑
python -m backend.contracts._lint

# 输出:
#   [ERROR] /path/to/contract.py:42 [R1] bad_ratio: bad_ratio 字段名以 _ratio 结尾, ...
#   [ERROR] /path/to/contract.py:55 [R4] ratios: ratios 是 List["X"] 前向引用, ...
#   12 issue(s) found.
#   exit code 1

# 或:
#   OK All contracts pass ground-truth-lint
#   exit code 0
```

### 3.2 只检查 1 个文件 (内部用)

```python
from pathlib import Path
from backend.contracts._lint import lint_contract_file

issues = lint_contract_file(Path("backend/contracts/category.py"))
for i in issues:
    print(f"[{i.rule}] {i.field}: {i.message}")
```

### 3.3 pytest

```bash
cd backend && pytest contracts/tests/test_lint.py -v
# 10 passed in 0.1s
```

## 4. 怎么写新 contract (B1+B2 模式)

### 4.1 B1: AudiencePattern (28 字段补标, Sprint 15)

Sprint 15 B1 模式: 写完 contract 后, **每个 ratio/pct/ppt 字段必须显式标
RatioField/PercentageField/PpField**, 跟 `backend/contracts/types.py` 对齐.

**模板**:

```python
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from backend.contracts.types import RatioField, PercentageField, PpField


class MyNewResponse(BaseModel):
    name: str
    count: int

    # 单字段: 直接用 (用 "RatioField" 字符串前向引用 OK)
    member_ratio: "RatioField" = 0.42

    # 可选字段: Optional 或 | None
    yoy_pct: Optional[PercentageField] = None
    diff_ppt: PpField | None = None

    # List 字段: 必须 Annotated, 不许 List["X"]
    member_ratios: List[Annotated[float, Field(ge=0.0, le=1.0)]] = []
```

### 4.2 B2: 跑 lint 必须 0 issue

写完 contract 立刻跑:

```bash
python -m backend.contracts._lint backend/contracts/my_new.py
```

期望: 0 issue, exit 0.

如果 lint 报错, 按 message 提示修 (e.g. `bad_ratio 必须 RatioField` → 改 RatioField).

### 4.3 Commit 前 checklist

- [ ] 写完新 contract, ratio/pct/ppt 字段全部标注
- [ ] List 字段用 List[Annotated[...]] 而非 List["X"]
- [ ] 跑 `python -m backend.contracts._lint` 期望 0 issue
- [ ] 跑 `pytest contracts/tests/test_lint.py -v` 10/10 过
- [ ] 跑 `pytest backend/tests/test_*.py -x -q` 全套件无 regression

## 5. 集成: pre-commit hook (可选)

加 `.git/hooks/pre-commit`:

```bash
#!/bin/sh
# Sprint 17 #121: 跑 ground-truth-lint
output=$(python -m backend.contracts._lint 2>&1)
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "❌ ground-truth-lint failed:"
    echo "$output"
    echo ""
    echo "Fix the contract fields above, then commit again."
    exit 1
fi
```

```bash
chmod +x .git/hooks/pre-commit
```

**注意**: 芙清 CRM Sprint 13+ 是 LLM-heavy 工作流, 跑批 + 写 contract 的 LLM 不一定
触发 git commit (通常 PR review 阶段才 commit). pre-commit hook 更适合 human dev 写
contract 的场景. LLM agent 应该用:

```bash
# 写完 contract 后自检
python -m backend.contracts._lint && echo "OK"
```

## 6. 跟 Sprint 17 其它任务配合

### 6.1 跟 #120 (B2 全量 audit 剩 9 contract 字段补标)

#120 修 11 个 contract (asset/audience/breakdown/churn/common/flow/geo/rfm/sampling/
visitor/schemas) 缺的 ratio/pct/ppt 字段. 修完后跑 lint:

```bash
python -m backend.contracts._lint
# 期望: 0 issue (除了 _lint.py 等工具文件, 已被 skip)
```

如果 #120 修完还有 issue, 说明 audit 漏了字段, 加进 #120 后续.

### 6.2 跟 #122 (B1+B2 模式写进 CLAUDE.md)

#122 在 `CLAUDE.md` 的 "Ratio Convention (Sprint 13+)" 章节加:
- 命名约定: 字段名以 `_ratio`/`_pct`/`_ppt` 结尾
- 3 个 Pydantic 类型对应 (RatioField/PercentageField/PpField)
- 写新 contract 强制走 B1+B2 模式
- 跑 `python -m backend.contracts._lint` 必须 0 issue

#122 在规范层 (CLAUDE.md) 强制, #121 在工具层强制. 互补.

## 7. 已知限制 & 未来扩展

### 7.1 已知限制

- **启发式 Name 匹配**: linter 用 `RatioField`/`PercentageField`/`PpField` 名称识别合规
  类型, 假设从 `backend.contracts.types` 正确导入. 如果用户自己定义同名但不同 (ge, le)
  的类型, linter 不会发现.
- **List 内部类型不复查**: 假设 List 内部 X 跟外层字段名一致. e.g. `yoy_pct: List[float]`
  (字段名 `_pct` 结尾 + List 不合规), linter 不会报 — 因为 List 内是 `float` 不是字符串.
  这种情况需要 Pydantic 2 的 TypeAdapter runtime 验证.
- **B2 试点本身用字符串**: `category.py`/`health.py` 用 `"RatioField"` (单字段 OK,
  Pydantic v2 解析), linter 视为合规. R4 专治 List["X"] 反模式.

### 7.2 未来扩展

- Sprint 18+: 加 `field_validator` 跟 ratio 命名一致 (e.g. `_sum_to_1` validator on
  ratio 字段), linter 同样规则.
- Sprint 19+: 加 frontend contract (TypeScript interface) 同样 lint, 强制前端对齐
  backend ratio 命名.
- Sprint 20+: 集成 autoplan precommit, 写 contract 后自动跑 lint + 报 issue 到 review.

## 8. 测试覆盖

10 个 pytest 在 `backend/contracts/tests/test_lint.py`:

| Test | 类型 | 验证 |
|------|------|------|
| `test_r1_missing_ratio_field` | True-positive | 2 个裸 float `_ratio` 字段 → 2 个 R1 issue |
| `test_r2_missing_percentage_field` | True-positive | 2 个裸 float `_pct` 字段 → 2 个 R2 issue |
| `test_r3_missing_pp_field` | True-positive | 2 个裸 float `_ppt` 字段 → 2 个 R3 issue |
| `test_r4_list_forward_ref` | True-positive | 2 个 `List["X"]` → 2 个 R4 issue |
| `test_compliant_ratio_field` | False-positive | 2 个 `RatioField` → 0 issue |
| `test_compliant_percentage_field` | False-positive | 2 个 `Optional[PercentageField]` → 0 issue |
| `test_compliant_pp_field` | False-positive | 2 个 `PpField \| None` → 0 issue |
| `test_compliant_annotated_list` | False-positive | `List[Annotated[float, Field(ge, le)]]` → 0 issue |
| `test_skip_non_basemodel_class` | Skip-rule | dataclass 不被检查 |
| `test_syntax_error_returns_single_issue` | Edge case | 语法错误返 1 个 SYNTAX issue, 不抛异常 |

跑测试: `pytest contracts/tests/test_lint.py -v` → 10 passed.

## 9. 实际跑 lint 输出 (Sprint 17 现状)

修完 B2 试点 9 字段后跑:

```bash
$ python -m backend.contracts._lint
# 74 issue(s) found.
```

74 issue 分布在 11 个未修 contract (asset/audience/breakdown/churn/common/flow/geo/
rfm/sampling/visitor/schemas). 这是 #120 待修的债务, 修完应该降到 0.

**重要**: 9 个 B2-done 字段 (3 contract × 3 mark) 跑 lint 全 0 issue, 跟 Sprint 16.5 试点
报告一致.
