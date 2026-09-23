#!/usr/bin/env python3
# exercises/sol-03-telemetry-fetcher.py —— 练习 3 参考实现：mock 外部接口（隔离网络依赖）
# 验证环境：Python 3.13.9 + pytest 8.4.2 + requests 2.32.5（本机已装并实测）
# 运行：python3 -m pytest sol-03-telemetry-fetcher.py -q（离线可跑，已验证 —— mock 后不发真实请求）
# 验证状态：已验证 —— 7 个用例全过；本文件语句覆盖率 100%（trace 实测：53 个可执行行全命中）
# 验证块数字实测：python3 -m pytest sol-03-telemetry-fetcher.py -q -> 7 passed
#                trace 覆盖率 -> lines 53, cov 100%
import pytest
import requests
from unittest.mock import MagicMock, patch


class TelemetryFetcher:
    """查设备速度的客户端：真实环境发 HTTP 请求，测试时用 mock 替换。"""

    def __init__(self, base_url: str = "https://api.example.com") -> None:
        self.base_url = base_url

    def fetch_speed(self, device_id: str) -> float:
        resp = requests.get(f"{self.base_url}/devices/{device_id}/speed", timeout=2)
        resp.raise_for_status()
        return float(resp.json()["speed"])

    def fetch_batch(self, ids: list[str]) -> dict[str, float]:
        return {vid: self.fetch_speed(vid) for vid in ids}


def fake_response(payload: dict | None = None, error: Exception | None = None):
    resp = MagicMock()
    resp.json.return_value = payload or {}
    if error is not None:
        resp.raise_for_status.side_effect = error
    return resp


# ---- 测试 ----
def test_fetch_speed_success():
    with patch("requests.get", return_value=fake_response(payload={"speed": 42.5})) as mock_get:
        speed = TelemetryFetcher().fetch_speed("EV-001")
    assert speed == 42.5
    mock_get.assert_called_once_with("https://api.example.com/devices/EV-001/speed", timeout=2)


def test_fetch_speed_http_error():
    err = requests.exceptions.HTTPError("404 Client Error")
    with patch("requests.get", return_value=fake_response(error=err)):
        with pytest.raises(requests.exceptions.HTTPError):
            TelemetryFetcher().fetch_speed("EV-002")


def test_fetch_speed_timeout():
    with patch("requests.get", side_effect=requests.exceptions.ConnectTimeout("timeout")):
        with pytest.raises(requests.exceptions.ConnectTimeout):
            TelemetryFetcher().fetch_speed("EV-003")


def test_fetch_batch_uses_fetch_speed():
    fetcher = TelemetryFetcher()
    # patch.object 替换「实例方法」：验证批量接口复用了单条接口逻辑，且不碰网络
    with patch.object(fetcher, "fetch_speed", side_effect=[10.0, 20.0]) as mock_fetch:
        result = fetcher.fetch_batch(["EV-004", "EV-005"])
    assert result == {"EV-004": 10.0, "EV-005": 20.0}
    assert mock_fetch.call_count == 2


def test_fetch_batch_empty():
    fetcher = TelemetryFetcher()
    with patch.object(fetcher, "fetch_speed") as mock_fetch:
        assert fetcher.fetch_batch([]) == {}
    mock_fetch.assert_not_called()


def test_fetch_speed_raises_on_missing_key():
    # 响应里没有 speed 字段：KeyError 让调用方第一时间发现接口契约不符
    with patch("requests.get", return_value=fake_response(payload={"name": "EV"})), \
            pytest.raises(KeyError):
        TelemetryFetcher().fetch_speed("EV-006")


def test_custom_base_url():
    with patch("requests.get", return_value=fake_response(payload={"speed": 1.0})) as mock_get:
        TelemetryFetcher("http://localhost:8000").fetch_speed("EV-007")
    mock_get.assert_called_once_with("http://localhost:8000/devices/EV-007/speed", timeout=2)


if __name__ == "__main__":
    pytest.main(["-q", __file__])
