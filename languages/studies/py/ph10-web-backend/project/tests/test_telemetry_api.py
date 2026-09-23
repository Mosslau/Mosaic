# project/tests/test_telemetry_api.py —— 离线测试：上报 / 校验 / 查询 / 统计 / CLI 演示
# 运行（在 project/ 目录下）：pytest -q（已验证，7 个用例全过，不依赖网络）
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 导入平级的 telemetry_api.py

from fastapi.testclient import TestClient  # noqa: E402

from telemetry_api import build_demo_rows, create_app, main  # noqa: E402


def make_client(tmp_path) -> TestClient:
    """每个用例一个独立临时 sqlite 库，互不污染。"""
    db = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db}")
    return TestClient(app)


def post(client, payload, path="/telemetry"):
    return client.post(path, json=payload)


def test_report_single_creates_row(tmp_path):
    with make_client(tmp_path) as client:
        r = post(client, {"device_id": "V001", "ts": "2024-06-01T08:00:00",
                          "speed": 60.5, "soc": 78.5})
        assert r.status_code == 201
        body = r.json()
        assert body["id"] == 1                      # response_model 带 id
        assert body["device_id"] == "V001"
        assert body["speed"] == 60.5 and body["soc"] == 78.5
        # 列表能查到这条记录
        assert len(client.get("/telemetry").json()) == 1


def test_report_validation_ranges(tmp_path):
    with make_client(tmp_path) as client:
        base = {"device_id": "V001", "ts": "2024-06-01T08:00:00",
                "speed": 60.0, "soc": 80.0}
        for field, bad, loc_type in [("speed", 250, "less_than_equal"),
                                     ("speed", -5, "greater_than_equal"),
                                     ("soc", 101, "less_than_equal")]:
            payload = dict(base, **{field: bad})
            r = post(client, payload)
            assert r.status_code == 422
            err = r.json()["detail"][0]
            assert err["loc"] == ["body", field] and err["type"] == loc_type


def test_batch_report_and_limits(tmp_path):
    with make_client(tmp_path) as client:
        rows = [{"device_id": f"V00{i}", "ts": "2024-06-01T08:00:00",
                 "speed": 60.0, "soc": 80.0} for i in range(1, 4)]
        r = client.post("/telemetry/batch", json=rows)
        assert r.status_code == 201 and r.json() == {"inserted": 3}

        r = client.post("/telemetry/batch", json=[])              # 空列表 → 400
        assert r.status_code == 400

        rows_bad = [{"device_id": "VX", "ts": "2024-06-01T08:00:00",
                     "speed": 500, "soc": 80.0}]                  # 批量中一条非法 → 422
        r = client.post("/telemetry/batch", json=rows_bad)
        assert r.status_code == 422

        assert len(client.get("/telemetry").json()) == 3          # 失败的不入库


def test_list_telemetry_filters(tmp_path):
    with make_client(tmp_path) as client:
        ts_list = ["2024-06-01T08:00:00", "2024-06-01T08:10:00", "2024-06-01T08:20:00"]
        for i, ts in enumerate(ts_list):
            post(client, {"device_id": "V001", "ts": ts, "speed": 60.0 + i, "soc": 80.0})
        post(client, {"device_id": "V002", "ts": "2024-06-01T08:00:00",
                      "speed": 90.0, "soc": 70.0})

        assert len(client.get("/telemetry").json()) == 4
        by_device = client.get("/telemetry", params={"device_id": "V001"}).json()
        assert len(by_device) == 3 and all(x["device_id"] == "V001" for x in by_device)

        window = client.get("/telemetry",
                            params={"since": "2024-06-01T08:05:00",
                                    "until": "2024-06-01T08:15:00"}).json()
        assert [x["ts"] for x in window] == ["2024-06-01T08:10:00"]

        limited = client.get("/telemetry", params={"limit": 2}).json()
        assert len(limited) == 2


def test_stats_aggregation(tmp_path):
    with make_client(tmp_path) as client:
        # V001: 3 条 speed [50, 60, 70] → avg 60 / max 70；V002: 2 条 [80, 100] → avg 90 / max 100
        data = [
            ("V001", "2024-06-01T08:00:00", 50.0, 90.0),
            ("V001", "2024-06-01T08:10:00", 60.0, 85.0),
            ("V001", "2024-06-01T08:20:00", 70.0, 80.0),
            ("V002", "2024-06-01T08:00:00", 80.0, 70.0),
            ("V002", "2024-06-01T08:10:00", 100.0, 60.0),
        ]
        for vid, ts, speed, soc in data:
            post(client, {"device_id": vid, "ts": ts, "speed": speed, "soc": soc})

        stats = client.get("/telemetry/stats").json()
        assert stats == [
            {"device_id": "V001", "count": 3, "avg_speed": 60.0,
             "max_speed": 70.0, "avg_soc": 85.0},
            {"device_id": "V002", "count": 2, "avg_speed": 90.0,
             "max_speed": 100.0, "avg_soc": 65.0},
        ]

        one = client.get("/telemetry/stats", params={"device_id": "V002"}).json()
        assert len(one) == 1 and one[0]["count"] == 2 and one[0]["max_speed"] == 100.0

        none = client.get("/telemetry/stats", params={"device_id": "V999"}).json()
        assert none == []


def test_main_demo_offline(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "批量上报" in out and "全量分组统计" in out and "自检通过" in out


def test_demo_rows_deterministic():
    rows = build_demo_rows()
    assert len(rows) == 72                       # 3 台设备 × 24 条
    assert {r.device_id for r in rows} == {"V001", "V002", "V003"}
    assert all(0 <= r.speed <= 200 and 0 <= r.soc <= 100 for r in rows)
