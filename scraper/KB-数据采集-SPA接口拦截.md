# 知识库：SPA 场景下的数据采集方法论

> **适用场景**：单页应用（SPA）中的图表数据抓取
> **创建时间**：2026-04-12
> **关键字**：Network 拦截、API 逆向、SPA 爬虫、桑基图、Canvas 图表
> **关联项目**：达摩盘数据采集（DMP_test_package）

---

## 一、问题背景

### 1.1 传统爬虫为什么会失效

| 方法 | 原理 | 为什么对 SPA 失效 |
|---|---|---|
| 请求 HTML + 正则 | 服务端返回完整 HTML | SPA 的 HTML 是空壳，数据由 JS 动态渲染 |
| requests/BeautifulSoup | 静态页面解析 | 页面内容不在 HTML 里，在 API 响应里 |
| Selenium 截图 | 截图识别 | 能看到图，但拿不到数字 |

**SPA 的本质**：浏览器先下载一个空页面，执行 JavaScript，JavaScript 再通过 Ajax 请求 API 拿到数据，最后把数据渲染成 HTML。

```
传统网站：
服务器 → 返回完整 HTML（包含数据）→ 爬虫直接解析

SPA：
服务器 → 返回空 HTML + JS → 浏览器执行 JS → JS 请求 API → 渲染数据
                                              ↑
                                         爬虫在这里
```

### 1.2 达摩盘的数据流

达摩盘的桑基图不是用 `<div>` 拼出来的，是用 **Canvas** 或 **SVG** 画的。

```
HTML 里只有 Canvas 占位符：
<canvas class="sankey-canvas">（占位符，内部数据不在 DOM 里）

实际数据路径：
浏览器 JS → 请求 /asset/deeplink/transfer → 拿到 JSON → 用 D3.js/echarts 画图
```

**结论**：DOM 抓取根本拿不到桑基图数字，因为数字在 Canvas 内部，根本不在 HTML 里。

---

## 二、核心方法：Network 拦截

### 2.1 什么是 Network 拦截

浏览器和服务器之间的所有 HTTP 通信，都经过 Network 层。用工具截取这段通信，就是「Network 拦截」。

```
正常请求：
浏览器 → API 请求 → 服务器 → JSON 响应 → 浏览器渲染

拦截后：
浏览器 → API 请求 → 服务器 → JSON 响应 → 你的代码截取 → 也发给浏览器
                 ↑
           你在这里拿到原始数据
```

Playwright 提供的 `page.on('response')` 就是这个能力：**监听所有浏览器发出的 HTTP 响应**。

### 2.2 达摩盘的两个关键 API

| API | 完整路径 | 职责 | 关键字段 |
|---|---|---|---|
| transfer/overview | `asset/deeplink/transfer/overview` | 人群快照（initial 值） | `initialAsset.list[].uv` |
| transfer | `asset/deeplink/transfer` | 流转矩阵（桑基图数值） | `data.list[].uv` |

**为什么是两个？**

桑基图需要两组数据才能画出来：
- **Overview**：回答「起点有多少人」
- **Transfer**：回答「人往哪里流」

两组数据合起来，才是完整的流转图。

### 2.3 拦截代码模板

```python
from playwright.sync_api import sync_playwright

def intercept_api():
    captured_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # ✅ 关键：在访问页面之前就注册拦截器
        page.on('response', lambda response: handle_response(response, captured_data))

        # 访问页面
        page.goto('https://dmp.taobao.com/...')
        page.wait_for_timeout(3000)  # 等待 API 返回

        browser.close()

    return captured_data


def handle_response(response, captured_data):
    url = response.url
    if 'dmp.taobao.com' not in url:
        return

    # 判断是哪个 API
    if '/transfer/overview' in url:
        data = response.json()
        captured_data['overview'] = data

    elif '/asset/deeplink/transfer' in url:
        data = response.json()
        captured_data['transfer'] = data
```

### 2.4 URL 参数识别法（核心技巧）

```
URL = https://dmp.taobao.com/api/asset/deeplink/transfer?startDate=2026-03-28&bizDate=2026-03-29&statusId=2001&...
                                                                    ↑           ↑
                                                              时间范围      人群状态
```

通过 URL 参数，你能知道：
- `startDate` / `bizDate` → 统计日期范围
- `statusId` → 哪个人群（2001=发现，2002=种草，2003=互动，2004=行动，2006=首购，2007=复购，2008=至爱，0=新增）
- 换日期/换人群 → URL 参数变化 → 你知道该请求哪个接口

---

## 三、判断用哪种方法

### 3.1 决策树

```
第一步：确认数据在哪里
│
├─ 数据在普通 HTML DOM 里？
│   └─ ✅ 用 requests + BeautifulSoup / Selenium DOM 抓取
│
├─ 数据在 Canvas / SVG 图表里？
│   └─ ❌ DOM 抓不到 → 走下一步
│
├─ 页面是 SPA（Vue / React / Angular）？
│   └─ ✅ 大概率走 API → 用 Network 拦截
│
└─ 页面是纯静态页面（没有 Ajax 请求）
    └─ ✅ 数据在 HTML 里隐藏，用 requests 深度抓取
```

