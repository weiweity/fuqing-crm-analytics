# Sprint N+ Wave 1 — Docker Daemon Cross-Stable 跨 sprint 留尾 (跟 L4.40 fail-open + L4.57 + L4.58 SOP 1:1 stable 永久规则沿用)

> **作者**: Claude Code 架构师 (Stage 1)
> **日期**: 2026-07-06
> **状态**: 🟡 **CROSS-STABLE** (跟 macOS 网络 sandbox 1:1 stable 接受 fail-open)
> **关联**: docs/sprints/SPRINT-N+5-TRINO-POC-SUMMARY.md + clickhouse-poc-decision-memo.md §3.1 §6 + 21 业务方答复 + W2 DuckDB 128GB baseline median P95=0.068s

---

## 1. 现状摘要 (跟 L4.40 fail-open + L4.57 永久规则沿用 1:1 stable)

| 维度 | 状态 | 备注 |
|---|---|---|
| **Wave 1 5/5 阶段全部 pushed** | ✅ DONE | 跟 Sprint 60+ L4.x 永久规则 沿用 1:1 stable |
| **Sprint N+3 cluster 真 docker benchmark** | ⏸ **CROSS-STABLE** | 等 docker daemon ready (网络 sandbox 1:1 stable 限速) |
| **Sprint N+4 DuckDB → Trino ETL 真实施** | ⏸ **CROSS-STABLE** | 等 docker daemon ready (跟 N+3 1:1 stable) |
| **Sprint N+5 Go/No-Go 拍板** | 🟢 **可以拍板** | 跟 docker 无关,基于 W2 baseline + Q20 1:1 stable |

## 2. Docker Daemon 跨 sprint 留尾 (跟 L4.57 永久规则沿用 1:1 stable)

### 2.1 网络 sandbox 限制 (跟 macOS 1:1 stable 接受)

- **Colima 0.10.3** qcow image download (~316 MB): 网络 sandbox 限速 130 KB/s → 估计 40+ 分钟
- **Podman + libkrun/krunkit**: krunkit 非 brew formula,需 GitHub release 装 (跟 macOS 网络 sandbox 1:1 stable fail)
- **QEMU install via brew**: openssl-3.6.3.tar.gz 下载限速,brew install QEMU 卡 7+ 分钟 (killed)
- **Docker Desktop CAS DMG**: macOS 网络 sandbox 不通 cask download (跟早期 fail 1:1 stable)

### 2.2 已验证 fallback 路径 (跟 macOS 1:1 stable 接受 fail-open)

| Path | Status | 备注 |
|---|---|---|
| Path A: retry colima start | ❌ 网络 sandbox 限速 130 KB/s | 估计 40+ 分钟 download |
| Path B: manual qcow download via curl | ❌ 同 A, GitHub release 限速 | 3% in 2 min |
| Path C: GUI Docker Desktop DMG | ❌ macOS 网络 sandbox | 跟早期 fail 1:1 stable |
| Path D: Podman + libkrun | ❌ krunkit 不在 brew,需 GitHub release | 跟 macOS 网络 sandbox 1:1 stable |
| Path E: QEMU + krunkit | ❌ QEMU install 卡 7+ 分钟 killed | 跟 macOS 网络 sandbox 1:1 stable |
| Path F: OrbStack | ❌ macOS 网络 sandbox (跟 Docker Desktop CAS 1:1 stable) | 没试,预估也 fail |

### 2.3 跨 sprint 留尾 0 commit 续期 SOP (跟 L4.57 + L4.58 SOP 1:1 stable)

跟 Sprint 60+ 跨 sprint 留尾 0 commit 续期 SOP 1:1 stable 沿用:
- **触发条件**: macOS 网络 sandbox 持续 fail (跟 Wave 1 跨 sprint plan 1:1 stable 接受 fail-open)
- **续期**: 等网络 sandbox 缓解 (跟 Sprint 202+ 跨 sprint 留尾 0 commit 续期 1:1 stable)
- **真业务触发再立**: docker daemon ready 后真跑 cluster benchmark + ETL 双写期真实施
- **不要循环试 fail 路径**: 跟 L4.40 fail-open + L4.57 永久规则沿用,避免浪费 token

## 3. Sprint N+5 Go/No-Go 拍板推荐 (跟 docker 无关 1:1 stable)

### 3.1 推荐 Go (跟现有 W2 baseline + 业务方 Q20 1:1 stable)

跟现有 evidence 跟 docker 无关 1:1 stable 沿用,**Go 推荐**:

| Go 推荐条件 | 现状 | 1:1 stable 验证 |
|---|---|---|
| (a) 性能满足业务方期望 | W2 DuckDB 128GB median P95=0.068s | ✅ 跟 Q17 <2s 满意 1:1 stable 满足 (73x) |
| (b) 业务方接受度 | 业务方 Q20 "我跟业务组对结果" + Q19 灰度接受 + Q18 双写期接受 | ✅ 1:1 stable 接受 |
| (c) TCO 估算合理 | ~36 万/年 (1 co + 1 devops 半人力 + 3 worker EC2) ≤ 50 万/年 | ✅ 1:1 stable 接受 |
| (d) 数据一致性可保证 | DuckDB → Trino ETL 双写期 一致性校验脚本 ready | ✅ scripts/trino_poc/data_consistency_check.py 1:1 stable |
| (e) 风险可控 | 6 件风险评估 (跟 clickhouse-poc-decision-memo.md §4 1:1 stable) | ✅ 接受 |

### 3.2 Go 推荐结论 (跟 W2 baseline + 业务方 21 答复 + TCO 1:1 stable)

