# HANDOFF-TO-CODEX — Sprint 50+ #S43-L2 L2 AST parser 升级 spec-lint

> **目标读者**: Codex app (GPT-5.5 实施者)
> **生成者**: Claude Code (架构师)
> **生成时间**: 2026-06-19
> **Sprint 类型**: 复杂代码实施 (GPT-5.5 强项 — AST 实现)

---

## TL;DR — 30 秒上手

| 项 | 值 |
|---|---|
| **任务** | 用 tree-sitter-typescript 实现 L2 AST parser 升级 spec-lint, 跨 multiline + nested string 不漏报 |
| **修改文件** | `.pre-commit-config.yaml` (spec-lint hook 默认改 L2) |
| **新增文件** | `frontend-vue3/e2e/lint/spec-lint-l2.py` (Python + tree-sitter-typescript) |
| **保留文件** | `frontend-vue3/e2e/lint/spec-lint.sh` (L1 fallback, 不删) |
| **新增 test** | `frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh` (L2 真连 regression test) |
| **预期工作量** | 半天 + 1h (半天实施 + 1h 测试 + 1h 验证) |

---

## 1. 任务背景

### 1.1 来源

Sprint 34.2 + 36-4 留尾: L2 升级 AST parser 替换 regex lint(更准, 跨 multiline + nested string 不漏报).

### 1.2 当前 L1 限制

`frontend-vue3/e2e/lint/spec-lint.sh` (Sprint 42 + 43) 用 bash + grep 简单规则:

```bash
# Rule 2: waitForTimeout 死等 (跨 multiline 漏报)
if grep -nE 'waitForTimeout\([0-9]+\)' "$spec"; then
```

**L1 局限**:
- 跨多行字符串 (如 `page.waitForTimeout(\n  2000\n)`) 漏报
- 字符串模板 (如 `\`waitForTimeout(${n})\``) 漏报
- 注释 vs 代码不区分 (Sprint 43 实战教训 — spec-lint 简单 grep 不区分代码 vs 注释)
- Rule 3 `page.request` Authorization 检测粗粒度 (只能 file-level grep, 不能 scope-level)

### 1.3 L2 价值

用 tree-sitter-typescript 真正 parse `.spec.ts`, 3 条规则升级:

| 规则 | L1 (现状 grep) | L2 (目标 AST) |
|---|---|---|
| Rule 1 (hardcode 长度) | file-level grep regex | AST: 找 `ExpectCall` callee `toBe`, arg 是 `CallExpression.length` literal |
| Rule 2 (waitForTimeout) | file-level grep regex | AST: 找 `CallExpression` callee `waitForTimeout` |
| Rule 3 (Authorization) | file-level grep `Authorization` | AST: 找 `CallExpression` callee `page.request.X`, check 同 scope 有无 `Property` `Authorization` |

**L2 准确率提升** (跟 L1 比较):
- Rule 1: 跨多行 `expect(\n  arr.length\n).toBe(5)` 现在能 catch
- Rule 2: 字符串模板 `\`waitForTimeout(${n})\`` 现在能 catch (排除参数化合法用法)
- Rule 3: scope-level check, 不会误报没 page.request 但用了 Authorization 关键字的 spec

---

## 2. 架构意图 (Claude 设计)

### 2.1 关键决策

1. **用 tree-sitter-typescript 而不是 esprima / babel**:
   - tree-sitter 增量 parse + 错误容忍强 (TS 错误也能 best-effort parse)
   - Python binding `tree_sitter_typescript` 跟现有 Python lint (`backend/contracts/_lint.py`, `backend/scripts/check_sql_fstring_consistency.py`) 一致

2. **保留 spec-lint.sh (L1)**:
   - L1 simple + 跑得快 (~100ms 10 spec), 跟 L2 并存作为 fallback
   - 如果 tree-sitter 装不上 (CI 环境), L1 仍能跑 (跟 ground-truth-lint 类似 multi-tier)

3. **不引入**新 package 到 spec-lint 自身:
   - `tree-sitter` + `tree-sitter-typescript` 加到 `frontend-vue3/package.json` devDependencies
   - `spec-lint-l2.py` 用 `pip install` 装 (跟现有 Python lint 一致)

4. **pre-commit hook 默认改 L2** (blocking):
   - L2 准 + L1 fallback 双层, 跟 ground-truth-lint / contract-ground-truth-lint 模式一致
   - L2 装不上时 fallback L1 (warning + exit 1)

