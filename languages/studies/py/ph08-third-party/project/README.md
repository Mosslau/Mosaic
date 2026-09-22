# ph08 阶段项目：网页数据采集器

> 对应 Roadmap（python.md）ph08「推荐项目」第二个「网页数据采集器」。给一组 URL，用 requests + BeautifulSoup 提取结构化字段（标题、链接、表格数据），清洗后存 CSV；提取函数有 pytest 覆盖，ruff 保持整洁。

## 需求

实现一个命令行网页数据采集器：输入一组 URL，逐个抓取页面，用 BeautifulSoup 提取标题、全部链接（转为绝对 URL）与首个表格的数据行，汇总清洗后写入 CSV。要求网络层与解析层分离——解析函数是纯函数（输入 HTML 字符串、输出结构化数据），可以离线测试；CLI 支持超时配置与失败容错（单个 URL 失败不中断整批）；附 `--demo` 模式，用内置样例 HTML 离线演示完整链路。

## 功能清单

- [x] 抓取：`fetch(url, timeout)` 显式超时 + `raise_for_status()` + 三类异常分类（超时 / HTTP / 网络）
- [x] 解析：`parse_page(html, base_url)` 纯函数——提取标题、去重链接（`urljoin` 转绝对地址）、首个表格的行数据
- [x] 汇总：`scrape_urls(urls, timeout)` 批量抓取，单 URL 失败记日志并继续，不中断整批
- [x] 输出：`save_csv(records, path)` 用标准库 `csv` 写出（小任务不引 pandas——体会依赖成本）
- [x] CLI：argparse 支持多个 URL、`-o` 输出路径、`-t` 超时、`--demo` 离线演示
- [x] 日志：`logging` 输出抓取进度与失败原因（承接 ph06 的日志能力）
- [x] 测试：`tests/test_scraper.py` 用内置 HTML fixture 离线覆盖解析与 CSV 写出（pytest fixture + 断言）
- [x] 质量：`pyproject.toml` 内置 ruff 配置，`ruff check . && pytest -q` 一键门禁

## 验收标准

- [ ] `python3 scraper.py --demo` 离线跑通：解析内置样例 HTML，打印提取结果并写出 CSV
- [ ] `python3 scraper.py https://example.com -o out.csv` 联网跑通：CSV 含标题、链接等字段
- [ ] 批量抓取时混入一个无效 URL，程序记日志继续跑完，退出码仍为 0
- [ ] `pytest -q` 全部通过（离线，不依赖网络）
- [ ] `ruff check .` 零告警
- [ ] 说清为什么解析层要设计成纯函数（可离线测试、与网络层解耦）

## 扩展方向（可选）

- 提取结果改用 pandas 写 Excel（openpyxl），对比"标准库 csv vs pandas"的依赖成本（主文档 3.5）
- 给抓取加并发：`httpx.AsyncClient` + `asyncio.gather` 把串行抓取改成并发（主文档 3.1/4.1，深入见 ph14 并发阶段）
- 页面是 JS 动态渲染时切换到 playwright（主文档 3.2 选型表）
- 把 CLI 挂进 pre-commit / CI：`ruff check . && pytest` 自动化（ph13 工程质量阶段）

## 验证环境

- Python 3.13.9；依赖：requests 2.32.5、beautifulsoup4 4.13.5、pytest 8.4.2、ruff 0.12.0
- 安装：`pip install requests beautifulsoup4 pytest ruff`（建议先在 venv 中安装，见 ph07）
- 运行 / 测试命令见「验收标准」各条
- 验证状态：已验证（`--demo` 离线链路、example.com 联网抓取、无效 URL 容错、pytest 5 个用例、ruff 零告警均在本环境实际执行通过）
