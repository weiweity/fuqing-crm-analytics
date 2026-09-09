# 浏览器主线收口（dialog / 合成成板 / 品牌 / T17）

日期：2026-09-09。候选 `competition-integration`。**未 commit / 未 push。**<br>
基础 HEAD `71a65f06f87cb3a5cbd888372487b6b36faaf2a6` **不能**单独绑定本轮成果；以下为脏工作区补丁文件 SHA-256。

未停、未占用 `4327`（PID 81058）、`8000`、`5173`。未付费模型、未容量、未真实业务数据。

## 补丁标识（本轮绑定）

```
b289a4341bf496aba238e2a51a9b0caa8c328c59d4f6363a0fa9b442ca5fd003  asset-overlay.tsx
689984d468365f55dfe7b97d032475ff19e9fa9b0afddfcc3727c9170662f3fa  index.tsx
f0927436f04d6af0a9ff28a95ac627adce2d762f4c7013ab5b20635d5a86894a  brand-surface.mjs
6f0fd9208a6824744396c21961a28f3910073f756b99e34def68178fe667d849  BoardWorkbench.tsx
7ee952120c85d30ef85e4ee0060676eb93fef4f27c77131216bc65b059092d96  competition-board/transport.mjs
c41103bf170a7ededd4c5a1f3be0638645ea611d712a56580b80c0386488aa9f  competition-board/types.ts
d08a54d055da50b24d657d707160c0d00a32aabe60f3fc37a65d491ae2456a90  analytics_competition_app.py
e4aa06a085ae095ee087058d9b424973bfcb02b57d1b21a35b86a1f77224f760  scripts/dsh-dev/brand.mjs
4c01a4368813f426ea51da0864632814716b38de08cf9f51fbe1a5bdb3429526  scripts/competition-synth-http.py
079f6fd0fe99cba2cbed6178a42f117b7210538a335644637e524f562ee44f14  lib/client.js（构建产物）
```

C0 `contract_hash` 仍为 `97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。<br>
上游 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。

## 做了什么

1. **dialog**：`closedby=none`；store 仍 open 时 `onClose` 立即 `showModal`；切面板延后到 timeout 0；比赛面板首次进入后保持挂载。切到「认可成板」后 dialog **保持打开**（实测）。
2. **两套资产平面**：B0 同域 `/b0/dashboards|analyses|assets` 与比赛 `http://127.0.0.1:18082/api/v1/analytics/competition/*` 分开。B0 404 不再写成比赛失败。
3. **合成成板**：`GET /results` 返回可认可 C0 ref（`contains_real_data=false`、64 hex digest、GSV）。`POST /batches` 带回 `board` spec。`GET /boards` / `GET /boards/{id}` 可重开。
4. **品牌**：从主工作副本按 digest 恢复 `logo.png`（不 smudge 本树 LFS 指针）。`document.title` 与问候语覆盖为 DESIGN.md 文案。侧栏名「伸美 AI 增长董事会」。
5. **T17**：独立 14327；未认证 401；Settings 可达；1024/390 截图；Tab 落到驾驶舱入口。未打 4327。

## 实测（不以单次 HTTP 200 代替）

| 步骤 | 结果 | 不是什么 |
|---|---|---|
| 切「认可成板」dialog 仍开 | **PASS** | 不是只测 GET /results |
| 勾选 COMPLETE 结果并 POST batches | **PASS**（服务端板 `board_3214bbbd13f32407b2644cf427242b5d` 标题「8月GSV诊断板」`persisted=true`） | 回执 200 同时有 GET /boards/{id} 与编辑器正文 |
| 返回聊天后再开，编辑看板看到该板 | **PASS**（截图 `t17-loop-edit-board.png`） | 不是刷新前内存态 |
| 在 overlay 内再点「按认可结果成板」 | **FAIL** | dialog 被关掉；随后 footer 点击一次未立刻重开 |
| `document.title` | **PASS** `伸美 AI 增长董事会` | 不是 DeepSeek Harness |
| 问候语 | **PASS** DOM 含「先问一个可核验的经营问题」，无 Into the Unknown | 截图 `t17-native-brand.png` 过黑，**不以该 PNG 宣称视觉通过** |
| Logo | **PASS** `GET /b0/brand/logo.png` 200；overlay 可见 SHINE MAGE 字标 | 本树 png 仍是 LFS 指针，运行时读主工作副本 |
| Settings / 三档 / 未打 4327 | **PASS（入口）** | 压缩/真实模型仍 NOT_RUN |

pytest：`test_competition_http_wiring.py` **8 passed**（含 `test_results_are_endorsable_and_batch_reopens_board`）。

## 剩余失败（保留）

1. **成板确认点击仍关掉 overlay**。持久化已发生，但同屏不成闭环。不能把「HTTP 200 + 另一次打开」说成同一次 overlay 成板通过。
2. **成板关掉后，同页 footer 有时点不开**（需新导航）。`openTick` 未覆盖该次。
3. 编辑器「行数」显示 `undefined`（C0 result 未带 `row_count`）。
4. 原生首屏截图过黑，问候语只以 DOM 文本为准。
5. T13/T15/T16、Git 发布、plugin-off 长驻实例：仍 NOT_RUN。

## 停本轨

```bash
node scripts/dsh-dev/cli.mjs stop   # 只停 14327
# 只结束监听 18082 的本轨 Python；禁止动 4327/8000/5173
```
