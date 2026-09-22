#!/usr/bin/env python3
# examples/ex03-mock.py —— mock 外部依赖：unittest.mock 隔离网络请求（主文档 3.3）
# 验证环境：Python 3.13.9 + pytest 8.4.2 + requests 2.32.5（本机已装并实测）
# 运行：python3 -m pytest ex03-mock.py -q（离线可跑，已验证 —— mock 后不会真的发网络请求）
# 验证状态：已验证 —— 6 个用例全过（成功 2 + 错误 2 + 超时 1 + 调用参数断言 1）
# 核心：测试里用 patch 替换 requests.get，被测代码根本碰不到真实网络——测试快、稳、可复现
import pytest
import requests
from unittest.mock import MagicMock, patch


# ---- 被测代码：查车辆实时速度（真实环境会发 HTTP 请求）----
def fetch_speed(vehicle_id: str, base_url: str = "https://api.example.com") -> float:
    resp = requests.get(f"{base_url}/vehicles/{vehicle_id}/speed", timeout=2)
    resp.raise_for_status()                 # 4xx/5xx 抛 HTTPError
    return float(resp.json()["speed"])


# ---- 测试工具：造一个「假响应」（MagicMock 自动模仿任何属性/方法调用）----
def fake_response(status: int = 200, payload: dict | None = None, error: Exception | None = None):
    resp = MagicMock()                      # MagicMock 的任意属性都是 Mock，调了不报错
    resp.status_code = status
    resp.json.return_value = payload or {}
    if error is not None:
        resp.raise_for_status.side_effect = error
    return resp


# 1) 成功路径：patch 成上下文管理器，返回假响应
def test_success_with_context_manager():
    with patch("requests.get", return_value=fake_response(payload={"speed": 42.5})) as mock_get:
        assert fetch_speed("EV-001") == 42.5
    # 顺带断言「被测代码确实按预期调用了接口」——参数与 timeout 都不能错
    mock_get.assert_called_once_with(
        "https://api.example.com/vehicles/EV-001/speed", timeout=2
    )


# 2) 装饰器形式：patch 把 mock 对象注入测试函数参数（与 with 等价）
@patch("requests.get")
def test_success_with_decorator(mock_get):
    mock_get.return_value = fake_response(payload={"speed": 30.0})
    assert fetch_speed("EV-009") == 30.0
    assert mock_get.call_count == 1


# 3) 错误路径：side_effect 让 raise_for_status 抛 HTTPError（模拟 404）
def test_http_error():
    resp = fake_response(status=404, error=requests.exceptions.HTTPError("404 Client Error"))
    with patch("requests.get", return_value=resp):
        with pytest.raises(requests.exceptions.HTTPError):
            fetch_speed("EV-002")


# 4) 超时路径：side_effect 直接抛 ConnectTimeout（模拟网络不通）
def test_timeout():
    with patch("requests.get", side_effect=requests.exceptions.ConnectTimeout("timeout")):
        with pytest.raises(requests.exceptions.ConnectTimeout):
            fetch_speed("EV-003")


# 5) side_effect 列表：同一 mock 连续调用依次返回不同值
def test_side_effect_sequence():
    with patch("requests.get", side_effect=[
        fake_response(payload={"speed": 10.0}),
        fake_response(payload={"speed": 20.0}),
    ]):
        assert fetch_speed("EV-004") == 10.0
        assert fetch_speed("EV-004") == 20.0


# 6) MagicMock 的「自动模仿」是把双刃剑：没配返回值时它静默编造值——float() 返回 1.0、
#    下标取值也照常返回 mock。测试「看起来通过了」，实际测的是假值（假阳性），
#    这正是 mock 配置必须显式写清楚的原因
def test_magicmock_auto_attribute_is_silent_trap():
    with patch("requests.get", return_value=MagicMock()):
        speed = fetch_speed("EV-005")
    assert speed == 1.0   # 没配 json.return_value：静默拿到 1.0 而不是报错——值毫无意义


if __name__ == "__main__":
    pytest.main(["-q", __file__])
