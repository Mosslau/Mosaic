"""模型测试：可复现性、泛化指标、产物保存/加载闭环。"""

from __future__ import annotations

import numpy as np

from health.data import load_component_data
from health.evaluate import clf_baseline, evaluate_classifier, evaluate_regressor, reg_baseline
from health.model import ComponentHealthPipeline, train_pipeline


def _fixture(n: int = 400) -> tuple:
    data = load_component_data(n=n, seed=42)
    train, test = data.split(test_size=0.25, seed=42)
    return train, test


def test_same_seed_same_metrics():
    """同数据同 seed → 训练可复现（浮点误差 ~1e-13 内一致）。"""
    train, test = _fixture()
    p1 = train_pipeline(train)
    p2 = train_pipeline(train)
    assert np.allclose(p1.predict_health(test.X), p2.predict_health(test.X), atol=1e-10)
    assert np.array_equal(p1.predict_grade(test.X), p2.predict_grade(test.X))


def test_regression_beats_mean_baseline():
    """HEALTH 回归显著优于「预测均值」baseline（先 baseline 再复杂化的验收）。"""
    train, test = _fixture()
    pipeline = train_pipeline(train)
    rmse = evaluate_regressor(pipeline, test)["rmse"]
    base = reg_baseline(train, test)
    assert rmse < base * 0.7, f"模型 RMSE {rmse:.2f} 应明显低于 baseline {base:.2f}"
    assert evaluate_regressor(pipeline, test)["r2"] > 0.9, "HEALTH 回归 R² 应 > 0.9"


def test_classification_beats_majority_baseline():
    """等级分类 acc/macro-F1 显著优于多数类 baseline。"""
    train, test = _fixture()
    pipeline = train_pipeline(train)
    clf = evaluate_classifier(pipeline, test)
    base = clf_baseline(train, test)
    assert clf["accuracy"] > base + 0.05
    assert clf["macro_f1"] > 0.7, "等级分类 macro-F1 应 > 0.7"


def test_pipeline_save_load_roundtrip(tmp_path):
    """joblib 产物：save → load 后预测一致（模型部署最小闭环的测试）。"""
    train, test = _fixture(n=250)
    pipeline = train_pipeline(train)
    path = pipeline.save(tmp_path)
    loaded = ComponentHealthPipeline.load(path)
    assert path.exists() and path.stat().st_size > 0
    assert np.allclose(loaded.predict_health(test.X), pipeline.predict_health(test.X), atol=1e-10)
    assert loaded.features == pipeline.features
    assert loaded.n_train == pipeline.n_train


def test_no_target_leakage_features():
    """教学点固化：特征里不允许出现 health/grade（目标不能当特征）。"""
    train, _ = _fixture()
    assert "health" not in train_pipeline(train).features
    assert "grade" not in train_pipeline(train).features
