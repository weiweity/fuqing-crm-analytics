# DMP 爬虫定时调度配置

## 问题背景
达摩盘单品洞察数据 T+1 跨日更新：6/7 的数据 6/8 下午 15:00 才出。
早上 9:00 跑批必然抓不到（会拿到 6/6 旧值）。

## 解决方案
分时段跑批 + `T_OFFSET` 环境变量动态控制：

| 时段 | 调度 | T_OFFSET | 抓的日期 | 原因 |
|---|---|---|---|---|
| 早 9:00 | morning.plist | 2 | 今天-2 (6/6) | 保险，6/6 数据已稳 |
| 下午 16:00 | afternoon.plist | 1 | 今天-1 (6/7) | 达摩盘 15:00 更新，16:00 跑准点 |
| 晚 21:00 (可选) | evening.plist | 0 | 今天 (6/8) | 兜底，今天数据如果出了也抓 |

## 启用方法

```bash
# 加载调度
launchctl load ~/Library/LaunchAgents/com.fuqing.dmp-scraper.morning.plist
launchctl load ~/Library/LaunchAgents/com.fuqing.dmp-scraper.afternoon.plist

# 查看状态
launchctl list | grep fuqing

# 卸载
launchctl unload ~/Library/LaunchAgents/com.fuqing.dmp-scraper.morning.plist
```

## plist 文件位置
- `~/Library/LaunchAgents/com.fuqing.dmp-scraper.morning.plist`
- `~/Library/LaunchAgents/com.fuqing.dmp-scraper.afternoon.plist`

## 手动覆盖
```bash
# 今天抓昨天的（手动补跑）
T_OFFSET=1 python3 dmp_master.py --items

# 极端情况：今天抓今天（达摩盘可能已更新）
T_OFFSET=0 python3 dmp_master.py --items
```

## 日志
- 早：`/tmp/fuqing-dmp-scraper-morning.log`
- 下午：`/tmp/fuqing-dmp-scraper-afternoon.log`
- 错误：`.err` 同名

## 注意
- 跑批前确保 Chrome 未在用（避免 chrome_profile 锁冲突）
- 第一次跑会触发登录态检测（headless=True 模式下会复用 chrome_profile Cookie）
