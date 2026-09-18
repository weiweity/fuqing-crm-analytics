# 三路生产接缝集成

- 状态：**PARTIAL**（代码已收口到本树，未 commit / 未 PR / 未 reload 6677）
- 集成树：`fuqing-crm-analytics-free-html-SEAMS` 分支 `codex/free-html/seams` 基线 `d6b57452`
- 来源：Lane G/H/K 均未 commit，按文件拷贝 + `index.tsx` 手工合并（生成段来自 G，leave/`openCockpitPanel` 来自 K；H 零碰 index）
- 现役 6677 PID **83542** 未触碰

## 合并点

- G：`free_html_page_generate` + waiter + PagePackageToolCard
- H：隔离 18091 HTTP + dsh-dev `--page-http` + `globalThis.__PAGE_*__`
- K：脏页 `openCockpitPanel` 走三选；净页直切避免 D43 丢预览；侧栏限制文案

## 本树抽查

- G 专项 6/6（构建后）
- K 接缝+leave DOM+cockpit source 22/22
- H launcher pytest 9 + page-http/cli 26 + globals 2
- p12-live-adapters 11/11
- plugin typecheck + build exit 0
- ruff + `git diff --check` 干净

P13 真模型、6677 `--page-http on` reload、openPlazaRole、Noto 字体不在本收口。
