# DMP 项目错误日志

> 记录所有抓取失败、选择器失效、异常退出等错误事件
> 格式：ERR-YYYYMMDD-XXX

---

## [ERR-20260403-001] selector_engine.py Windows硬编码路径

**Logged**: 2026-04-03T18:10:00Z
**Priority**: high
**Status**: pending
**Area**: config

### Summary
selector_engine.py 第18行硬编码了 Windows 路径 `C:\Users\Tyuan\Desktop\DMP test`，导致在 Mac 上 `save_config()` 和 `_append_log()` 静默失败，选择器变更无法持久化。

### Error
```
CONFIG_DIR = r"C:\Users\Tyuan\Desktop\DMP test"
SELECTORS_FILE = os.path.join(CONFIG_DIR, "selectors.json")
```
Mac 上该路径不存在，`json.dump()` 写入时不会报错（因为不会触发 os.path.exists 检查失败的分支），但配置实际未保存。

### Context
- 文件：core/selector_engine.py 第17-20行
- 影响：AI 修复选择器后无法写入 selectors.json，下次运行仍然用旧选择器

### Suggested Fix
将 `CONFIG_DIR` 改为使用 `os.path.dirname(os.path.abspath(__file__))` 动态获取，与 dmp_common.py 的 `get_script_dir()` 保持一致。

### Metadata
- Reproducible: yes (所有非Windows环境)
- Related Files: core/selector_engine.py, core/selectors.json
- **Status**: ✅ resolved (2026-04-03)

---

## [ERR-20260403-002] 资产诊断数据全同值（弹窗干扰+距离算法）

**Logged**: 2026-04-03T18:30:00Z
**Priority**: high
**Status**: resolved
**Area**: data-quality

### Summary
第一次运行抗变异版选择器时，8个AIPL指标全部提取到相同值（28150296），原因是：
1. 达摩盘"AI识人"弹窗遮挡页面，ESC键可关闭但关闭后数据区域可能未完全刷新
2. 原始的距离算法有bug：父级搜索时取到的是"最大的数字"而非"最近的数字"

### Error
```
解析后的数据: {'initial': 28150296, 'zhuanfaxian': 28150296, 'zhuanzhongcao': 28150296, ...}
⚠️ 严重警告：所有8个指标值完全相同(28150296)！
```

### Context
- 文件：core/dmp_scraper.py extract_aipl_data()
- 触发：达摩盘资产诊断页面弹出"AI识人人群纠偏"推广弹窗

### Fix Applied (已修复)
1. **增强弹窗关闭**：增加15种关闭按钮选择器 + ESC键 + 点击外部区域三重策略
2. **距离优先算法**：找到标签元素后，收集附近所有候选数字，用欧几里得距离选**最近**的那个（而非最大的）
3. **全同值检测**：如果所有字段值完全相同，自动判定为异常并拒绝保存数据

### 验证结果
修复后 8/8 字段中有 7 个完美匹配截图值，Engage(种草)仍有偏差（离TOTAL太近被抢占了），后续可优化

### Metadata
- Related Files: core/dmp_scraper.py
