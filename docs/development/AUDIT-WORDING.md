# Audit 措辞 SOP (Sprint 59 #8 落地)

> 闭环 Sprint 32.3 a9b1d91 + Sprint 58 #2 commit-msg blocking 同根因 (模糊词无 commit SHA / 实证).
> 战略收缩 (Codex review #23 + #24): 不写 lint script, 关键词 regex 推动作者写出能骗过正则的文本, 失去门禁价值.
> 真控制点 = 结构化证据字段 (claim + commit + verification + date), 由 Stage 3 architecture review 人工验证.

## 5 规则

1. **避免"完成"/"治根"/"闭环"等模糊词**: 必须带 commit SHA (7-40 hex, `git rev-parse --verify` 验证存在) 或具体数据
2. **数据导向**: 用 N=N 验证 + commit hash + 文件:行号 引用代替主观判断
3. **回归可追溯**: `0.5x → 1x 加速` 写 "4.32s → 2.26s, commit SHA X" 而非 "加速 73x"
4. **避免"搞定"/"修好"**: 改用 "WARN→blocking 升级" + commit SHA
5. **结构化证据**: claim + commit + verification + date 字段, 不用关键词 regex

## 反例 → 正例 (5 对, 教学材料)

| ❌ 反例 | ✅ 正例 |
|---------|---------|
| race flake 治本 | race flake 治本 (per-worker tmp DuckDB + ATTACH read_only, commit `81b43cd`) |
| CI 实战 fix 持久化完成 | CI 实战 fix 持久化 (12+4 follow-up → `docs/operating/ci-e2e-history.md` 142 行, commit `09e2a18`) |
| Sprint 58 #1 治根 | Sprint 58 #1 e2e OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s, commit `4e297a3`) |
| 误报率优化 | 误报率算法优化 (THRESHOLD_RATIO 3.0→10.0, 误报率 17/20 → 0/14, commit `11416b5`) |
| Sprint 58 闭环 | Sprint 58 闭环 (8 commit 0 debt, main HEAD `17b5361`, v0.4.14.142, pytest 754/1) |

## 验证 commit SHA 真实

```bash
for sha in $(grep -oE '[0-9a-f]{7,40}' docs/development/AUDIT-WORDING.md); do
  git rev-parse --verify "$sha" > /dev/null 2>&1 || echo "❌ $sha 不存在"
done
# 期望: 0 个 "不存在" 输出
```

## 不写 lint script (Codex review #23 + #24)

关键词 regex lint 推动作者写出能骗过正则的文本 (例如 "治根 + 版本号" 通过, "Sprint 58 闭环" 附近加版本号即可过).
真控制点是结构化证据字段, 不是关键词匹配. 老 entry 是 immutable record, 不回溯改 (Sprint 56 教训).