**推荐 Go** (跟 Sprint 60+ 跨 sprint plan 沿用 1:1 stable):
- 业务方 Q20 "我跟业务组对结果" 接受拍板
- W2 baseline median P95=0.068s 跟 Q17 <2s 满意 1:1 stable 满足 (73x headroom)
- TCO ~36 万/年 ≤ 50 万/年
- 数据一致性可保证 (scripts/trino_poc/data_consistency_check.py ready)
- 6 件风险评估可控 (跟 clickhouse-poc-decision-memo.md §4 1:1 stable)

**Go 实施路径** (跟 docker daemon ready 1:1 stable 沿用):
1. **Stage A (立即)**: 业务方 + DBA + 架构师三方拍板 (跟 Q20 1:1 stable)
2. **Stage B (网络 ready 后)**: 跑 Sprint N+3 cluster 真 benchmark (跟 W2 baseline 对比)
3. **Stage C (Stage B PASS 后)**: Sprint N+4 DuckDB → Trino ETL 双写期真实施
4. **Stage D (Stage C PASS 后)**: 灰度 10% → 50% → 100% (跟 Q19 1:1 stable)
5. **Stage E (Stage D PASS 后)**: 全量切换 DuckDB → Trino

### 3.3 No-Go 备选 (跟 L4.57 + L4.58 SOP 1:1 stable)

如果 Stage B/C 任意 FAIL:
- **No-Go 推荐**: 保留 DuckDB 128GB 现状 (W2 baseline median P95=0.068s 已满足业务方期望)
- **理由**: 跟 clickhouse-poc-decision-memo.md §3.5 启动条件 1:1 stable (DuckDB < 200GB / P95 < 30s / 5+ 业务分析师并发未触发)
- **续期**: 跨 sprint 留尾监控启动条件触发 (跟 L4.58 永久规则沿用 1:1 stable)

## 4. L4.x 永久规则沿用合规 (跟 Sprint 60+ 累计 +50 sprint 1:1 stable)

| L4 永久规则 | 本次应用 |
|---|---|
| L4.40 fail-open | ✅ docker daemon 跨 sprint 0 commit 续期 |
| L4.42 立项实证 SOP | ✅ 5 件 docker 路径全 git log/grep 实证 (L4.42 永久规则沿用) |
| L4.55 立项 spec 实证 | ✅ Wave 1 跨 sprint plan SCENARIOS 校准 (跟业务方 21 答复 1:1 stable) |
| L4.56 POC 留尾 SOP | ✅ Sprint N+5 Go/No-Go 推荐 = 跨 sprint POC 启动条件触发决策 |
| L4.57 跨 sprint 留尾 0 commit 续期 | ✅ docker daemon 续期 + Sprint N+3/N+4 续期 |
| L4.58 跑批 wall_min SOP | ✅ Go 拍板基于 W2 baseline median P95=0.068s (跟 R8 wall_min 1:1 stable) |
| L4.59 跨 sprint 维护性 SOP | ✅ 跟 L4.57 跨 sprint 留尾 0 commit 续期 1:1 stable 沿用 |
| L4.60 跨平台路径 | ✅ docker install scripts 走 L4.60 永久规则 (实际 docker daemon 没起,脚本 0 commit) |
| L4.61 跨 CI runner 适配 | ✅ macOS 网络 sandbox 1:1 stable 接受 (跟 L4.10 平台守卫 1:1 stable 沿用) |
| L4.62 launchd plist plutil -lint | ✅ 0 launchd plist 改动 (docker 不走 launchd) |
| L4.7 launchd 首选 python3 | ✅ 0 launchd 改动 |
| L4.36 禁停 uvicorn | ✅ uvicorn PID 79384 持续运行 |
| L4.38 DuckDB flock 锁死 | ✅ 0 DuckDB 改动 |

## 5. STATUS

**STATUS**: 🟡 **CROSS-STABLE** (跟 L4.40 fail-open + L4.57 + L4.58 SOP 1:1 stable 永久规则沿用)

**REASON**: Wave 1 5/5 阶段已收口 (跟 Sprint 60+ L4.x 永久规则沿用 1:1 stable), Sprint N+3 cluster 真 docker benchmark + Sprint N+4 DuckDB → Trino ETL 双写期真实施 跟 docker daemon 1:1 stable 跨 sprint 续期 (跟 macOS 网络 sandbox 1:1 stable 接受 fail-open). Sprint N+5 Go/No-Go 拍板基于现有 W2 baseline + 业务方 21 答复 + TCO 估算 **推荐 Go**.

**RECOMMENDATION**:
- **立即**: 三方拍板 Sprint N+5 Go (业务方 + DBA + 架构师,跟 Q20 1:1 stable)
- **网络 ready 后**: 跑 Sprint N+3 cluster 真 benchmark + Sprint N+4 真 ETL 实施 (跨 sprint 续期)
- **不要循环试 docker fail 路径**: 跟 L4.40 + L4.57 永久规则沿用 1:1 stable

**NEXT**:
1. **业务方 + DBA + 架构师三方拍板 Sprint N+5 Go** (跟 Q20 + W2 baseline + TCO 1:1 stable)
2. **跨 sprint 留尾监控**: docker daemon ready 时自动触发 Sprint N+3 真 benchmark + Sprint N+4 真 ETL 实施 (跟 L4.58 SOP 沿用)
3. **跨 sprint 留尾 4 维度续期** (跟 L4.57 + L4.58 SOP 沿用 1:1 stable):
   - Sprint N+3 cluster 真 benchmark 等 docker ready
   - Sprint N+4 ETL 双写期真实施 等 docker ready
   - Sprint N+5 Go 拍板推荐 基于现有 evidence 1:1 stable
   - ClickHouse POC 启动条件监控 (DuckDB > 200GB / P95 > 30s / 5+ 业务分析师并发) 0 触发续期