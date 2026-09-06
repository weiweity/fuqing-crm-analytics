# 项目 Git hooks

当前检查矩阵、隔离配置与证据格式统一见 [验证入口](../docs/operating/verification.md)。行为授权以 [AGENTS.md](../AGENTS.md) 为准。

| 入口 | 实际职责 | 失败与副作用 |
|---|---|---|
| `pre-commit` | 检查 hooksPath；CHANGELOG 提醒；按暂存路径执行 bare-except、contract、import、test-order、ground-truth、Excel SSOT 暂存内容检查 | 检查失败阻断，管道保留原始失败；CHANGELOG 默认提醒，显式 strict 才阻断；不启动 pytest/vue-tsc |
| `commit-msg` | 调用 `scripts/commit_msg_check.py` 核验提交描述与差异 | 阻断型，保留检查器退出码 |
| `pre-push` | 从 Git ref 协议计算累计差异，调用共用检查矩阵，成功后调用 Git LFS | 验证或 LFS 失败阻断；删除 ref 不跑验证；无结果缓存或自动绕过 |
| `post-merge` | main/master 追加 `.ship-audit.log`，CHANGELOG 只提醒 | 标为 `MERGED into`，不代表发布；不删分支、不拉取、不重启 |

`core.hooksPath=.githooks` 时，默认 `.git/hooks/pre-push` 不会被调用，因此项目 `pre-push` 必须接回 LFS。LFS 接收原始 stdin ref 和 remote 参数，验证跳过也不跳过 LFS。

只有需要激活且已获对应授权时才运行 `bash scripts/setup-hooks.sh`。它会修改仓库 Git 配置，不是诊断命令；本轮治理没有执行安装。相对 hooksPath 在每个工作树解析，各工作树的文件版本可能不同。

`.pre-commit-config.yaml` 是手工选用的 framework 配置（Ruff、contract、spec-lint 三项），不与项目 hooks 叠加安装，不是等价替代。历史对照见 [hooks-choice](../docs/operating/hooks-choice.md)。

分支维护脚本默认预览；应用须指定准确的本地分支且保持工作树干净，保护/当前/未合并/占用分支会拒绝，删除失败不退化为 `-D`。远端删除须另行检查和授权。普通 hook 不调用该脚本。