### 3.2 数据获取方法对比

| 方法 | 数据在哪 | 难度 | 速度 | 稳定性 |
|---|---|---|---|---|
| requests + 正则 | HTML 源码 | ⭐ | 快 | 差（页面改结构就坏） |
| BeautifulSoup DOM 解析 | HTML DOM | ⭐⭐ | 快 | 中（依赖 CSS 选择器） |
| Selenium 截图 + OCR | 视觉呈现 | ⭐⭐⭐ | 慢 | 差（OCR 精度有限） |
| **Network 拦截（API）** | **API 响应 JSON** | ⭐⭐ | **快** | **高（API 通常比 UI 稳定）** |
| Playwright DOM 抓取 | JS 渲染后 DOM | ⭐⭐ | 中 | 中（依赖 DOM 结构） |

### 3.3 什么时候用 Network 拦截

**适合的场景：**
- SPA 应用（Vue/React/Angular）
- 图表数据（ECharts、Highcharts、D3.js、D3 桑基图）
- 后台管理系统（数据由 API 提供，不在 HTML 里）
- 数据需要高精度（OCR 有误差，API 直接拿原始值）

**不适合的场景：**
- 页面做了严格的反爬（IP 限制、请求签名）
- 数据需要登录且登录态难以复现
- API 返回加密/混淆数据

---

## 四、踩过的坑（经验总结）

### 4.1 坑 1：拦截器注册太晚

**错误：**
```python
page.goto('...')      # 先访问了页面
# 此时 API 请求已经发出去了
page.on('response', ...)  # 注册太晚，错过了
```

**正确：**
```python
page.on('response', ...)  # 先注册拦截器
page.goto('...')           # 再访问页面
```

**原因**：有些 SPA 在 `page.goto()` 之后立即发出 API 请求，如果不在访问前注册，会漏掉第一个请求。

---

### 4.2 坑 2：把 transfer/channel 当成流转数据源

**错误认知：**
> transfer/channel 返回的是桑基图的流转数据

**实际情况：**
- `transfer/channel` → 是**渠道明细表**（哪个渠道带来多少人），与桑基图无关
- `asset/deeplink/transfer` → 才是桑基图的流转数据

**怎么发现的：**
对比 Network 响应里的数据，和页面上桑基图显示的数字。数字对不上的那个 API 就不是你要的。

---

### 4.3 坑 3：混淆 overview 和 transfer 的职责

**错误：**
用 transfer API 的返回值当 initial 值。

**正确：**
- `transfer/overview` 的 `initialAsset.list[].uv` → initial（起点人群）
- `transfer` 的 `data.list[].uv` → 流转值（桑基图的边权重）

---

### 4.4 坑 4：DOM 抓取当作主方案

**问题：**
达摩盘用 Canvas 画桑基图，DOM 里只有占位符，用 DOM 抓取数字永远是错的或 0。

**解决：**
Network 拦截拿到的是**后端返回的原始数据**，精度 100%，不受前端渲染影响。

---

## 五、PM 能从中得到什么

### 5.1 产品设计层面

**理解「数据从哪来」：**
当你知道桑基图数据是后端 API 返回的，就会理解：
- 为什么切换日期需要等待（API 请求）
- 为什么数据有延迟（后端 T+1 计算）
- 为什么有时候数据是 0（API 还没算完）

**理解「前端和后端的边界」：**
- 前端负责交互和渲染
- 后端负责计算和存储
- PM 提数据需求时，要搞清楚「数据从哪个环节取」

### 5.2 数据敏感度

| 现象 | PM 应该联想到 |
|---|---|
| 数据指标突然变成 0 | API 是否失败？网络问题？还是数据没跑完？ |
| 图表加载慢 | 前端渲染问题还是后端接口慢？ |
| 报表和实际不符 | 数据口径是否一致？前端显示和数据库是否是同一个表？ |
| 定时数据更新 | 是否了解 ETL 作业时间窗口？ |

### 5.3 技术决策支持

**什么场景该要求「提供 API」而不是「页面截图」？**
- 需要做二次分析（截图无法计算）
- 需要自动化报表（人工截图效率低）
- 需要做数据对比（跨时间、跨人群）

**什么场景接受「截图/导出」就够了？**
- 临时性需求，不需要自动化
- 数据量小，人工可接受
- 没有技术资源对接 API

---

## 六、AI 加速复用指南

### 6.1 让 AI 快速解决问题的提示词模板

**遇到 SPA 数据抓取问题，直接用这个提示词：**

```
我需要抓取一个 SPA（单页应用）的数据，
具体是这个平台：[平台名 + URL]
数据在 [图表类型，如桑基图/折线图/柱状图] 里，
我已经打开 DevTools 看到有两个 XHR 请求：
1. [请求 1 的 URL 模式]
2. [请求 2 的 URL 模式]
返回的数据结构是 [你观察到的 JSON 结构]

请帮我：
1. 判断这两个 API 是否是图表的数据来源
2. 写出 Playwright Network 拦截代码
3. 告诉我如何从 URL 参数判断统计日期和人群状态
```