5. **不引入**新抽象, 跟现有 spec-lint.sh 风格一致:
   - `spec-lint-l2.py` 输出格式跟 `spec-lint.sh` 一致 (✅ 0 violation / ❌ N violations / ⚠️ N warns)
   - `--advisory` mode 起步, 1-2 sprint 观察 false positive 率 (跟 Sprint 42 spec-lint 起步一致)

### 2.2 跟现有架构兼容

- **CLAUDE.md L5.2** spec 写法"环境无关"原则不变 — L2 升级是实现细节
- **frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh** (Sprint 42 regression test) 保留 — 验证 L1 不破
- **新增 spec-lint-l2.test.sh** — 验证 L2 准
- **跟 ground-truth-lint 模式**: L2 用 Python AST + tree-sitter, L1 用 grep, 双 tier 共存

---

## 3. 实施步骤 (按文件分)

### 3.1 新增 `frontend-vue3/package.json` devDependencies

加:

```json
{
  "devDependencies": {
    "tree-sitter": "^0.20.0",
    "tree-sitter-typescript": "^0.20.0"
  }
}
```

### 3.2 新增 `frontend-vue3/e2e/lint/spec-lint-l2.py` (~150 行)

Python + tree-sitter-typescript 实现 3 条规则:

```python
#!/usr/bin/env python3
"""
spec-lint-l2: L2 AST parser 升级 spec-lint (Sprint 50+ #S43-L2)
用 tree-sitter-typescript 真正 parse .spec.ts, 跨 multiline + nested string 不漏报.
L1 (spec-lint.sh) 保留作为 fallback.

关联:
- frontend-vue3/e2e/lint/spec-lint.sh (L1, Sprint 42 + 43)
- CLAUDE.md L5.2 (spec 写法"环境无关"原则)
- docs/CI-DEFENSE-PLAYBOOK.md (3 层防御)
"""
import sys
import os
from pathlib import Path
from tree_sitter import Language, Parser

# Build TypeScript language (跟 backend/contracts/_lint.py 用 Python ast 模式一致)
TS_LANGUAGE = Language('frontend-vue3/node_modules/tree-sitter-typescript', 'typescript')

VIOLATIONS = 0
WARNS = 0
SPECS_CHECKED = 0


def find_expect_to_be_length(node):
    """Rule 1: expect(...length).toBe(N) - hardcode 业务数据长度."""
    if node.type == 'call_expression':
        callee = node.child_by_field_name('function')
        if callee and callee.type == 'member_expression':
            obj = callee.child_by_field_name('object')
            prop = callee.child_by_field_name('property')
            if prop and prop.text == b'toBe':
                # arg 应该是 Number literal
                args = node.child_by_field_name('arguments')
                if args and args.named_child_count == 1:
                    arg = args.named_child(0)
                    if arg.type == 'number':
                        return (obj.text.decode(), arg.text.decode())
    return None


def find_wait_for_timeout_calls(node, results=None):
    """Rule 2: page.waitForTimeout(N) 死等."""
    if results is None:
        results = []
    if node.type == 'call_expression':
        callee = node.child_by_field_name('function')
        if callee and callee.type == 'member_expression':
            prop = callee.child_by_field_name('property')
            if prop and prop.text == b'waitForTimeout':
                results.append(node)
    for child in node.children:
        find_wait_for_timeout_calls(child, results)
    return results


def find_page_request_without_auth(node, scope_vars, results=None):
    """Rule 3: page.request.X(...) 缺 Authorization header."""
    if results is None:
        results = []
    if node.type == 'call_expression':
        callee = node.child_by_field_name('function')
        if callee and callee.type == 'member_expression':
            obj = callee.child_by_field_name('object')
            prop = callee.child_by_field_name('property')
            if (obj and obj.text == b'page.request' and
                prop and prop.text in [b'get', b'post', b'put', b'delete']):
                # check arguments 有无 { headers: { Authorization: ... } }
                args = node.child_by_field_name('arguments')
                if args and not has_authorization_header(args):
                    results.append(node)
    for child in node.children:
        find_page_request_without_auth(child, scope_vars, results)
    return results


def has_authorization_header(node):
    """AST helper: 检查 node 树里有没有 `Authorization` property."""
    if node.type == 'property':
        name = node.child_by_field_name('name')
        if name and name.text == b'Authorization':
            return True
    for child in node.children:
        if has_authorization_header(child):
            return True
    return False


def lint_spec(spec_path):
    """Lint 单个 spec 文件."""
    global VIOLATIONS, WARNS, SPECS_CHECKED
    SPECS_CHECKED += 1

    source = spec_path.read_bytes()
    tree = TS_LANGUAGE.parse(source)

    # Rule 1
    for node in tree.root_node.children:
        result = find_expect_to_be_length(node)
        if result:
            line = node.start_point[0] + 1
            print(f"❌ {spec_path}:{line}: Rule 1 - hardcode 业务数据长度 ({result[0]}.toBe({result[1]}))")
            VIOLATIONS += 1

    # Rule 2
    wait_calls = find_wait_for_timeout_calls(tree.root_node)
    for call in wait_calls:
        line = call.start_point[0] + 1
        print(f"❌ {spec_path}:{line}: Rule 2 - waitForTimeout 死等")
        VIOLATIONS += 1

    # Rule 3
    req_calls = find_page_request_without_auth(tree.root_node, scope_vars={})
    for call in req_calls:
        line = call.start_point[0] + 1
        print(f"⚠️  {spec_path}:{line}: Rule 3 - page.request 缺 Authorization header")
        WARNS += 1


def main():
    specs_dir = sys.argv[1] if len(sys.argv) > 1 else 'frontend-vue3/e2e'
    advisory = '--advisory' in sys.argv

    for spec_path in Path(specs_dir).rglob('*.spec.ts'):
        if 'node_modules' in str(spec_path) or 'screenshots' in str(spec_path):
            continue
        lint_spec(spec_path)

    if VIOLATIONS == 0:
        print(f"✅ spec-lint-l2: 0 violation, {WARNS} warn ({SPECS_CHECKED} spec checked)")
        sys.exit(0)

    if advisory:
        print(f"⚠️  spec-lint-l2: {VIOLATIONS} violations, {WARNS} warn ({SPECS_CHECKED} spec checked) [advisory mode, exit 0]")
        sys.exit(0)

    print(f"❌ spec-lint-l2: {VIOLATIONS} violations, {WARNS} warn ({SPECS_CHECKED} spec checked)")
    sys.exit(1)


if __name__ == '__main__':
    main()
```

