# examples/ex01-fetch-json.py —— 主文档 6.1：requests 请求 API（超时 + 错误处理 + JSON 解析）
# 验证环境：Python 3.13.9，requests 2.32.5；运行：python3 ex01-fetch-json.py（需联网，已验证）
import requests


def fetch_json(url: str, timeout: int = 10) -> dict:
    """带超时、状态检查、JSON 解析与错误分类的请求封装。"""
    try:
        resp = requests.get(url, timeout=timeout)  # 显式超时，防挂起
        resp.raise_for_status()  # 4xx/5xx 抛 HTTPError
        return resp.json()
    except requests.Timeout as e:
        raise RuntimeError(f"请求超时: {url}") from e
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP 错误: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"网络错误: {e}") from e


if __name__ == "__main__":
    data = fetch_json("https://httpbin.org/json")  # 需联网
    print(data["slideshow"]["title"])
    print(data["slideshow"]["author"])
