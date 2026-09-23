"""CLI 测试：demo 自检、默认训练、产物落盘、predict 推理一致性。"""

from __future__ import annotations

import json

import numpy as np

from health.model import ComponentHealthPipeline
from cli import main


def test_demo_self_check(tmp_path, capsys):
    """--demo 小样本训练 + 断言 + 产物落盘，退出码 0、stdout 有自检结论。"""
    out = tmp_path / "demo"
    main(["--demo", "--n", "300", "--seed", "42", "--out", str(out)])
    captured = capsys.readouterr().out
    assert "自检通过" in captured
    assert (out / "model.joblib").exists()
    assert (out / "metrics.json").exists()


def test_default_train_writes_metrics(tmp_path):
    """默认训练会落模型 + metrics.json，且 JSON 可读、字段齐全、模型优于 baseline。"""
    out = tmp_path / "model"
    main(["--n", "400", "--seed", "42", "--out", str(out)])
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert set(metrics) >= {
        "n_train",
        "n_test",
        "regression",
        "classification",
        "confusion_matrix",
        "baselines",
    }
    assert metrics["regression"]["rmse"] < metrics["baselines"]["reg_rmse_mean_pred"]
    assert metrics["classification"]["accuracy"] > metrics["baselines"]["clf_acc_majority"]


def test_predict_uses_saved_model(tmp_path, capsys):
    """--predict 读取产物并给出合理预测（模型部署最小闭环的端到端验证）。"""
    out = tmp_path / "model"
    main(["--n", "400", "--seed", "42", "--out", str(out)])
    main(["--predict", "1500", "25", "80", "1.0", "--out", str(out)])
    captured = capsys.readouterr().out
    assert "预测 HEALTH" in captured and "健康等级" in captured

    # 与直接加载产物推理的结果一致（同一模型、同一输入）
    pipeline = ComponentHealthPipeline.load(out / "model.joblib")
    x = np.array([[1500.0, 25.0, 80.0, 1.0]])
    health = float(pipeline.predict_health(x)[0])
    grade = int(pipeline.predict_grade(x)[0])
    assert 40.0 <= health <= 100.0
    assert grade in (0, 1, 2)
    assert f"{health:.1f}%" in captured


def test_predict_without_model_fails(tmp_path, capsys):
    """模型不存在时 --predict 报错退出（错误路径也要测）。"""
    out = tmp_path / "empty"
    try:
        main(["--predict", "1500", "25", "80", "1.0", "--out", str(out)])
        raise AssertionError("应因模型缺失而退出")
    except SystemExit as exc:
        assert exc.code == 2
        assert "模型不存在" in capsys.readouterr().err
