# DMP 项目功能需求

> 记录用户提出但目前尚未实现的功能
> 格式：FEAT-YYYYMMDD-XXX

---

## [FEAT-20260403-001] 抓取完成后自动同步CSV到frontend目录

**Logged**: 2026-04-03T18:10:00Z
**Priority**: medium
**Status**: pending
**Area**: automation

### Requested Capability
每次抓取完成后，自动将 core/ 下的 data.csv、data2.csv、data3.csv 复制到 frontend/ 目录，无需手动操作。

### User Context
当前流程：跑完抓取 → 手动 cp csv 到 frontend → 刷新看板。经常忘记同步导致看板数据不是最新的。

### Complexity Estimate
simple (3行shell命令或python脚本)

### Suggested Implementation
在 dmp_master.py 的汇总结果部分追加同步代码：
```python
import shutil
for f in ['data.csv', 'data2.csv', 'data3.csv']:
    src = os.path.join(Config._SCRIPT_DIR, f)
    dst = os.path.join(os.path.dirname(Config._SCRIPT_DIR), 'frontend', f)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        log(f"已同步 {f} 到 frontend")
```

### Metadata
- Frequency: recurring (每次抓取后)
- Related Features: 看板展示, 定时任务
