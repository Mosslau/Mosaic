# examples —— 自动化脚本阶段完整示例

> 每个示例对应主文档 `12-automation.md` 相关小节（3.x / 4.x / 6 章）的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：openpyxl 3.1.5、requests 2.32.5（本机已装并实测）；schedule 1.2.2（本机全局未装，装于一次性临时 venv 后实测，读者可自行创建：`python3 -m venv /tmp/ph12-venv && /tmp/ph12-venv/bin/pip install schedule==1.2.2`）；paramiko / fabric 见主文档 3.8 概念小节。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-batch-files.py` | 文件批处理：pathlib 按日期批量归档日志文件，幂等 + 审计日志（主文档 3.1、roadmap 示例） | `python3 ex01-batch-files.py`（离线） |
| `ex02-excel-report.py` | Excel 自动化：openpyxl 生成设备状态周报（表头/数据/合计/样式/冻结窗格）+ 重开核对（主文档 3.2/3.5） | `python3 ex02-excel-report.py`（离线） |
| `ex03-log-analyzer.py` | 日志分析：正则逐行解析 + Counter 统计状态码/小时/IP + CSV 报表（主文档 3.3/3.5） | `python3 ex03-log-analyzer.py`（离线） |
| `ex04-api-test.py` | 接口测试：http.server 起临时 API + requests 实测 GET/POST/404/超时（主文档 3.4/4.3） | `python3 ex04-api-test.py`（离线） |
| `ex05-mail-notify.py` | 邮件通知：smtplib + 进程内最小 SMTP 调试服务器（socketserver 手写，`smtpd` 自 3.12 移除），CSV 附件（主文档 3.6/4.4） | `python3 ex05-mail-notify.py`（离线） |
| `ex06-schedule-jobs.py` | 定时任务：schedule 注册任务 + `run_pending()` 轮询循环（主文档 3.7/4.5） | `python3 ex06-schedule-jobs.py`（需 `pip install schedule`；本环境用 venv 解释器实测） |

说明：

- **产物纪律**：全部示例的样本文件、报表（`.xlsx`/`.csv`）、审计日志一律写到**系统临时目录**（`tempfile.mkdtemp`）；ex04 的 HTTP 服务、ex05 的 SMTP 调试服务器都在进程内线程起停，结束 `shutdown()` 干净关闭——运行后用 `git status` 可确认工作区干净。
- **依赖状态**：openpyxl 3.1.5、requests 2.32.5 在本环境已安装并实测；schedule 1.2.2 本机全局未装，已装进一次性临时 venv（读者可自行创建：`python3 -m venv /tmp/ph12-venv && /tmp/ph12-venv/bin/pip install schedule==1.2.2`）实测 ex06 通过——直接使用请 `pip install schedule`；paramiko 5.0.0 / fabric 3.2.3 已装进临时 venv 验证 import 与 API 表面，但**本机无 SSH 服务器可连，未做真实连接验证**（主文档 3.8 为概念讲解 + 标注）。
- 运行命令里 ex06 用 `/tmp/ph12-venv/bin/python ex06-schedule-jobs.py`（venv 为一次性验证产物，读者先按上文命令创建，或用自己装好 schedule 的解释器）。

验证状态：ex01~ex05 全部在本环境实际运行通过（已验证）；ex06 在临时 venv（schedule 1.2.2）中实际运行通过（已验证）。实测关键输出：

- `ex01`：样本 4 个文件（3 日志 + 1 txt）；第一次运行移动 `3`、非日志跳过 `1`；第二次运行（同样文件重现）移动 `0`、已存在跳过 `3`——安全重跑不重复；归档到 `archive/2026-09/` 与 `archive/2026-10/`；审计日志 `8` 行（每个动作一条）
- `ex02`：工作表「设备状态周报」`11 行 × 6 列`；表头 6 列；合计行 累计运行量 `908.5`、能耗 `138.6`、平均速度 `49.82`；冻结窗格 `A2`；xlsx 约 `5.6 KB`
- `ex03`：总行数 `12`（有效 `11`、无效 `1`）；状态码 `{200: 7, 201: 2, 404: 1, 500: 1}`；最繁忙时段 `10 时（4 条）`；Top IP `192.168.1.10（4 条）`；CSV 报表 `13 行`（含表头）
- `ex04`：`GET /health` → `200 {'status': 'ok'}`、`Content-Type: application/json`；`POST /devices` → `201 {'created': 'EV-004'}`；`GET /nope` → `404` 且 `raise_for_status` 抛 `HTTPError`；`GET /slow`（服务端睡 1.5s）→ `timeout=0.3` 抛 `ReadTimeout`；结束打印「临时 HTTP 服务已关闭」
- `ex05`：SMTP 调试服务器收信 `1` 封；From `ops@example.com`、收件人 `admin@example.com`、主题「设备状态日报」；附件 `1` 个（`device-report.csv`）；结束打印「SMTP 调试服务器已关闭」
- `ex06`：注册任务 `2` 个；日报任务下次运行取决于运行时刻（本机实测为运行日的次日 08:00）；心跳任务每秒触发、实测 `3` 次后循环结束；`schedule.clear()` 后注册数 `0`
