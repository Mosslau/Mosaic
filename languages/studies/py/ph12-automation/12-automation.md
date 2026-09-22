# Python 自动化脚本阶段

> 面向日常工作效率提升，本阶段用 Python 把重复劳动固化成脚本——文件批处理、Excel 自动化、日志分析、接口测试、报表生成、邮件通知、定时任务与 CAN 日志解析，同时把「日志 + 错误处理、参数化、可安全重跑、输出可审计」四个工程习惯内化为脚本本能。

## 1. 概述

Python 自动化脚本阶段的目标是：**用 Python 提升日常工作效率**（roadmap 第 12 节目标）——把重复的手工操作（整理文件、填报表、看日志、试接口、发邮件、跑定时任务）变成一条命令。它是整个学习路线的「生产力」一站：前面 ph05 文件操作与异常处理阶段、ph06 标准库阶段（re/csv/json/logging）、ph08 第三方库阶段（openpyxl 认识）积累的单点能力，在本阶段被组合成**完整可用的脚本工具**；ph11 数据库与缓存阶段的「批量入库、从库取数」又让脚本有了数据落地的去处（ph11 的 project 扩展方向已预告「向 ph12+ 自动化脚本阶段的时间序列报表过渡」）。本阶段把四个必会概念内化为脚本习惯——**自动化脚本也要有日志和错误处理、重复任务应参数化、脚本要能安全重跑、输出结果要可审计**——这是区分「一次性脚本」和「可复用工具」的分水岭。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件批处理 | pathlib 遍历/归档/重命名、shutil 移动、幂等批量操作（roadmap 示例） |
| Excel 自动化 | openpyxl 读写 xlsx、样式、多 Sheet、报表生成 |
| 日志分析 | 正则逐行解析、Counter 统计、无效行容错 |
| 接口测试 | requests/urllib、超时与重试、状态码与异常处理、本地起服务离线测试 |
| 报表生成 | csv 标准库读写、CSV→Excel 汇总报表、可审计输出 |
| 邮件通知 | smtplib + EmailMessage、附件、本地 SMTP 调试服务器 |
| 定时任务 | schedule 注册任务与调度循环 |
| 远程操作 | paramiko/fabric 概念（SSH 客户端、SFTP 传输） |
| CAN 日志解析 | candump 格式解析、按 ID 统计信号值（格式规约解析的入门样本） |
| 脚本工程化 | logging + 错误处理、argparse 参数化、安全重跑、可审计（四个必会概念） |

