# Sprint 文档区

> **最后更新**: 2026-07-19  
> 只放**未 ship / 进行中**的 handoff。已收口一律进 `archive/`。

## 当前文件

| 文件 | 用途 |
|---|---|
| [`_sprint-close-index.md`](_sprint-close-index.md) | close memory 指针（~/.claude 本地，仓内只索引） |
| [`archive/`](archive/) | 已 ship / 已撤回 handoff、验证报告、根目录迁入的 HANDOFF |

## 规则

1. **新 handoff** 写在本目录：`HANDOFF-*.md` / `WORKFLOW-*.md`
2. **合 main 或产品撤回后 24h 内** → `git mv` 到 `archive/`
3. **开放债**只写 [`../TECH-DEBT.md`](../TECH-DEBT.md)，不在此堆过程日记
4. 根目录禁止长期堆 `HANDOFF-TO-CODEX-*.md`（已 gitignore；落盘请放 `archive/root-handoffs-*`）

## 2026-07-19 整理

- 根 8 份 `HANDOFF-TO-CODEX-*` → `archive/root-handoffs-2026-07-19/`（本地 ignore，不入远程强制）
- SprintC / Admin Upload / PC2 / Market-Focus / backlog workflow 等已 ship 文 → `archive/`
