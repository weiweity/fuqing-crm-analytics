# 本地候选运行与回退

用户选择由本轮推荐发布环境。本轮采用单用户、仅 loopback 的独立本地候选；不替换用户演示服务。当前基线版本 0.7.0.0，产品修复位于 `codex/competition-product-readiness`，以该分支提交 SHA 和 source-manifest.json 绑定。未建立正式 release tag，也未宣称完整产品验收通过。

## 环境

- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-product-readiness`。
- Web：`http://127.0.0.1:4325/`；synthetic API：`http://127.0.0.1:18083`。只绑定 loopback，Web 未认证访问为 401。
- DSH 上游：`d347e703908d0406b7a7ef80e3a0e594d86b2215`；准备位置为 `competition-closeout/.context/dsh-b0/upstream`。Node 24.19.0；现有 backend/B0 独立 Python 3.14.4 环境保持。新增业务依赖按本轮锁文件在独立目录安装。
- DSH runtime：本树 `.context/dsh-dev/runtime-Cn0Ifc`；保留用户配置的 DeepSeek-V4-Flash 凭据和原生会话。模型密钥不写入 Git、日志或备份证据。
- API 状态：本树 `.context/competition-synth`。启动显式指定 `COMPETITION_SYNTH_PORT=18083`、`COMPETITION_SYNTH_WEB_ORIGIN=http://127.0.0.1:4325`，通过已有 `scripts/competition-synth-http.py` 入口。
- DSH 与浏览器插件构建使用同一服务根地址 `COMPETITION_HTTP_BASE=http://127.0.0.1:18083` 和 synthetic token（不含 API 路径）；模型证书链使用 `NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem`。认证控制状态只供 `cli.mjs` 读取，禁止整文件输出。

完整 B0 pipeline 的默认构建不携带本实例 HTTP 配置。验收前按环境重建插件并重启本工作树拥有的 DSH supervisor；沿用同一 runtime，不能使用 `--fresh` 覆盖用户配置。

## 当前源码与视觉候选

4325 当前插件为 `6202e89`，CI 34437915131 SUCCESS；18083 API 仍为 PID 23661。模型配置和原有板保持，新旧插件及运行绑定见[当前候选与评测](PRODUCT-UAT-CANDIDATE-2026-09-10.md)。真实评测新增计算结果后现有 8 条结果、2 块板，本次没有刷新历史完整备份。方法引用修正已进入运行候选，并通过 A3/B2 两条真实回归；完整 T13 仍 PARTIAL。

## 备份与恢复证据

**单位 v2 切换前置条件**：新读者读取旧 v1 不改 JSON 或摘要，固定旧读者读取新 v2 明确返回 409，见[跨版本实测](evidence/computed-units-2026-09-10/reader-compatibility.json)。当前单位修复仅本地验证。切换 4325/18083 前须更新五库备份，并用独立恢复目录验证现有全部板、草稿和 8 条结果；以下历史备份不能代替此检查。回退保留升级后的状态，旧代码只使用对应旧快照。

只停止本轮拥有的 18083 API 后，通过 SQLite `Connection.backup()` 保存 4 库，再用相同接口恢复至另一个目录；不直接复制 WAL 文件。备份目录 `.context/readiness-backup-20260910`，恢复目录 `.context/readiness-restore-20260910`，均私有权限。备份对应运营草稿创建之前的状态。

备份范围为 `assets/competition_assets.sqlite3`、`audience/competition-audience.sqlite`、`cockpit/cockpit.sqlite3`、`saved/analyses.sqlite3`。四库 quick_check=ok，各表行数一致；恢复后新应用 GET /boards 返回 1 块板，GET 明细为同一板 v2/BAR。旧候选 `3862e7711d72075e95b57932dc7fe0ed2ae4511b` 也实际读到同一恢复板 v2/BAR。完整证据见 [state-backup-restore.json](evidence/product-readiness-2026-09-10/state-backup-restore.json)。

## 回退操作与条件

1. 先从本工作树 `cli.mjs status` 及监听归属确认当前 4325/18083；只停止该 supervisor 和本轮 API。用户的 4327/8000/5173，以及 Grok 14327 不参与。
2. 当前状态保留原位。需要恢复备份时，将当前备份的五库通过 SQLite backup 接口恢复到**新的私有目录**，运行 quick_check 并核对 manifest。不要覆盖当前目录或将旧备份直接拷到活库上。
3. 使用显式 `COMPETITION_SYNTH_STATE=/absolute/restored-directory` 启动候选 API，再启动同一 DSH runtime；重建对应版本的插件。先检查未经认证 401、已认证会话可用、原板及草稿版本，再允许继续编辑。
4. 本轮证实了备份可恢复和旧后端可读。旧版完整浏览器降级、旧版继续写新状态未验证；切回旧代码前必须补验，不能仅因 schema 仍为 v1 就宣称可无损降级。恢复此备份会看不到备份之后创建的运营草稿，当前目录必须保留以便对照和恢复。

## 当前部署后结果

新代码已在 4325/18083 加载。模型配置和 8 轮原生会话保留；已保存 BAR 重开、草稿 LINE 恢复/放弃、行动草稿 v1→v2 刷新恢复、脱离会话阅读和 footer 重开均实际通过。1440/390 截图已查看。产品仍 PARTIAL：见 [UAT](PRODUCT-UAT-2026-09-10.md) 与 [审查记录](evidence/product-readiness-2026-09-10/REVIEW-AND-VERIFICATION.md)。正式版本、T15 签字与完整发布后监测待后续完成。