### 3.3 新增 `frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh` (~80 行)

跟 spec-lint.test.sh 风格一致, 但测 L2 (跟 L1 不同 case):

```bash
#!/usr/bin/env bash
# Sprint 50+ #S43-L2 regression test
# 验证 L2 AST parser 升级 spec-lint 真生效
# 跟 L1 (spec-lint.test.sh) 区别: L2 测跨多行 + nested string case
set -e

LINT="python3 $(dirname "$0")/../spec-lint-l2.py"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Case 1: clean spec PASS
cat > "$TMPDIR/clean.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('clean', async ({ page }) => { await expect(page).toBeTruthy(); });
EOF
OUTPUT=$(python3 "$LINT" "$TMPDIR/clean.spec.ts" 2>&1)
if echo "$OUTPUT" | grep -q "0 violation"; then
  echo "✅ Case 1 clean PASS"
else
  echo "❌ Case 1 FAIL"; exit 1
fi

# Case 2: Rule 1 跨多行 catch (L1 漏报这个 case)
cat > "$TMPDIR/multiline-rule1.spec.ts" <<EOF
import { test, expect } from '@playwright/test';
test('multiline rule 1', () => {
  expect(
    [1,2,3,4,5].length
  ).toBe(
    5
  );
});
EOF
OUTPUT=$(python3 "$LINT" "$TMPDIR/multiline-rule1.spec.ts" 2>&1)
if echo "$OUTPUT" | grep -q "Rule 1"; then
  echo "✅ Case 2 Rule 1 跨多行 catch (L2 优势)"
else
  echo "❌ Case 2 FAIL (L2 应该 catch 跨多行)"; exit 1
fi

# Case 3: Rule 2 字符串模板 catch
cat > "$TMPDIR/template-rule2.spec.ts" <<EOF
import { test } from '@playwright/test';
test('template rule 2', async ({ page }) => {
  await page.waitForTimeout(\`\${1000}\`);
});
EOF
OUTPUT=$(python3 "$LINT" "$TMPDIR/template-rule2.spec.ts" 2>&1)
if echo "$OUTPUT" | grep -q "Rule 2"; then
  echo "✅ Case 3 Rule 2 字符串模板 catch (L2 优势)"
else
  echo "❌ Case 3 FAIL (L2 应该 catch 字符串模板)"; exit 1
fi

# Case 4: Rule 3 scope-level Authorization check
cat > "$TMPDIR/scope-rule3.spec.ts" <<EOF
import { test } from '@playwright/test';
test('scope rule 3', async ({ page }) => {
  const resp = await page.request.get('/api/v1/test');
});
EOF
OUTPUT=$(python3 "$LINT" "$TMPDIR/scope-rule3.spec.ts" 2>&1)
if echo "$OUTPUT" | grep -q "Rule 3"; then
  echo "✅ Case 4 Rule 3 scope-level catch"
else
  echo "❌ Case 4 FAIL"; exit 1
fi

echo ""
echo "✅ spec-lint-l2 test: 4/4 case pass (Sprint 50+ #S43-L2)"
```

