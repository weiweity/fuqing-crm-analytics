# Git 收口与独立复现（2026-09-09）

候选分支：`codex/competition-closeout`。包含 CI 提交 a3ffe50、57075a5，
以及 competition-integration 的未提交补丁和 A9 独立测试/金标准。
原工作树未改动。原始输入以 SOURCE-MANIFEST.json 绑定，后续修复由 Git diff 绑定。

## 独立复现范围

本候选新建 Python venv 分别安装 requirements-lock.txt 和 scripts/dsh-b0/requirements.lock；
Vue 使用 npm ci；DSH 使用固定 d347e703908d0406b7a7ef80e3a0e594d86b2215，
重新安装 pnpm 锁并 build:official，未复制上游 node_modules 或旧插件 lib。
公网 fetch 等待未完成，终止本次 fetch 后从已固定的本地 Git 对象取同一 SHA；
源码和 lock 哈希由 pipeline 校验。没有宣称公网重新下载成功。
Logo 使用本树 git lfs pull 的原字节。

已执行：独立后端环境比赛及检查器测试 198 passed；
B0 pipeline 460 Python、20 supervisor、225 源测试、53 编译测试、52 比赛 Node 测试，
再在不带 lib/node_modules 的干净插件副本重建并通过 53 编译测试，产物逐字节一致。
BUILD-EVIDENCE.json 记录产物哈希。Vue 类型检查与构建通过。
第一次 pre-push 在 backend 第 9 组被旧 MTD 月初断言拦截，未开始 LFS 或远端推送。
该断言仍要求回落完整上月，与已冻结 C0 月初 EMPTY 金标准冲突；现更新为本月空窗并保留闰年 cutoff 校验。
最后两组已独立重跑通过；下次推送仍完整执行正常门禁，不按前次结果跳过。

提交 6e0c4a1568e915ff9272be7c3aba5c8925f86f0b 后，另起本轮自有 18083 合成 HTTP，
认可→成板→重复提交仍一块板→停止并重启该 Python→GET 重开 persisted=true。
行数为 1，板数为 1，见 LIVE-REPRODUCTION.json。仅结束本轮 18083 实例。

## 提交前审查与修复

- A9 默认 SUT 改为当前仓库，保留显式覆盖；补入独立金标准文件。
- Logo 取消相邻工作树兜底，缺文件、LFS 指针及错误字节均拒绝。
- supervisor 只选择空闲 4328/4329；诊断监听测试使用系统分配端口。
  pipeline PATH 补系统 sbin，避免缺 lsof 时误判端口空闲。
- 取消 attempt/batch 按 actor 隔离；历史渠道/商品进入 RFM 缓存键。
- 修复新空分母语义在旧格式化调用中的异常，AudienceRow ratio 接受 null，离线重生成 Vue 类型。
  归档 sampling 保留现有数值契约，显式传 default=0.0，不把它当 C0 验收。
- 非 C0 参数校验保留 FastAPI 原异常编码器，避免不可序列化错误对象造成 500。
- 品牌脚本允许无 document 的插件装配测试；更新过期 footer 文案断言。
- 检查 SQL 参数、持久化事务、身份范围、构建依赖及新增文件；未引入真实数据库或凭据。
- 历史计划钩子误报：冻结 G0 的 17 文件逐字节校验原 manifest；检查器只对该固定 manifest 和匹配的 Git index/HEAD 字节识别历史证据，改写快照或 manifest 仍不豁免。当前计划文档追加历史条件说明。

## 复现命令

在本仓库根目录，先准备两个独立 Python 3.14 环境和 Node 24：

```sh
python3.14 -m venv .context/reproduce-backend
.context/reproduce-backend/bin/python -m pip install -r requirements-lock.txt
python3.14 -m venv .context/reproduce-python
.context/reproduce-python/bin/python -m pip install -r scripts/dsh-b0/requirements.lock
git lfs pull --include=frontend-vue3/src/assets/brand/shine-mage.png --exclude=
node scripts/dsh-b0/pipeline.mjs --prepare --python "$PWD/.context/reproduce-python/bin/python"
node scripts/dsh-b0/pipeline.mjs --check --python "$PWD/.context/reproduce-python/bin/python"
.context/reproduce-backend/bin/python scripts/run_backend_tests_bounded.py
npm --prefix frontend-vue3 ci --ignore-scripts
npm --prefix frontend-vue3 run build
npm --prefix frontend-vue3 run test:unit
```

混合 Git hook 检查的 PATH 选后端环境与 Node 24，另设
`FQ_B0_PYTHON="$PWD/.context/reproduce-python/bin/python"`。
正常执行 hooks 和 LFS，不设置 skip、不绕过 gate。

## 未关闭范围

产品仍 PARTIAL。T13 真实模型、T15 三角色 UAT、T16 容量未执行；
本轮未新做真实浏览器 T17，沿用 Grok 历史 PARTIAL，编译 DOM 不替代完整原生验收。
真实 cohort features、A3 串行 MCP、业务默认值/会员历史/派样渠道、antd 口径仍需后续处理。
没有 merge、部署、营销发送或真实数据访问。既有 4327/8000/5173/14327/18082 未停止。