这个阶段只涉及**单机日常自动化的完整闭环**——文件批处理、Excel 自动化、日志分析、接口测试、报表生成、邮件发送、定时任务、CAN 日志解析与脚本工程化四要素，**不涉及并发与异步深入（asyncio/aiohttp 大规模并发抓取）、测试工程体系（pytest/fixture/mock/覆盖率/CI）、生产部署运维（Docker、CI/CD、监控告警）和数据分析深入（pandas 透视表与可视化）** — 那些是 [ph14 并发、并行与异步阶段](../ph14-concurrency-async/14-concurrency-async.md)（roadmap 第 14 节）、ph13 测试与工程质量阶段、[ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）和 ph09 数据分析阶段的内容；带格式规约的深度日志解析、反爬与规模化抓取属 [ph18 数据平台分析 / 自动化方向阶段](../ph18-data-platform-automation/18-data-platform-automation.md)（roadmap 第 18 节，目录已建）。爬虫在本阶段只取其起点（requests 拉取 + 解析响应），深入不涉及。本阶段承接 ph11 数据库与缓存阶段——脚本能安全地读写数据、批量入库、从库取数生成报表，爬虫抓取的数据也有了落库与去重的去处。本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

自动化脚本的历史是「**脚本语言在运维与办公场景里逐步接管手工劳动**」的演进。1990 年代 Unix 世界里，**Shell 脚本**是自动化的事实标准——短小、管道强大，但跨平台差、语法脆弱、无法优雅处理复杂逻辑；Python 以「**胶水语言（Glue Language）**」的定位切入：能调用系统命令、处理文本、读写文件，同时语法可读、跨平台，成为「复杂一点的 Shell」的自然替代。随后标准库逐步补齐自动化所需的每一块拼图：**logging**（2003，PEP 282）让脚本从 `print` 调试走向结构化日志；**argparse**（2011，Python 3.2）取代手工 `sys.argv` 解析，命令行参数化有了官方方案；**pathlib**（2014，PEP 428，Python 3.4）把路径操作从字符串拼接升级为面向对象 API，文件批处理自此有了「正统写法」。

第三方生态同期补位：**requests**（2011，Kenneth Reitz，「HTTP for Humans」）把 urllib 的繁琐封装成一句话；**openpyxl**（2010 年代起步，Eric Gazoni 与 Charlie Clark 维护，3.0 于 2021 年发布）成为读写 xlsx 的事实标准；**schedule**（2014 年前后由 Dan Bader 在 GitHub（dbader/schedule）起步，2020 年发布 1.0）提供进程内定时任务的最轻方案；**paramiko**（2003 年由 Robey Pointer 创建）是 Python 的 SSHv2 协议原生实现，**fabric**（1.x 起步，2018 年 2.0 基于 invoke + paramiko 重写）在其上提供「一行命令跑远程任务」的高层封装。Python 3.12 起标准库 **smtpd** 模块被移除（3.10/3.11 起弃用）——本地 SMTP 调试从 `python -m smtpd` 换代为 aiosmtpd 或自建 sink 服务器，本阶段示例 5 用 socketserver 手写一个最小调试服务器，顺便把 SMTP 协议本身看透。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Python 定位为「胶水语言」 | 1990s | 取代复杂 Shell 脚本，跨平台 + 可读语法 |
| logging（PEP 282） | 2003 | 脚本从 print 调试走向结构化日志 |
| paramiko | 2003 | Python 原生 SSHv2 协议实现（Robey Pointer 创建） |
| requests | 2011 | 「HTTP for Humans」——接口调用的事实标准 |
| argparse 进标准库 | 2011（3.2） | 命令行参数化的官方方案（取代 optparse） |
| pathlib（PEP 428） | 2014（3.4） | 面向对象的路径操作成为文件批处理主力 |
| schedule | 2014 起 / 2020 发 1.0 | 进程内定时任务的最轻方案（dbader/schedule） |
| fabric 2.0 | 2018 | 基于 invoke + paramiko 重写，远程任务高层封装 |
| openpyxl 3.0 | 2021 | xlsx 读写的稳定基线（本环境 3.1.5） |
| smtpd 移除 | 2023-2024 | Python 3.12 起移除，本地 SMTP 调试换代为 aiosmtpd / 自建 sink |

本文示例以 **Python 3.13.9** 为基线（本机验证工具链实测版本），验证工具链：openpyxl 3.1.5 + requests 2.32.5（全局已装并实测）+ pytest 8.4.2 + ruff 0.12.0（质量门禁）；schedule 1.2.2、paramiko 5.0.0、fabric 3.2.3 装于一次性临时 venv 实测（venv 为验证产物，读者可自行创建：`python3 -m venv /tmp/ph12-venv && /tmp/ph12-venv/bin/pip install schedule==1.2.2 paramiko fabric`）——schedule 的示例 6 在 venv 中实测通过，paramiko/fabric **本机无 SSH 服务器可连，未做真实连接验证**（3.8 为概念讲解 + 标注）。这个阶段的语法与 API 是 Python 标准库中最稳定的部分——pathlib / re / csv / logging / argparse / smtplib 十余年未变，本文示例在 Python 3.9+ 上几乎可以原样运行（练习 3/4 与 project 用到 `X | None` 联合类型写法，需 Python 3.10+），这正是「自动化脚本要能跑很多年」的底气。

## 3. 语法与参数

### 3.1 文件批处理（pathlib + shutil）

**文件批处理**是自动化最频繁的场景：整理下载目录、归档日志、批量重命名。核心是 **pathlib**（PEP 428）——路径不再是字符串，而是 `Path` 对象，遍历、拼接、改名、移动都是方法调用（ph05 文件操作与异常处理阶段已用 `open()`/`os.path` 入门，本阶段统一升级到 pathlib）。

```python
# 关键片段：examples/ex01-batch-files.py —— 批量归档日志（完整版见示例 1，本机已验证）
from pathlib import Path
import re, shutil

DATE_RE = re.compile(r"app-(\d{4})(\d{2})(\d{2})\.log$")   # 从文件名提取日期
for p in sorted(src.iterdir()):                             # iterdir 遍历全部条目
    if p.is_dir() or p.suffix != ".log":                    # 只看 .log 文件
        continue
    m = DATE_RE.search(p.name)
    target = dest_root / f"{m.group(1)}-{m.group(2)}" / p.name   # 目标目录 2026-09
    if target.exists():                                     # 幂等：已存在 → 跳过
        continue
    shutil.move(str(p), str(target))                        # 移动归档
```

要点：

- **pathlib 常用 API**：`Path.glob("*.log")` 按模式匹配（只匹配文件名）、`rglob` 递归、`iterdir` 全量遍历、`mkdir(parents=True, exist_ok=True)` 递归建目录、`rename`/`unlink`/`stat().st_size`。`glob` 与 `iterdir` 的区别是「只挑匹配的」与「全看一遍」——示例 1 用 `iterdir` 是为了统计非日志文件。
- **`shutil.move` 处理跨目录移动**（`os.rename` 跨文件系统会报错，`shutil` 会先复制再删）；批量复制用 `shutil.copy2`。
- **安全重跑（幂等）模式**：每次动作前先检查「目标是否已存在」——脚本重复执行不会重复移动、不会覆盖（示例 1 第二次运行移动 0 个、跳过 3 个）。
- **坑（路径即对象，别拼接字符串）**：`os.path.join("a", "b")` 是字符串拼接，Windows 分隔符是 `\`、macOS 是 `/`——`Path` 对象跨平台自动处理；再写字符串路径拼接就该被 code review 拦下。

### 3.2 Excel 自动化（openpyxl）

**Excel 自动化**把「手工填表」变成「脚本生成报表」：`Workbook` 建簿、`active` 取默认工作表、`append` 按行追加、`cell` 精确读写、样式对象控制格式（ph08 第三方库阶段已认识 openpyxl 的读与写，本阶段升级到「报表工程」——样式、合计、冻结、重开核对）。

```python
# 关键片段：examples/ex02-excel-report.py —— 车辆状态周报（完整版见示例 2，本机已验证）
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

ws = wb.active
ws.title = "车辆状态周报"
ws.append(HEADERS)                                  # 按行追加：表头
for cell in ws[1]:                                  # 表头样式：加粗白字 + 蓝底
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
for r in rows:
    ws.append(r)                                    # 按行追加：数据
total_row = ws.max_row + 1                          # 合计行（max_row 动态算）
ws.cell(total_row, 1, "合计")
ws.cell(total_row, 4, round(sum(r[3] for r in rows), 1))
ws.freeze_panes = "A2"                              # 冻结表头行
wb.save(out)
```

要点：

- **写入三板斧**：`append`（整行追加）、`cell(row, col, value)`（精确落子，适合合计行）、`merge_cells`（合并单元格做标题）。**读取**用 `load_workbook(path)` 重开（示例 2 存盘后重开核对单元格——报表数字可审计的关键一步）。
- **样式是对象不是字符串**：`Font`（字型）、`PatternFill`（填充）、`Alignment`（对齐）、`column_dimensions[字母].width`（列宽）、`freeze_panes`（冻结窗格）——都是赋值给单元格属性的对象，改动不影响已有数据。
- **坑（`ws.max_row` 是「用过的最大行」不是「数据行数」）**：删过行或样式残留会让 `max_row` 虚高；示例用 `ws.max_row + 1` 追加合计前，先想清楚当前表里到底有几行数据。
- 数据处理别交给 openpyxl：它管「文件格式」，**分析**交给 ph09 的 pandas（`groupby` 统计）或本阶段的 Counter——openpyxl 里手写求和远不如 `sum(r[3] for r in rows)` 一行。

### 3.3 日志分析（正则 + Counter）

**日志分析**是运维与研发的日常：从日志里数出「今天 500 了多少次、哪个 IP 最活跃、几点最忙」。三板斧：**正则**逐行提取字段（ph06 标准库阶段已入门 `re`）、**Counter** 计数（`collections.Counter`，字典的计数升级版）、**统计报表**落盘。

```python
# 关键片段：examples/ex03-log-analyzer.py —— 访问日志统计（完整版见示例 3，本机已验证）
LINE_RE = re.compile(
    r"^(?P<ts>\S+ \S+) (?P<ip>\S+) (?P<method>\S+) "
    r"(?P<path>\S+) (?P<status>\d{3}) (?P<bytes>\d+)$"   # 命名分组，一次取全字段
)
for line in log_path.read_text(encoding="utf-8").splitlines():
    m = LINE_RE.match(line)                               # match 从行首锚定
    if m is None:
        invalid += 1                                      # 无效行计数，不崩溃
        continue
    records.append(m.groupdict())
status = Counter(r["status"] for r in records)            # 状态码分布
print(dict(sorted(status.items())))                       # {'200': 7, '201': 2, ...}
print(status.most_common(1))                              # 最高频
```

要点：

- **正则的三条纪律**：① 用 `re.compile` 编译一次复用（引擎有缓存，但显式编译可读性更好）；② **命名分组** `(?P<name>...)` + `m.groupdict()` 让字段像字典一样取，比 `m.group(1)` 编号可读；③ 日志格式变了正则就得跟着改——**先看一行真实日志再写正则**，别对着文档猜。
- **`re.match`（行首锚定）vs `re.search`（任意位置）**：逐行解析用 `match` + `^` 锚定整行；在长文本里找模式才用 `search`。
- **Counter 是统计主力**：`Counter(x)` 计数、`most_common(n)` 取 Top n、`+`/`-` 合并——比手写字典 `d[k] = d.get(k, 0) + 1` 干净（统计思维与 ph09 数据分析阶段的分组统计同源）。
- **大文件用流式**：`read_text().splitlines()` 会把整个文件读进内存，百万行日志用 `for line in f:` 逐行迭代（内存 O(1)，详见 4.1 原理；project 的扩展方向也提示了这一点）。

### 3.4 接口测试（requests / urllib）

**接口测试**是把「人工开 Postman 试接口」变成脚本：`requests.get` 拉取、`status_code` 看状态、`.json()` 解响应、`timeout` 限时、`raise_for_status()` 抛错。requests 是第三方库（ph08 第三方库阶段已用过），标准库替代是 **urllib.request**——requests 全部能力 urllib 都有，只是繁琐（见下表）。

```python
# 关键片段：examples/ex04-api-test.py —— requests 测本地服务（完整版见示例 4，本机已验证）
r = requests.get(f"{base}/health", timeout=2)      # 超时是铁律：别让脚本挂死
print(r.status_code, r.json())                    # 200 {'status': 'ok'}
r = requests.post(f"{base}/vehicles", json={"vin": "V004"}, timeout=2)
print(r.status_code, r.json())                    # 201 {'created': 'EV-004'}
try:
    r = requests.get(f"{base}/nope", timeout=2)
    r.raise_for_status()                          # 4xx/5xx 抛 HTTPError
except requests.exceptions.HTTPError as e:
    print("404 ->", type(e).__name__)             # HTTPError
```

| 能力 | requests | urllib.request |
|------|----------|----------------|
| 发起 GET/POST | `requests.get(url, timeout=2)` | `urllib.request.urlopen(Request(url))` |
| JSON 编解码 | `r.json()` / `json=` 参数 | 手写 `json.loads` + header 设置 |
| 超时 | `timeout=2`（连接 + 读取统一） | `socket.setdefaulttimeout()` 或 `urlopen(timeout=2)` |
| 状态码异常 | `raise_for_status()` | 手写 `if code >= 400: raise` |
| 异常类型 | `requests.exceptions.*` 家族 | `URLError`/`HTTPError` |

要点：

- **requests 的异常家族**：`ConnectionError`（连不上）、`Timeout`（超时，`ConnectTimeout`/`ReadTimeout` 子类）、`HTTPError`（4xx/5xx）——统一继承 `RequestException`，`except requests.exceptions.RequestException` 一把兜住，再按子类分诊。
- **`timeout` 一定要给**：不给超时，目标服务挂起时脚本跟着挂死——「自动化脚本也要有错误处理」的第一个落点。`timeout=(connect, read)` 可分开设。
- **离线测试的姿势**：真实接口不可依赖（会变、会挂），示例 4 在进程内用 `http.server` 起一个临时 API（随机端口），requests 打它——**测试目标可控，脚本才能可复现**（ph13 测试与工程质量阶段的 mock 思想在这里先打了个样）。
- **爬虫的起点**：roadmap 学习内容里的「爬虫」在本阶段只取其起点——`requests.get` 拉页面/接口 + 正则或解析提取，就是最简单的抓取；**反爬对抗、并发抓取、爬虫框架属 ph18/ph14 阶段的内容**，这里不展开。

### 3.5 报表生成（csv 标准库 + Excel）

**报表生成**是自动化的「交付物」环节：数据算完了，要落成人类能看的表。两种载体：**CSV**（标准库 `csv`，通用、可被 Excel 打开）与 **xlsx**（openpyxl，带样式，见 3.2）。本阶段 CSV 用标准库就够——roadmap 学习内容里的「报表生成」对应 csv + Excel 两条路。

```python
# 关键片段：examples/ex03-log-analyzer.py —— 统计结果写 CSV（完整版见示例 3，本机已验证）
import csv
with out.open("w", newline="", encoding="utf-8") as f:   # newline="" 防 Windows 空行
    writer = csv.writer(f)
    writer.writerow(["统计项", "取值", "数量"])            # 表头
    for code, n in sorted(status.items()):
        writer.writerow(["状态码", code, n])
    for ip, n in ips.most_common(3):
        writer.writerow(["Top IP", ip, n])
```

要点：

- **`newline=""` 是 csv 的固定搭配**：不写的话 Windows 上每行会多一个空行（Excel 兼容的代价）。
- **`DictReader`/`DictWriter`** 用列名读写字典行，适合「字段多、顺序乱」的数据；`writer.writerows(...)` 批量写。
- **CSV 与 pandas 的取舍**：CSV 就是纯文本表格，几 MB 以内用标准库 `csv` 零依赖搞定；上 GB、要透视/清洗才上 pandas（ph09 数据分析阶段）——「报表」优先 csv/Excel，别为了一个小表引入 numpy（ph08 的依赖成本必会概念）。
- **报表要可审计**：表头齐全、来源与生成时间标注（见 project 的 summary.txt）、数字在脚本里**重新打开核对**（示例 2 的 `load_workbook` 复读）——「输出结果要可审计」的落点。

### 3.6 邮件发送（smtplib + 本地调试服务器）

**邮件通知**让脚本「干完活自己汇报」：`smtplib.SMTP` 连接服务器、`EmailMessage` 组装邮件（From/To/Subject/正文/附件）、`send_message` 发送。smtplib 是标准库，纯文本协议（原理见 4.4）。

```python
# 关键片段：examples/ex05-mail-notify.py —— 发带附件邮件（完整版见示例 5，本机已验证）
from email.message import EmailMessage
import smtplib

msg = EmailMessage()
msg["From"] = "ops@example.com"
msg["To"] = "admin@example.com"
msg["Subject"] = "车辆状态日报"
msg.set_content("今日车辆状态汇总见附件，请查收。")
msg.add_attachment(report.read_bytes(), maintype="text",
                   subtype="csv", filename=report.name)   # CSV 附件
with smtplib.SMTP("127.0.0.1", port, timeout=5) as smtp:  # with 结束自动 quit()
    smtp.send_message(msg)                                # 一次发整封（含头与附件）
```

要点：

- **`EmailMessage`（email.message 新 API）优先**：`set_content` 管正文、`add_attachment` 管附件、`[]` 下标赋值头字段，比老 `MIMEText`/`MIMEMultipart` 手工拼简单得多；`EmailMessage` 会自动生成 `Content-Type` 边界与编码。
- **本地调试服务器**：`python -m smtpd` 在 Python 3.12 已移除，示例 5 用 `socketserver` 手写一个「只收不发」的最小 SMTP 服务器（约 30 行），把收到的邮件原样存进内存——**发邮件再也不需要真实邮箱**，同时把 SMTP 协议看透（4.4）。
- **真实发送的注意点**：`SMTP(host)` 后通常要 `starttls()`（加密）+ `login(user, password)`（认证），再 `send_message`——示例连本地调试服务器所以省略；生产用「应用专用密码」，别在脚本里硬编码明文口令（`getpass` 或环境变量）。
- **坑（附件文件名中文）**：`add_attachment(filename=...)` 对非 ASCII 文件名会做 RFC 2231 编码，`smtplib` 发送需确保头字段合规——示例用 ASCII 文件名规避。

### 3.7 定时任务（schedule）

**定时任务**让脚本「到点自己跑」：`schedule.every().day.at("08:00")` 注册任务，主循环 `run_pending()` 检查到期、`sleep` 到下一个时刻。schedule 是进程内调度（原理见 4.5），API 三件套——**注册 → 轮询 → 清空**。

```python
# 关键片段：examples/ex06-schedule-jobs.py —— 调度循环（完整版见示例 6，本机已验证）
import schedule, time

executed = []
schedule.every(1).seconds.do(heartbeat, executed)            # 每 1 秒（演示用）
daily = schedule.every().day.at("08:00").do(job, "生成日报")   # 每天 08:00
rounds = 0
while len(executed) < 3 and rounds < 10:  # 演示用有界循环；真实脚本是永不退出的 while True
    schedule.run_pending()                # 检查并执行到期任务
    time.sleep(0.5)                       # 频繁小睡 + 频繁检查，别空转烧 CPU
    rounds += 1
schedule.clear()                          # 主循环退出后清空所有任务
```

| schedule 写法 | 含义 |
|------|------|
| `every().day.at("08:00")` | 每天 08:00（已过则明天） |
| `every().hour` / `.minute` / `.seconds` | 每小时/每分/每秒 |
| `every(5).minutes` | 每 5 分钟 |
| `every().monday.at("09:30")` | 每周一 09:30 |
| `job.tag("a")` / `schedule.clear("a")` | 分组管理（批量暂停一类任务） |

要点：

- **schedule 不是常驻服务**：它不 fork 不守护，你的脚本就是调度器——主循环不能退出；部署到服务器长期跑、开机自启属 ph16 部署与 DevOps 阶段（systemd/cron 换一种方式做同一件事）。
- **坑（任务在循环外 sleep）**：`time.sleep(60)` 后再 `run_pending()` 会让分钟级任务漂移；正确姿势是**频繁小睡 + 频繁 run_pending**（示例 6 的 0.5s 轮询），或 `schedule.idle_seconds()` 睡到精确的下一个到期时刻。
- **依赖标注**：schedule 在本机全局 Python **未安装**，示例 6 在临时 venv（一次性验证产物，读者可自行创建：`python3 -m venv /tmp/ph12-venv && /tmp/ph12-venv/bin/pip install schedule==1.2.2`）中装 schedule 1.2.2 实测通过——直接使用需 `pip install schedule`；练习 3 用「轮询 + sleep」演示了同一思想，不装也能跑。

### 3.8 远程操作（paramiko / fabric）——概念层

**远程操作**是运维自动化的重头：批量在几十台机器上执行命令、拉取/推送文件。底层是 **SSH 协议**，Python 侧两层：**paramiko**（协议层——`SSHClient` 连接、`exec_command` 执行、`SFTPClient` 传文件）与 **fabric**（封装层——`Connection.run()` 一句话跑远程命令、`put`/`get` 传文件，内部就是 paramiko + invoke）。

```python
# 概念代码：paramiko/fabric 未在本环境做真实连接验证（本机无 SSH 服务器）
# 依赖：pip install paramiko fabric（本环境已装进临时 venv，仅验证 import 与 API 表面）
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 首次连接信任主机
client.connect("10.0.0.8", username="ops", password="***")    # 生产用密钥认证
stdin, stdout, stderr = client.exec_command("df -h")          # 远程执行
print(stdout.read().decode())

from fabric import Connection
with Connection("ops@10.0.0.8") as c:
    c.run("df -h")                                            # 一句话远程命令
    c.put("report.csv", "/tmp/report.csv")                    # 上传文件
```

要点：

- **paramiko 是「能干的库」，fabric 是「好用的壳」**：需要精细控制（隧道、代理、端口转发）用 paramiko；日常「跑命令、传文件」用 fabric 三行搞定。
- **认证优先密钥，不要密码**：`connect(pkey=...)` 加载 `~/.ssh/id_ed25519`；密码走 `keyboard-interactive` 也支持，但明文密码进脚本是安全事故。
- **`exec_command` 是「命令返回流」不是「等结果」**：`stdout.read()` 前要用 `channel.recv_exit_status()` 或先读流，否则大输出会死锁（fabric 的 `run` 已处理）。
- **验证状态**：paramiko 5.0.0 / fabric 3.2.3 已装进临时 venv 验证 import 与 API 表面；**本机无 SSH 服务器可连，未做真实连接验证**——上述片段标注「未在本环境验证」，装好 SSH 服务端后即可实测。

### 3.9 脚本工程化四要素（roadmap 必会概念）

四个必会概念不是「语法」而是「习惯」，本阶段全部示例与练习都在践行，这里集中给判据：

| 必会概念 | 判据（怎么算做到了） | 落地示例 |
|---------|---------------------|---------|
| 日志 + 错误处理 | `logging` 而非 `print` 满天飞；异常按类型捕获而非裸 `except`；失败不静默 | ex01 审计日志、ex03 无效行计数、ex04 异常家族、project 的 `--log-file` |
| 重复任务应参数化 | 输入输出路径、过滤条件、日志级别都是命令行参数（argparse），不写死在代码里 | project 的 `--input/--output-dir/--filter-id/--log-level` |
| 脚本要能安全重跑 | 同一输入跑两遍结果一致（幂等）；目标已存在不覆盖、不重复；临时产物不污染工作区 | ex01 第二次运行全跳过、ex06 `schedule.clear()`、project 报表确定性覆盖写 |
| 输出结果要可审计 | 报表带时间戳与来源；日志逐动作留痕；数字可被重新打开核对 | ex02 `load_workbook` 复读、project `summary.txt` + 审计日志 |

argparse 与 logging 是两件标准库工具，值得单独认一认（ph06 标准库阶段只点到，这里到「工程级」）：

```python
# project/can_log_tool.py 的 CLI（argparse）与日志（logging）骨架
import argparse, logging, sys

parser = argparse.ArgumentParser(description="CAN 日志批处理工具")
parser.add_argument("--input", help="CAN 日志文件路径")           # 必填（--demo 除外）
parser.add_argument("--output-dir", default=".", help="报表输出目录")
parser.add_argument("--filter-id", help="只统计指定 ID（如 0x123）")
parser.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
parser.add_argument("--log-file", help="审计日志文件路径（可选）")
args = parser.parse_args()                                        # 自动生成 --help

handlers = [logging.StreamHandler(sys.stderr)]                    # 默认 stderr
if args.log_file:
    handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
logging.basicConfig(level=args.log_level.upper(),
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=handlers)
```

要点：

- **argparse 三件事**：`add_argument` 声明参数（`default` 给默认值、`choices` 限取值）、`parse_args` 解析（自动处理 `--help`/非法输入）、`parser.error` 报必填缺失（退出码 2）——手写 `sys.argv` 解析是重复造轮子。
- **logging 三级用法**：`basicConfig` 一键配置（级别 + 格式 + 输出流）、`logger.info/error` 打点、多 Handler 分流（stderr + 文件双写，见 project）——日志是「可审计」的第一载体。
- **「能安全重跑」= 确定性**：同样的输入永远产出同样的报表（时间戳这类运行时信息只进 summary 不进 CSV），重复执行只是覆盖写、不留垃圾文件——project 测试里专门有一条幂等用例。

### 3.10 CAN 日志解析（格式规约解析样本）

**CAN 日志**是设备总线数据的第一手来源：控制器局域网（CAN 总线）上的报文被 `candump` 工具导出为文本，一行一帧。roadmap 练习 4 与 project 都是围绕它——解析格式、按 ID 统计、出报表，正好把 3.1/3.3/3.5 的批处理 + 正则 + 报表三件套合体。

```python
# 关键片段：project/can_log_tool.py —— candump 格式解析（完整版见 project，本机已验证）
FRAME_RE = re.compile(r"^\((\d+\.\d+)\) (\S+) ([0-9A-Fa-f]+)#([0-9A-Fa-f]*)$")
m = FRAME_RE.match(line.strip())
can_id = int(m.group(3), 16)                    # ID 十六进制转 int
data = bytes.fromhex(m.group(4))                # 负载 HEX 字符串转字节
# 按 ID 分组统计首字节 min/max/avg（简化约定：首字节即信号值）
```

要点：

- **candump 格式一行 = 时间戳 + 接口 + ID + 负载**：`(1629946800.123456) can0 123#1E00000000000000`——时间戳是「秒.微秒」浮点，ID 是十六进制（candump 输出不带 0x 前缀，如 `123`；`--filter-id` 参数才支持 `0x123` 写法），负载是 HEX 字符串（2 字符 = 1 字节）。
- **信号值的简化约定**：本阶段「负载首字节即信号值」（车速 30 → 0x1E）；真实场景信号跨字节、有缩放因子与字节序，需要 DBC 文件描述——**带格式规约的深度日志解析属 [ph18 数据平台分析 / 自动化方向阶段](../ph18-data-platform-automation/18-data-platform-automation.md)（roadmap 第 18 节，目录已建）**，这里用简化约定把「解析 → 统计 → 报表」链路打通。
- **无效行容错是必须的**：抓包日志里夹杂乱行、空行、注释行，解析器要计数跳过而不是崩溃（project 的 `invalid` 计数 + 测试用例）。

## 4. 底层原理

### 4.1 正则引擎：NFA 与回溯（为什么正则慢、为什么会卡死）

`re` 模块用的是 **NFA（非确定有限自动机）+ 回溯（Backtracking）** 引擎：正则被编译成状态机，匹配时从起始状态逐字符推进，遇到多分支（`|`、`*`、`?`）先试一条路，失败就**回溯**换另一条路。多数正则很快，因为引擎按「最左优先」尝试且大部分分支一次命中；但遇到**嵌套量词**（如 `(a+)+$`）时，失败匹配会指数级尝试所有组合——**灾难性回溯（Catastrophic Backtracking）**，几行日志就能把 CPU 打满（这是「日志正则导致服务变慢」的经典事故）。防护三招：① 用**锚定**（`^...$`）让引擎知道边界；② 避免嵌套量词与模糊匹配（`(a+)+`、`(.*)*` 是危险信号）；③ 解析结构化文本（JSON/XML）用专门解析器，不硬写正则。

### 4.2 .xlsx 的本质：一个 ZIP 压缩的 XML 目录

`.xlsx` 不是二进制表格格式，而是 **ZIP 压缩包内一组 XML 文件**：`xl/workbook.xml`（工作表清单）、`xl/worksheets/sheet1.xml`（单元格数据与样式引用）、`xl/styles.xml`（样式定义）。openpyxl 的读写本质是「解析/生成这套 XML + 打包/解包 ZIP」——所以**格式比 CSV 重得多**（示例 2 的 11 行小表也要 5.6 KB），也是为什么「纯数据用 CSV、要样式才用 xlsx」。验证姿势：`unzip -l report.xlsx` 看内部结构，`unzip -p report.xlsx xl/worksheets/sheet1.xml` 看单元格 `<c r="D2"><v>120.5</v></c>` 的存储形态——理解了这一层，Excel 文件损坏、公式不重算、样式丢失这类问题就有了排查方向。

### 4.3 HTTP 请求的生命周期（requests 背后发生了什么）

`requests.get(url)` 一行背后是完整的分层之旅：**DNS 解析域名 → TCP 三次握手 → （HTTPS）TLS 握手 → 发送请求报文（请求行 + 头 + 体）→ 读取响应报文（状态行 + 头 + 体）→ 关闭/复用连接**。状态码的语义分层由此而来：`2xx` 成功、`3xx` 重定向、`4xx` 客户端错（404 找不到、429 限流）、`5xx` 服务端错（500 内部、503 过载）。`timeout` 参数因此有**两个独立计时器**：连接超时（TCP/TLS 握手）与读取超时（发完请求等响应体）——`timeout=(3.05, 10)` 分开设置是生产惯例。requests 的异常家族就是这条链路的故障映射：连不上 → `ConnectionError`，超时 → `Timeout`，4xx/5xx → `HTTPError`（示例 4 实测 404 路径、练习 3 实测 500 路径）。

### 4.4 SMTP：一个文本命令协议（示例 5 的最小服务器就是协议本身）

SMTP 是**命令-响应的文本协议**：客户端发 ASCII 命令，服务器回三字状态码 + 文本。一次会话的状态机：`220` 欢迎 → `EHLO` 打招呼（`250` 应答，可附扩展能力）→ `MAIL FROM:`（`250`）→ `RCPT TO:`（`250`）→ `DATA`（`354` 允许正文）→ 正文以单独一行 `.` 结束 → `250` 入队 → `QUIT`（`221`）。示例 5 的「最小 SMTP 调试服务器」就是把这张状态机翻译成 socketserver 的 30 行代码——看懂它，就懂了 smtplib 每次 `send_message` 在线上发生了什么，也懂了为什么「邮件没到」要按 `250` 应答逐段排查。

### 4.5 schedule 的调度循环（进程内轮询 vs 系统级 cron）

schedule 没有自己的守护进程，它维护一个**按下次运行时间排序的任务队列**：`every().day.at("08:00")` 计算出 `next_run` 存入任务，主循环每次 `run_pending()` 扫描「到期任务」执行并重算下一次，`idle_seconds()` 返回「距最近到期还有多久」供 `sleep` 精确等待——这就是 3.7 说的「频繁小睡 + 频繁检查」。对比 **cron**（Unix 系统级调度器）：cron 是守护进程、按分/时/日/月语法触发外部命令、脚本退出后无状态；schedule 是进程内、能用 Python 对象与异常处理、但**进程死了任务就没了**。取舍：要开机自启、系统级容错用 cron/systemd（ph16 部署与 DevOps 阶段）；要「跟脚本一体、逻辑可测」用 schedule。

### 4.6 SSH 传输层（paramiko 在做什么）

SSH（Secure Shell）是**加密的远程登录协议**，paramiko 是它的 Python 原生实现（2003 年由 Robey Pointer 创建，纯 Python，无系统依赖）。连接建立分三步：**版本协商**（双方交换 SSH 版本串）→ **密钥交换（KEX）**（Diffie-Hellman 类算法协商会话密钥，双方各自推导共享密钥，防中间人）→ **认证**（客户端用口令或公钥证明身份，`~/.ssh/authorized_keys` 校验）。之后每条命令/每个文件传输都在**加密通道（Channel）**内进行——`exec_command` 开一个 channel 跑远程命令、SFTP 在通道上做文件读写。fabric 的 `Connection.run()` 就是「SSHClient 连接 + exec_command + 流处理」的高层封装——知道传输层有三步，才理解为什么要 `set_missing_host_key_policy`（首次连接的主机密钥信任）、为什么推荐密钥认证、为什么大输出要防死锁（3.8）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 日常文件整理（下载目录/日志归档/批量改名） | pathlib + shutil + 幂等模式（ex01、练习 1） |
| 报表自动化（周报/月报、车辆状态汇总） | openpyxl + csv + 重开核对（ex02、练习 2） |
| 日志监控与统计（错误率、Top IP、繁忙时段） | 正则 + Counter + CSV（ex03） |
| 接口冒烟/巡检（健康检查、定时拉数据） | requests + 超时 + 重试 + 错误日志（ex04、练习 3） |
| 结果通知（报表发邮件、告警通知） | smtplib + EmailMessage + 附件（ex05） |
| 定时任务（到点跑报表/抓数/巡检） | schedule + 调度循环（ex06） |
| 远程运维（批量执行命令、拉取采集文件） | paramiko/fabric（概念层，3.8） |
| 总线日志处理（CAN 日志统计） | 正则解析 + 按 ID 统计 + 报表（练习 4、project） |

**不适合此阶段的事项**：

- 高并发/大规模抓取（asyncio、aiohttp、分布式爬虫）：[ph14 并发、并行与异步阶段](../ph14-concurrency-async/14-concurrency-async.md)（roadmap 第 14 节）
- 测试工程体系（pytest/fixture/mock/覆盖率、CI 流水线）：ph13 测试与工程质量阶段
- 数据深度分析（pandas 透视表、时间序列、可视化）：ph09 数据分析阶段
- 生产部署与长期驻留（Docker、systemd/cron 化、监控告警）：[ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节）
- 完整 DBC 信号解析、反爬对抗、规模化采集平台：ph18 数据平台分析 / 自动化方向阶段（roadmap 第 18 节）

**与其他语言同类机制的对比**（一句话级，为 analysis/ 与 Tenet 合成积累素材）：Shell 管道做「一行流式文本处理」依然最快，但跨平台、复杂分支与测试是短板；Python 以「标准库齐全 + 可读 + 可测」成为复杂自动化主力；Go 单二进制部署适合「要分发的运维工具」（无解释器依赖），Node.js 在「前端周边的脚本」场景占优——自动化脚本选型本质是「开发效率 vs 部署形态 vs 生态」的权衡。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条运行。全部示例**离线可跑**：样本文件、报表（`.xlsx`/`.csv`）、审计日志一律写到**系统临时目录**（`tempfile.mkdtemp`），ex04 的 HTTP 服务与 ex05 的 SMTP 调试服务器都在进程内线程起停、结束 `shutdown()` 干净关闭——运行后用 `git status` 可确认工作区干净。依赖状态：openpyxl 3.1.5、requests 2.32.5 已装并实测；schedule 1.2.2 装于临时 venv 实测（ex06）；paramiko/fabric 仅 venv 验证 import（3.8）。

### 示例 1：文件批处理（pathlib 批量归档，对应 roadmap 示例）

呼应 3.1：把 `app-YYYYMMDD.log` 按月份归档到 `archive/YYYY-MM/`，目标已存在则跳过（幂等），每个动作写审计日志。完整文件 `examples/ex01-batch-files.py`。

```python
# examples/ex01-batch-files.py —— pathlib 批量归档（离线可跑，已验证）
for p in sorted(src.iterdir()):
    m = DATE_RE.search(p.name)
    target = dest_root / f"{m.group(1)}-{m.group(2)}" / p.name
    if target.exists():
        continue                       # 幂等：已存在 → 跳过
    shutil.move(str(p), str(target))
```

实测输出：样本 4 个文件（3 日志 + 1 txt）；第一次运行移动 `3`、非日志跳过 `1`；第二次运行（同样文件重现）移动 `0`、已存在跳过 `3`——**安全重跑不重复**；归档到 `archive/2026-09/` 与 `archive/2026-10/`；审计日志 `8` 行（每个动作一条）。

### 示例 2：Excel 自动化（openpyxl 车辆状态周报）

呼应 3.2/3.5：表头样式 + 数据行 + 合计行 + 冻结窗格，存盘后用 `load_workbook` 重新打开核对。完整文件 `examples/ex02-excel-report.py`。

```python
# examples/ex02-excel-report.py —— openpyxl 报表（离线可跑，已验证）
ws.append(HEADERS)
for r in rows:
    ws.append(r)
total_row = ws.max_row + 1
ws.cell(total_row, 4, round(sum(r[3] for r in rows), 1))
ws.freeze_panes = "A2"
wb.save(out)
```

实测输出：工作表「车辆状态周报」`11 行 × 6 列`（表头 + 9 数据 + 合计）；合计行 里程 `908.5`、能耗 `138.6`、平均速度 `49.82`；重开核对单元格 `B2 = EV-001`、冻结窗格 `A2`；文件约 `5.6 KB`（.xlsx 是 ZIP + XML，见 4.2）。

### 示例 3：日志分析（正则 + Counter → CSV 报表）

呼应 3.3/3.5：正则命名分组逐行解析访问日志，Counter 统计状态码/小时/IP，结果写 CSV 报表。完整文件 `examples/ex03-log-analyzer.py`。

```python
# examples/ex03-log-analyzer.py —— 访问日志统计（离线可跑，已验证）
m = LINE_RE.match(line)
if m is None:
    invalid += 1                        # 无效行计数，不崩溃
    continue
records.append(m.groupdict())
status = Counter(r["status"] for r in records)
```

实测输出：总行数 `12`（有效 `11`、无效 `1`）；状态码 `{200: 7, 201: 2, 404: 1, 500: 1}`；最繁忙时段 `10 时（4 条）`；Top IP `192.168.1.10（4 条）`；CSV 报表 `13 行`（含表头，3 张统计表）。

### 示例 4：接口测试（requests 打本地临时服务）

呼应 3.4/4.3：进程内起临时 HTTP API（随机端口），requests 实测 GET/POST/404/超时四类路径。完整文件 `examples/ex04-api-test.py`。

```python
# examples/ex04-api-test.py —— 接口测试（离线可跑，已验证）
r = requests.get(f"{base}/health", timeout=2)
print(r.status_code, r.json())          # 200 {'status': 'ok'}
try:
    r = requests.get(f"{base}/nope", timeout=2)
    r.raise_for_status()
except requests.exceptions.HTTPError as e:
    print(type(e).__name__)             # HTTPError（404）
```

实测输出：`GET /health` → `200 {'status': 'ok'}` + `Content-Type: application/json`；`POST /vehicles` → `201 {'created': 'EV-004'}`；`GET /nope` → `404` 且 `raise_for_status` 抛 `HTTPError`；`GET /slow`（服务端睡 1.5s）→ `timeout=0.3` 抛 `ReadTimeout`；结束打印「临时 HTTP 服务已关闭」。

### 示例 5：邮件通知（smtplib + 最小 SMTP 调试服务器）

呼应 3.6/4.4：socketserver 手写「只收不发」的 SMTP 调试服务器（`smtpd` 自 3.12 移除），EmailMessage 组装带 CSV 附件的日报并发送，服务器把邮件原样存进内存。完整文件 `examples/ex05-mail-notify.py`。

```python
# examples/ex05-mail-notify.py —— 邮件 + 本地调试服务器（离线可跑，已验证）
msg = EmailMessage()
msg["From"] = "ops@example.com"
msg["To"] = "admin@example.com"
msg["Subject"] = "车辆状态日报"
msg.add_attachment(report.read_bytes(), maintype="text",
                   subtype="csv", filename=report.name)
with smtplib.SMTP("127.0.0.1", port, timeout=5) as smtp:
    smtp.send_message(msg)
```

实测输出：SMTP 调试服务器收信 `1` 封；From `ops@example.com`、收件人 `admin@example.com`、主题「车辆状态日报」；附件 `1` 个（`vehicle-report.csv`）；结束打印「SMTP 调试服务器已关闭」。

### 示例 6：定时任务（schedule 调度循环）

呼应 3.7/4.5：注册每秒心跳任务 + 每日 08:00 任务，主循环 `run_pending()` 轮询，心跳触发 3 次后结束。完整文件 `examples/ex06-schedule-jobs.py`。

```python
# examples/ex06-schedule-jobs.py —— schedule 调度循环（schedule 1.2.2，venv 实测）
schedule.every(1).seconds.do(heartbeat, executed)
daily = schedule.every().day.at("08:00").do(job, "生成日报")
while len(executed) < 3 and rounds < 10:
    schedule.run_pending()
    time.sleep(0.5)
```

实测输出：注册任务 `2` 个；日报任务下次运行取决于运行时刻（本机实测为运行日的次日 08:00）；心跳任务每秒触发、实测 `3` 次后循环结束；`schedule.clear()` 后注册数 `0`。**验证环境备注**：schedule 未安装于本机全局 Python，本示例在临时 venv（一次性验证产物，读者可自行创建：`python3 -m venv /tmp/ph12-venv && /tmp/ph12-venv/bin/pip install schedule==1.2.2`）中实测通过；直接使用需 `pip install schedule`。

## 7. 总结

### 关键要点

1. **自动化脚本也要有日志和错误处理**（必会概念）：`logging` 逐动作留痕、异常按类型捕获、失败不静默——`print` 调试只属于一次性脚本
2. **重复任务应参数化**（必会概念）：路径、过滤条件、日志级别都是 argparse 参数，脚本是「可复用工具」而不是「写死的一次性代码」
3. **脚本要能安全重跑**（必会概念）：幂等 = 同一输入跑两遍结果一致（目标已存在 → 跳过），临时产物不污染工作区（示例 1 第二次运行移动 0 个）
4. **输出结果要可审计**（必会概念）：报表带时间戳与来源、日志逐动作留痕、数字可重开核对（示例 2 的 `load_workbook` 复读、project 的 summary.txt + 审计日志）
5. **pathlib 是文件批处理的正确姿势**：路径是对象不是字符串，`iterdir`/`glob`/`rglob`/`mkdir(exist_ok=True)` 跨平台；`shutil.move` 管跨目录移动
6. **正则三板斧**：`re.compile` 复用、命名分组 + `groupdict`、`match` 锚定整行；嵌套量词会灾难性回溯（4.1）
7. **requests 三件套**：`timeout` 必须给、`raise_for_status()` 抛 HTTPError、`requests.exceptions.RequestException` 一把兜住异常家族
8. **CSV 与 xlsx 各司其职**：纯数据用标准库 `csv`（`newline=""` 别忘了），要样式才用 openpyxl（.xlsx 本质是 ZIP + XML，4.2）
9. **smtplib + EmailMessage 是发邮件的现代写法**：`set_content`/`add_attachment` 组装、with 块自动 quit；本地调试用 socketserver 手写 sink（`smtpd` 已移除）
10. **schedule 是进程内轮询**：注册 → `run_pending()` 频繁检查 → 主循环不能退；系统级长期调度交给 cron/systemd（ph16）
11. **工程习惯 = 复用工具与一次性脚本的分水岭**：示例与练习里每一项（审计日志、无效行计数、幂等跳过、重开核对）都是四要素的落地

### 阶段验收清单

- [ ] 能把脚本写成可复用工具：argparse 参数化 + 路径/条件可配置（对应 roadmap「能把脚本写成可复用工具」）
- [ ] 能处理异常和日志：requests 异常家族、无效行容错、logging 留痕（对应 roadmap「能处理异常和日志」）
- [ ] 能参数化运行：`--input/--output-dir/--filter-id/--log-level` 全部命令行可配（对应 roadmap「能参数化运行」）
- [ ] 能说清四个必会概念并各举一个落地例子（3.9 的判据表）
- [ ] 能独立跑通 6 个示例并解释每个的实测数字（第 6 章）
- [ ] 能对照实测数字说明工程性收益：ex01 重跑移动 0、ex04 超时抛 ReadTimeout、ex05 收信 1 封带附件、ex06 心跳 3 次后循环结束

### 跨语言对比：自动化脚本

| 维度 | Python | Shell | Go | Node.js |
|------|--------|-------|----|---------|
| 文本处理 | 标准库齐全（re/csv/json） | 管道 + awk/sed 最快 | 标准库较弱，第三方多 | 生态丰富 |
| 跨平台 | ✅（解释器 + 路径对象） | ❌（bash 系为主） | ✅（单二进制） | ✅ |
| 复杂分支/可测试 | ✅ 可读可测 | ❌ 难测 | ✅ 强类型 | ✅ |
| 部署形态 | 需解释器环境 | 系统自带 | 单二进制分发 | 需 Node 运行时 |
| 生态定位 | 自动化/数据/AI 全能 | 系统管理快捷指令 | 运维分发工具 | 前端周边脚本 |

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。与 roadmap「练习」小节一一对应，完成 4 题后继续：

- 批量整理日志（★）：pathlib 归档旧日志 + 清理临时文件，幂等 + 审计日志（提示：正则从文件名取日期；动作前检查目标已存在）
- 生成 Excel 报表（★★）：CSV → 多 Sheet xlsx，汇总 sheet 按车辆分组（提示：`round(..., 2)`；`load_workbook` 重开核对）
- 定时拉取接口（★★）：轮询循环拉本地接口，超时 + 重试 + 错误日志（提示：`raise_for_status()`；重试 1 次失败记 `errors.log`；`time.sleep(1)` 就是最小「定时」）
- 解析 CAN 日志（★★★）：candump 格式正则解析 + 按 ID 统计 + CSV 报表（提示：`int(id, 16)` + `bytes.fromhex`；首字节即信号值；无效行计数）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**CAN 日志批处理工具**——解析 candump 格式日志 → 按 ID 统计信号值 → 生成 CSV 报表 + 文本汇总，argparse 参数化、logging 审计、可安全重跑、输出可审计四个必会概念一个工具全部落地（对应 roadmap「推荐项目」第二个「CAN 日志批处理工具」；roadmap 的另一个「自动报表生成器」可作为扩展方向——把示例 2/5/6 合体成「定时生成 Excel 报表并发邮件」）。建议完成练习后再动手，尤其练习 4（同一主题的缩小版）。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[测试与工程质量阶段](../ph13-testing-quality/13-testing-quality.md) — pytest/fixture/mock、参数化测试与覆盖率、mypy 类型注解、ruff/black/pre-commit、CI/CD；自动化脚本写多了，下一步自然要回答「怎么证明脚本是对的、怎么防止改坏」——ph12 里随手写的自检断言与错误处理，正是 ph13 测试思维的原型；在此之前可先按推荐学习顺序巩固 ph11 数据库与缓存阶段与本阶段的练习与项目。
