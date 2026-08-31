# project/scraper.py —— 网页数据采集器：requests 抓取 + BeautifulSoup 解析 + CSV 输出
# 验证环境：Python 3.13.9，requests 2.32.5，beautifulsoup4 4.13.5（已验证）
# 运行：python3 scraper.py --demo                    # 离线演示（内置样例 HTML）
#       python3 scraper.py https://example.com -o out.csv   # 联网抓取
# 测试：pytest -q（离线）；lint：ruff check .
"""网页数据采集器：网络层（fetch）与解析层（parse_page，纯函数）分离。"""

import argparse
import csv
import logging
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper")

# --demo 模式使用的内置样例 HTML（离线演示 / 测试 fixture 同款结构）
SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>样例页面</title></head>
<body>
  <h1>车辆数据</h1>
  <a href="/about">关于</a>
  <a href="https://example.com/doc">文档</a>
  <a href="/about">关于（重复，应去重）</a>
  <table>
    <tr><th>vehicle_id</th><th>speed</th></tr>
    <tr><td>V001</td><td>80</td></tr>
    <tr><td>V002</td><td>63</td></tr>
  </table>
</body>
</html>
"""


def fetch(url: str, timeout: int = 10) -> str:
    """抓取 URL 返回 HTML 文本；失败时抛带 URL 的 RuntimeError。"""
    try:
        resp = requests.get(url, timeout=timeout)  # 显式超时，防挂起
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding  # 中文页面防乱码
        return resp.text
    except requests.Timeout as e:
        raise RuntimeError(f"请求超时: {url}") from e
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP 错误: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"网络错误: {e}") from e


def parse_page(html: str, base_url: str) -> dict:
    """纯函数：解析 HTML，提取标题、去重链接（绝对化）与首个表格的行数据。

    返回 {"url", "title", "links": [...], "table_rows": [[...], ...]}。
    不依赖网络，可直接用 HTML 字符串离线测试。
    """
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    links: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href]"):
        absolute = urljoin(base_url, a["href"].strip())  # 相对链接转绝对
        if absolute and absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    table_rows: list[list[str]] = []
    table = soup.find("table")
    if table is not None:
        for tr in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if cells:
                table_rows.append(cells)

    return {"url": base_url, "title": title, "links": links, "table_rows": table_rows}


def scrape_urls(urls: list[str], timeout: int = 10) -> list[dict]:
    """批量抓取并解析；单个 URL 失败记日志并继续，不中断整批。"""
    records: list[dict] = []
    for url in urls:
        logger.info("抓取 %s", url)
        try:
            html = fetch(url, timeout=timeout)
        except RuntimeError as e:
            logger.error("跳过 %s: %s", url, e)
            continue
        record = parse_page(html, url)
        logger.info(
            "  标题=%s 链接=%d 条 表格=%d 行",
            record["title"],
            len(record["links"]),
            len(record["table_rows"]),
        )
        records.append(record)
    return records


def save_csv(records: list[dict], path: str) -> None:
    """把采集结果写成 CSV：每个链接/表格行一行，小任务用标准库 csv 即可。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "title", "kind", "value"])
        for rec in records:
            for link in rec["links"]:
                writer.writerow([rec["url"], rec["title"], "link", link])
            for row in rec["table_rows"]:
                writer.writerow([rec["url"], rec["title"], "table_row", " | ".join(row)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="网页数据采集器：提取标题、链接、表格存 CSV")
    parser.add_argument("urls", nargs="*", help="要抓取的 URL 列表")
    parser.add_argument("-o", "--output", default="scraped.csv", help="输出 CSV 路径（默认 scraped.csv）")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="请求超时秒数（默认 10）")
    parser.add_argument("--demo", action="store_true", help="离线演示：解析内置样例 HTML，不联网")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.demo:
        records = [parse_page(SAMPLE_HTML, "https://demo.local/")]
    elif args.urls:
        records = scrape_urls(args.urls, timeout=args.timeout)
    else:
        parser.error("请提供 URL 列表，或用 --demo 离线演示")

    save_csv(records, args.output)
    logger.info("共采集 %d 个页面，已写入 %s", len(records), args.output)
    for rec in records:
        print(f"[{rec['title']}] {rec['url']}")
        for link in rec["links"]:
            print(f"  link: {link}")
        for row in rec["table_rows"]:
            print(f"  row:  {' | '.join(row)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