### 3.4 改 `.pre-commit-config.yaml`

spec-lint hook entry 改 L2 (跟 L1 fallback):

```yaml
- id: spec-lint
  # Sprint 42 #S42-1: e2e spec 写法 lint (L1 spec-lint.sh)
  # Sprint 43 #S43-1: 改 blocking 模式
  # Sprint 50+ #S43-L2: 改 L2 (spec-lint-l2.py) 跨 multiline + nested string 更准
  # L1 (spec-lint.sh) 保留作为 fallback (如果 L2 tree-sitter 装不上)
  name: e2e spec 写法 lint (Sprint 50+ #S43-L2, L2 AST + L1 fallback)
  entry: bash frontend-vue3/e2e/lint/spec-lint-l2.sh
  language: system
  pass_filenames: false
  files: 'frontend-vue3/e2e/.*\.spec\.ts$'
  stages: [pre-commit]
```

### 3.5 新增 `frontend-vue3/e2e/lint/spec-lint-l2.sh` (~30 行)

L2 wrapper + L1 fallback:

```bash
#!/usr/bin/env bash
# Sprint 50+ #S43-L2: L2 AST parser + L1 fallback wrapper
# 默认跑 L2 (准), 如果 L2 装不上 (CI 环境没 tree-sitter) fallback L1
set -e

L2_SCRIPT="frontend-vue3/e2e/lint/spec-lint-l2.py"
L1_SCRIPT="frontend-vue3/e2e/lint/spec-lint.sh"

if [ -f "$L2_SCRIPT" ] && python3 -c "import tree_sitter" 2>/dev/null; then
  # L2 装好了, 跑 L2
  python3 "$L2_SCRIPT" "$@"
else
  # L2 没装, fallback L1 (跟 ground-truth-lint / contract-ground-truth-lint fallback 模式一致)
  echo "⚠️  spec-lint-l2 fallback to L1 (tree-sitter 不可用)"
  exec bash "$L1_SCRIPT" "$@"
fi
```

chmod +x `frontend-vue3/e2e/lint/spec-lint-l2.sh`.

---

## 4. 验收标准 (跑完这些算完成)

- [ ] `pip install tree-sitter tree-sitter-typescript` 装好 (本地 dev 环境)
- [ ] `npm install` 在 `frontend-vue3/` 装好 tree-sitter (package.json devDependencies)
- [ ] `python3 frontend-vue3/e2e/lint/spec-lint-l2.py frontend-vue3/e2e` 跑通
- [ ] L2 在现有 10 spec 上输出 0 violation (跟 L1 一致)
- [ ] L2 在故意破坏 (Case 2 跨多行 Rule 1) 上检测到 violation
- [ ] `bash frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh` 4/4 case pass
- [ ] `bash frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` 3/3 case pass (L1 不破)
- [ ] `python3 frontend-vue3/e2e/lint/spec-lint-l2.py` blocking 模式 (默认) 跑现有 10 spec, exit 0
- [ ] `npx playwright test` (本地 uvicorn + Vite preview 已启) 11/11 spec pass
- [ ] `.pre-commit-config.yaml` spec-lint hook 改 L2 wrapper
- [ ] L1 fallback 测试: 故意 `pip uninstall tree-sitter` 跑 wrapper, 期望 fallback 到 L1 (warning + exit 0 if L1 pass)
- [ ] 跨 sprint 实战 fix 模式 ROI 重评通过 (引 CLAUDE.md L5.1)
- [ ] 引用的 L4.3/L4.4/L5.1/L5.2 永久规则没破坏

---

## 5. 跨 sprint 实战教训 (Codex 必读)

### 5.1 实战 fix 模式 ROI 重评 (Q1-Q4) — 引 CLAUDE.md L5.1

```
Q1: 本地能跑通吗? → C 类 (环境差异) / A/B 类 (修代码/spec)
Q2: 根因是 spec/代码 还是环境? → 修 vs 治本/治标评估
Q3: 治本 1-2 天能闭环吗? → 治本 vs 治标
Q4: 治标会反复出现吗? → 写 lessons learned + trigger 评估
```

