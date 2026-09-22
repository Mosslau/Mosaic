# exercises/sol-01-fetch-api.py —— 练习 1 参考实现：请求 API（requests 封装）
# 验证环境：Python 3.13.9，requests 2.32.5；运行：python3 sol-01-fetch-api.py（需联网，已验证）
import requests


def fetch_json(url: str, timeout: int = 10) -> dict:
    """GET 一个 URL 并返回解析后的 JSON；失败时抛带 URL 的 RuntimeError。"""
    try:
        resp = requests.get(url, timeout=timeout)  # 显式超时
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout as e:
        raise RuntimeError(f"请求超时: {url}") from e
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP 错误: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"网络错误: {e}") from e


if __name__ == "__main__":
    data = fetch_json("https://httpbin.org/json")
    print("标题:", data["slideshow"]["title"])

    try:  # 404 必须抛出带 URL 的错误，而非静默失败
        fetch_json("https://httpbin.org/status/404")
    except RuntimeError as e:
        print("按预期捕获:", e)
