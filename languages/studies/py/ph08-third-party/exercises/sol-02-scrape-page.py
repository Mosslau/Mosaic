# exercises/sol-02-scrape-page.py —— 练习 2 参考实现：抓取网页存 CSV
# 验证环境：Python 3.13.9，requests 2.32.5，beautifulsoup4 4.13.5
# 运行：python3 sol-02-scrape-page.py（需联网，已验证）；产物 links.csv 写到当前目录
import csv

import requests
from bs4 import BeautifulSoup


def scrape_links(url: str) -> list[tuple[str, str]]:
    """抓取页面，返回去重排序后的 (链接文本, href) 列表。"""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding  # 中文页面防乱码
    soup = BeautifulSoup(resp.text, "html.parser")

    seen: dict[str, str] = {}
    for a in soup.select("a[href]"):  # CSS 选择器：带 href 的 a 标签
        href = a["href"].strip()
        if href and href not in seen:
            seen[href] = a.get_text(strip=True)
    return sorted((text, href) for href, text in seen.items())


def save_csv(rows: list[tuple[str, str]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["link_text", "href"])
        writer.writerows(rows)


if __name__ == "__main__":
    # 注意：JS 动态渲染的页面 requests 拿到的只是空壳 HTML，
    # 应换 playwright 等浏览器自动化方案（见主文档 3.2 选型表）。
    rows = scrape_links("https://example.com")
    save_csv(rows, "links.csv")
    print(f"提取 {len(rows)} 条链接，已写入 links.csv")
    for text, href in rows:
        print(f"  {text or '(无文本)'} -> {href}")
