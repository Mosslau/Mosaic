"""ph16 项目测试（project/tests/test_api.py）。

覆盖：双探针分工、输入校验、规则兜底推理、训练产物闭环（train → joblib →
JoblibPredictor）、缺失产物的 503、/metrics 文本格式。全部离线可跑。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.predictor import RulePredictor

COND = {"cycles": 1500, "avg_temp": 25, "depth": 80, "c_rate": 1.0}


class Ph15LikePipeline:
    """与 ph15 BatteryHealthPipeline（bhealth/model.py）同形态：封装回归器 + predict_soh。

    刻意**不提供** sklearn 的 .predict——joblib 序列化要求类在模块层可见，
    故放在测试模块顶层，供 test_ph15_pipeline_artifact_compat 构造产物。
    """

    def __init__(self, regressor: object) -> None:
        self.regressor = regressor

    def predict_soh(self, X: object) -> object:
        return self.regressor.predict(X)  # type: ignore[no-untyped-call]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """规则兜底模式的服务（不设 MODEL_PATH）。"""
    monkeypatch.delenv("MODEL_PATH", raising=False)
    with TestClient(create_app()) as c:
        yield c


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["model_type"] == "rule"


def test_predict_rule_fallback(client: TestClient) -> None:
    r = client.post("/predict", json=COND)
    assert r.status_code == 200
    body = r.json()
    assert body["soh"] == 80.5 and body["grade"] == "退化" and body["model_type"] == "rule"


def test_predict_validation_422(client: TestClient) -> None:
    bad = {**COND, "cycles": -1}
    assert client.post("/predict", json=bad).status_code == 422


def test_metrics_endpoint(client: TestClient) -> None:
    client.post("/predict", json=COND)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "# TYPE bhealth_requests_total counter" in r.text
    assert 'bhealth_model_info{model_type="rule"} 1' in r.text
    assert "bhealth_predict_seconds_count 1" in r.text


def test_missing_artifact_not_ready(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """配置了 MODEL_PATH 但产物缺失 → /ready 与 /predict 都 503（不静默降级）。"""
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "nope.joblib"))
    with TestClient(create_app()) as c:
        assert c.get("/health").status_code == 200  # liveness 不受依赖影响
        assert c.get("/ready").status_code == 503
        assert c.post("/predict", json=COND).status_code == 503
        assert 'bhealth_model_info{model_type="missing"} 1' in c.get("/metrics").text


def test_trained_artifact_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """完整闭环：train.py 训产物 → MODEL_PATH 指向它 → 服务走 joblib 后端。"""
    joblib = pytest.importorskip("joblib")
    from train import train

    path = tmp_path / "model.joblib"
    joblib.dump(train(n=400, seed=42), path)
    monkeypatch.setenv("MODEL_PATH", str(path))
    with TestClient(create_app()) as c:
        r = c.get("/ready")
        assert r.status_code == 200 and r.json()["model_type"] == "joblib"
        soh = c.post("/predict", json=COND).json()["soh"]
        rule = RulePredictor().predict_soh([1500, 25, 80, 1.0])
        assert abs(soh - rule) < 5.0  # 训练数据与规则同源，预测应贴近规则值


def test_ph15_pipeline_artifact_compat(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """ph15 产物形态（BatteryHealthPipeline）可被 JoblibPredictor 直接消费。

    ph15 项目 languages/py/ph15-ai-ml/project/bhealth/model.py 的产物是 dataclass
    BatteryHealthPipeline：暴露 predict_soh(X)/predict_grade(X)，**没有** sklearn 的
    .predict。若 JoblibPredictor 只会调 .predict，加载 ph15 产物会 AttributeError，
    「ph15 产物 → ph16 服务」的闭环就断了——本用例用同形态 stub 验证形态分派。
    """
    joblib = pytest.importorskip("joblib")
    from train import train

    path = tmp_path / "ph15-style.joblib"
    joblib.dump(Ph15LikePipeline(train(n=300, seed=42)), path)
    monkeypatch.setenv("MODEL_PATH", str(path))
    with TestClient(create_app()) as c:
        r = c.get("/ready")
        assert r.status_code == 200 and r.json()["model_type"] == "joblib"
        soh = c.post("/predict", json=COND).json()["soh"]
        rule = RulePredictor().predict_soh([1500, 25, 80, 1.0])
        assert abs(soh - rule) < 5.0  # 与规则同源，预测应贴近规则值
