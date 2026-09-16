# 本机正式候选 v0.9.0.0（2026-09-16）

loopback，不上公网。产品仍 PARTIAL。不是 M1 DONE。

## 版本与环境

| 项 | 值 |
|---|---|
| VERSION | 0.9.0.0 |
| 驾驶舱 | `http://127.0.0.1:6677/` |
| 比赛看板 | `http://127.0.0.1:15173/` |
| 合成 HTTP | `http://127.0.0.1:18082/` |
| 比赛 API | `http://127.0.0.1:8000/` |

## 备份与回退

- BoardSpec sqlite：G6 `Connection.backup()` → restore-sandbox，未覆盖活库、未抄 WAL。
- 6677 runtime：现役 `.context/dsh-dev/runtime`；`--fresh` 另开空目录，验完已切回。
- 回退代码：同 runtime，`--plugin-path` 指回已验证构建后 stop/start，不用会编原仓的官方 `reload`。

## 关键路径（已核）

驾驶舱未认证 401；已存说明 v15／新板 v9／原板 v9 可读；人群行动 `auto_send=0`。比赛看板进程独立，不内嵌。

## 仍开放

T13 完整（131GB 归档禁止）、T16 SLO、T17 触控／读屏、M2 Figma／WATERFALL 真数据、公网部署。
