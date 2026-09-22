# examples/ex02-scrape-page.py —— 主文档 6.2：网页抓取（requests + BeautifulSoup 提取数据）
# 验证环境：Python 3.13.9，requests 2.32.5，beautifulsoup4 4.13.5
# 运行：python3 ex02-scrape-page.py（需联网，已验证）
import requests
from bs4 import BeautifulSoup


def fetch_title_and_links(url: str) -> tuple[str, list[str]]:
    """抓一个页面，提取标题与去重后的全部链接。"""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding  # 中文页面防乱码
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = sorted({a.get("href") for a in soup.find_all("a") if a.get("href")})
    return title, links


if __name__ == "__main__":
    title, links = fetch_title_and_links("https://example.com")  # 需联网
    print("标题:", title)
    for link in links:
        print("链接:", link)
