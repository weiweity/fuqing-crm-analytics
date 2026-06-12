# FIX-M1: ETL 调度器 (W6.5)

修复 audit 关键发现 **M1** (P0 必修) — W6 通知永远跑不到因为项目内 0 个 scheduler，PRD §4.2「每日 9 点自动刷新」验收 50% 缺失。

## 设计

- **每日 8:30 跑** `python scripts/run_etl.py --update`（8:30 给 9 点 dashboard 留 30min buffer）
- **跨平台**: Mac launchd plist + Windows Task Scheduler XML
- **失败告警**: TaskScheduler / launchd 失败时自动触发管理员通知 + W6 lark-cli 单独 oncall 通知
- **CLAUDE.md 合规**: 走 12 步流程；不在 main 改代码（在 `fix/m1-w6-scheduler` 分支）

## 文件

| 文件 | 平台 | 用途 |
|------|------|------|
| `com.fuqing.etl.daily.plist` | Mac | launchd 调度配置（每日 8:30 跑 --update）|
| `etl_daily_taskscheduler.xml` | Windows | Task Scheduler 调度配置（每日 8:30 跑 --update）|
| `install_macos.sh` | Mac | 一键安装 + 验证 |
| `install_windows.ps1` | Windows | 一键安装 + 验证（需 PowerShell 管理员）|
| `README.md` | - | 本文件 |

## Mac 安装

```bash
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
bash scripts/etl/scheduler/install_macos.sh
```

会做：
1. 复制 plist 到 `~/Library/LaunchAgents/com.fuqing.etl.daily.plist`
2. `launchctl load` 加载
3. `launchctl list | grep fuqing` 验证

## Windows 安装

```powershell
# PowerShell 管理员
cd "C:\Users\hutou\Desktop\fuqin-date\fuqing-crm-analytics"
.\scripts\etl\scheduler\install_windows.ps1
```

会做：
1. 读取 XML
2. 替换项目根路径
3. `Register-ScheduledTask` 注册 `\Fuqing\FuqingETLDaily`
4. 验证

## 手动验证 (跨平台)

```bash
# 1. 同步项目根 / Python 路径
export PYTHONPATH="$(pwd)"

# 2. 手动跑一次 (验证 ETL 路径)
python3 scripts/run_etl.py --update

# 3. 看 log
tail -f /tmp/fuqing-etl-scheduler.log  # Mac
# Windows: Event Viewer -> Task Scheduler
```

## 卸载

**Mac**:
```bash
launchctl unload ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
rm ~/Library/LaunchAgents/com.fuqing.etl.daily.plist
```

**Windows**:
```powershell
Unregister-ScheduledTask -TaskName "FuqingETLDaily" -Confirm:$false
```

## 失败告警链路

```
[ETL run 失败]
  ↓
[run_etl.py exit code != 0]
  ↓
[TaskScheduler / launchd 检测]
  ↓
[launchd/TaskScheduler 系统级失败通知]
  ↓
[W6 集成: pipeline.py run_full_etl() 调 notify_etl_complete(status='failed')]
  ↓
[lark-cli → 飞书私聊 oncall (NOTIFY_OPEN_IDS 配置)]
```

## 注意事项

1. **PYTHONPATH 必需**: plist 显式设 `PYTHONPATH` 指向项目根（CLAUDE.md 启动项）
2. **工作目录**: plist / XML 显式设 `WorkingDirectory` 指向项目根
3. **lark-cli 路径**:
   - Mac: `/Users/hutou/homebrew/bin/lark-cli`（plist env PATH 包含）
   - Windows: 需改成 `lark-cli.bat` 路径（暂未配，依赖未来部署 runbook）
4. **首次跑前**: 必须先 `cp .env.example .env` 并填真 `NOTIFY_OPEN_IDS`（不然 W6 通知 graceful skip）

## 设计权衡

- **8:30 而非 9:00**: 8:30 跑完（假设 30min wall time）→ 9:00 dashboard 数据 ready
- **Background ProcessType**: 跑批不阻塞 shell，launchd 不强制保持进程
- **RunAtLoad false**: 不在 launchd 加载时跑（避免误触发）
- **KeepAlive false**: 跑完就退，下次按 schedule 触发