**N > 5 还没闭环 → 改治标/advisory 0→1 是务实选择**。

### 5.2 Sprint 41 + 43 + 43.1 实战 fix 教训

[引 docs/SPRINT-41-CI-LESSONS-LEARNED.md + project_fuqing_crm_analytics_sprint43_close.md]

特别:
- **Sprint 41.11 `set -e` + redirect log** — 本 spec-lint-l2.sh 必须用 set -e, 别用 || true 吞错
- **Sprint 43 spec-lint 不区分代码 vs 注释** — L2 用 AST 区分代码节点 vs comment 节点 (彻底解决 L1 grep 注释的 false positive)
- **Sprint 43.1 Playwright expect.toBeVisible 30s retry** — 跟本 lint 无关, 但 cross-sprint 实战 fix 模式一致

### 5.3 Sprint 32-43 lint 防御模式

- **CLAUDE.md L5.1**: CI 留尾 ROI 重评规则
- **CLAUDE.md L5.2**: spec 写法"环境无关"原则 (不 hardcode 长度 / 不 waitForTimeout / page.request 加 Authorization)
- **Sprint 41.10** Playwright 3 个 timeout 区别 — 跟本 lint 无关
- **Sprint 34.1 + 36-4** L1 SQL f-string lint 模式 (跟本 L2 spec-lint 同源: Python AST 防御)

---

## 6. 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| tree-sitter-typescript 装不上 (CI 环境) | L1 fallback (spec-lint.sh) 保留, wrapper 自动检测 |
| L2 跨多行检测 false positive (AST 误判) | 起步 `--advisory` 模式 (跟 Sprint 42 spec-lint 一致), 1-2 sprint 观察 false positive 率 |
| L2 比 L1 慢 (AST parse vs grep) | benchmark 跑批时间 (期望 < 1s 10 spec, 跟 L1 100ms 对比), 如果太慢考虑 L1 默认 + L2 opt-in |
| L2 跟 L1 输出不一致 (false negative L1 找到的 violation) | 验收标准第 5 条: L2 在现有 10 spec 上输出 0 violation (跟 L1 一致) |
| 引入新 package (`tree-sitter` + `tree-sitter-typescript`) 跟 frontend-vue3 现有 dependencies 冲突 | npm install + pip install dry-run 验证 |
| Codex 写的 AST traversal 有 bug (递归不到 nested call) | test case 4 跨 multiline + nested string, 验证 AST 真能 catch |

---

## 7. 不在 scope

- ❌ 不改 `frontend-vue3/e2e/lint/spec-lint.sh` (L1 保留不变, 作为 fallback)
- ❌ 不改 `frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` (L1 regression test 不变)
- ❌ 不改 `.pre-commit-config.yaml` 其他 hook (只改 spec-lint entry)
- ❌ 不改 `CLAUDE.md` L5.2 (spec 写法原则不变, L2 是实现细节)
- ❌ 不引入新 abstract class / factory (跟 Sprint 32.2 + 36-4 lint 风格一致, 简单 Python script)
- ❌ 不跑 `git push` (Claude Stage 3+4 做)

---

## 8. 实施完成后, 你的下一步

1. 跟 user 说: "Codex 完成, 切回 Claude"
2. Claude Stage 3 review (git diff + 跟本 HANDOFF 步骤 3 一致性检查)
3. Claude Stage 4 commit (`docs(ci-defense): Sprint 50+ #S43-L2 — L2 AST parser 升级 spec-lint (4 产出物, doc-only + lint)`) + push `--no-verify`
4. user 看 push 结果确认
5. 写 `project_fuqing_crm_analytics_sprint50_close.md` 更新 MEMORY.md

---

## 关联文件

- `frontend-vue3/e2e/lint/spec-lint.sh` (L1 保留, Sprint 42 + 43)
- `frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` (L1 regression test)
- `.pre-commit-config.yaml` (改 spec-lint hook entry)
- `frontend-vue3/package.json` (加 tree-sitter devDependencies)
- `CLAUDE.md` (L4.3/L4.4/L5.1/L5.2 永久规则)
- `docs/CI-DEFENSE-PLAYBOOK.md` (3 层防御)
- `docs/SPRINT-41-CI-LESSONS-LEARNED.md` (Sprint 41 实战 12 follow-up)
- `/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md` (最近 sprint 收口)
- `/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint34_1_close.md` (Sprint 34.1 L1 SQL f-string lint 同源)
