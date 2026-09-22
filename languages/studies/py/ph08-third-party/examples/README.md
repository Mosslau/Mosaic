# examples —— 第三方库阶段完整示例

> 每个示例是主文档 `08-third-party.md` 第 6 章（及 3.1 节）对应示例的完整可运行版。验证环境：Python 3.13.9（macOS）；依赖：requests 2.32.5、httpx 0.28.1、beautifulsoup4 4.13.5、pandas 2.3.3、matplotlib 3.10.6、fastapi 0.139.1、pytest 8.4.2、ruff 0.12.0、mypy 1.17.1。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-fetch-json.py` | requests 请求 API：显式 timeout + `raise_for_status()` + JSON 解析 + 三类异常分类 | `python3 ex01-fetch-json.py`（需联网） |
| `ex02-scrape-page.py` | requests + BeautifulSoup 抓页面，提取标题与去重后的全部链接 | `python3 ex02-scrape-page.py`（需联网） |
| `ex03-csv-analysis.py` | 离线完整链路：造 CSV → pandas `read_csv` + `groupby` → matplotlib 折线 + 柱状图 `savefig` | `python3 ex03-csv-analysis.py`（离线，产物写到当前目录） |
| `ex04-fastapi-crud.py` | FastAPI + Pydantic：一个资源的 GET/POST/PUT/DELETE，`__main__` 用 TestClient 自测（含 422 校验演示） | `python3 ex04-fastapi-crud.py`（离线）；或 `uvicorn ex04-fastapi-crud:app --reload` 后开 `/docs` |
| `ex05-quality-tools/` | 质量工具三件套：`calc.py`（被测代码）+ `test_calc.py`（fixture + 参数化）+ `pyproject.toml`（ruff/mypy 配置） | 见下方说明 |
| `ex06-httpx-async.py` | httpx 同步 vs 异步：同一 API 双模式，实测 N 次请求 N×RTT 与 1×RTT 的差距 | `python3 ex06-httpx-async.py`（需联网） |

说明：

- `ex01`/`ex02`/`ex06` 需要联网（访问 httpbin.org / example.com）；`ex03`/`ex04`/`ex05` 离线可跑
- `ex03` 会在**当前工作目录**写出 `vehicle.csv` 与 `vehicle_analysis.png`，建议先 `cd` 到临时目录再运行
- `ex05-quality-tools/` 验证命令（在该目录下执行）：

  ```bash
  # 1. 跑测试（6 个用例全过）
  pytest -q
  # 2. lint 零告警
  ruff check .
  # 3. 类型检查通过
  mypy calc.py
  ```

验证状态：全部示例均已在本环境（Python 3.13.9）实际运行验证通过（已验证）：`ex01` 输出 httpbin JSON 的 title/author；`ex02` 输出 `Example Domain` 标题与 1 条链接；`ex03` 打印分组统计并生成 PNG；`ex04` TestClient 输出 201/422/200；`ex05` pytest 6 过、ruff 零告警、mypy 通过；`ex06` 实测同步 3 次约 1.6s、异步约 1.1s。