**遇到 Canvas/SVG 图表抓取，用这个提示词：**

```
[平台名] 的 [图表名] 是用 Canvas/SVG 画的，
我需要拿到这个图表背后的原始数据，
已知：
- 图表数据是通过 XHR 请求获取的
- 请求 URL 包含 [已知参数]
- 平台需要登录，Cookie 在 [说明 Cookie 来源]

请帮我：
1. 设计 Network 拦截方案
2. 处理登录态（Cookie 自动刷新）
3. 写出完整抓取代码
```

### 6.2 快速定位 API 的操作流程

当你面对一个新平台，不知道数据在哪，按这个顺序操作：

```
1. 打开浏览器 DevTools（F12）
2. 切到 Network 面板，筛选 XHR / Fetch
3. 触发你想要的数据（换日期/选人群/刷新）
4. 观察哪个请求的响应体最像数据（找 JSON）
5. 记录这个请求的：
   - 完整 URL（含 Query Parameters）
   - 请求 Method（GET 还是 POST）
   - 响应体结构（预览即可）
6. 换一个条件（不同日期/不同人群），看哪个参数变了
   → 变化的参数 = 你需要控制的变量
7. 用 Playwright 复现这个请求
```

### 6.3 让 AI 学习的最小样本

给 AI 以下信息，AI 就能帮你写出完整方案：

```
【输入模板】
- 目标平台：
- 图表类型：Canvas / SVG / 普通 DOM
- 是否 SPA：
- 我观察到的 API（可选）：
- 是否需要登录：
- 数据用途：
```

---

## 七、知识延伸

### 7.1 其他适合 Network 拦截的平台

| 平台 | 数据类型 | 关键 API 路径 |
|---|---|---|
| 生意参谋 | 竞争分析图、流量来源 | `betternative/...` |
| 京东商智 | 行业趋势图 | `api/mn/...` |
| 抖音创作者后台 | 作品数据趋势图 | `aweme/.../data` |
| 微信公众号后台 | 图文分析 | `appmsg` |
| 淘宝生意参谋 | 实时数据 | `wapgw` |

**通用方法**：打开 F12 → Network → 触发数据加载 → 找 XHR 请求 → 分析 URL 参数和响应结构。

### 7.2 当 API 有签名怎么办

有些 API 请求带了 `sign` 或 `token` 参数，由前端 JS 动态生成。

**方案 1：逆向 JS（最彻底）**
- 用 Chrome DevTools 的 Sources 面板，找到生成签名的 JS 函数
- 把这个逻辑翻译成 Python

**方案 2：Selenium 完全模拟（最省事）**
- 用 Selenium 控制真实浏览器执行 JS
- 让浏览器自动完成签名过程
- 缺点：慢，容易被检测

**方案 3：找无需签名的 API**
- 有些平台有多套 API，PC 版和 H5 版的签名机制不同
- 尝试找移动端版本或 H5 版本

### 7.3 当登录态容易失效怎么办

**Cookie 自动刷新方案：**

```python
def ensure_login(page, cookie_file='cookies.json'):
    """检查 Cookie 是否有效，无效则重新登录"""
    page.goto('https://login.platform.com')
    page.wait_for_timeout(1000)

    # 尝试加载 Cookie
    if Path(cookie_file).exists():
        with open(cookie_file) as f:
            cookies = json.load(f)
        page.context.add_cookies(cookies)

    # 验证是否登录成功（访问需要登录的页面）
    page.goto('https://platform.com/need-login-page')
    if '登录' in page.title():
        # 执行登录流程
        do_login(page)
        # 保存新 Cookie
        with open(cookie_file, 'w') as f:
            json.dump(page.context.cookies(), f)
```

---

## 八、Checklist

当你遇到一个新的数据采集需求时，用这个清单来思考：

```
□ 1. 数据在 HTML 源码里吗？→ 是 → requests + BeautifulSoup
□ 2. 数据是 JS 动态渲染的 SPA 吗？→ 是 → 继续
□ 3. 数据在 Canvas/SVG 里吗？→ 是 → Network 拦截
□ 4. 有没有现成的 API 可以调用？→ 有 → 直接调 API
□ 5. 需要登录吗？→ 是 → 先搞定 Cookie
□ 6. 有反爬吗？→ 有 → 评估成本，或找其他数据源
□ 7. 数据量大吗？→ 大 → 考虑增量方案（断点续传）
□ 8. 需要定时抓取吗？→ 是 → 配自动化 + 异常告警
□ 9. 数据精度要求高吗？→ 高 → 必须用 Network 拦截，不能用 OCR
□ 10. PM 是否需要数据接口？→ 是 → 推动提供 API，而不是截图
```

---

## 九、核心心法

> **数据在 API 里，不在 DOM 里。**
>
> **Network 拦截的本质是：绕过前端渲染，直接拿后端数据。**
>
> **所有 ECharts / D3.js / Canvas 图表，都可以用 Network 拦截拿到原始数据。**
>
> **拦截器要提前注册，在页面访问之前。**

---

*文档版本：v1.0 | 2026-04-12 | 来自达摩盘数据采集项目实战*
