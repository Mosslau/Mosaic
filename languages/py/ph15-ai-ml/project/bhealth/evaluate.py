"""评估指标（project/bhealth/evaluate.py）。

回归（SOH 预测）用 RMSE / MAE / R²；分类（健康等级）用 accuracy / macro-F1 /
混淆矩阵；summary_metrics 把全部指标收进一个 dict，便于落 JSON 与验收断言。
与主文档 3.5 的指标讲解一致：不平衡的等级分布下要看 macro-F1 而不是只看 acc。
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from bhealth.data import GRADE_NAMES, BatteryDataset
from bhealth.model import BatteryHealthPipeline


# 两个「什么都不学」的 baseline（roadmap 必会概念：先 baseline 再复杂化）
def reg_baseline(train: BatteryDataset, test: BatteryDataset) -> float:
    """预测训练集 SOH 均值，返回测试集 RMSE。"""
    pred = np.full(test.soh.shape[0], float(train.soh.mean()))
    return float(mean_squared_error(test.soh, pred) ** 0.5)


def clf_baseline(train: BatteryDataset, test: BatteryDataset) -> float:
    """永远猜训练集最常见的等级，返回测试集准确率。"""
    majority = int(np.bincount(train.grade).argmax())
    return float(accuracy_score(test.grade, np.full(test.grade.shape[0], majority)))


def evaluate_regressor(pipeline: BatteryHealthPipeline, test: BatteryDataset) -> dict[str, float]:
    pred = pipeline.predict_soh(test.X)
    return {
        "rmse": float(mean_squared_error(test.soh, pred) ** 0.5),
        "mae": float(mean_absolute_error(test.soh, pred)),
        "r2": float(r2_score(test.soh, pred)),
    }


def evaluate_classifier(pipeline: BatteryHealthPipeline, test: BatteryDataset) -> dict[str, float]:
    pred = pipeline.predict_grade(test.X)
    return {
        "accuracy": float(accuracy_score(test.grade, pred)),
        "macro_f1": float(f1_score(test.grade, pred, average="macro")),
    }


def summary_metrics(
    pipeline: BatteryHealthPipeline, train: BatteryDataset, test: BatteryDataset
) -> dict[str, Any]:
    """汇总回归/分类指标 + 两个 baseline 对照，一次调用拿全。"""
    reg = evaluate_regressor(pipeline, test)
    clf = evaluate_classifier(pipeline, test)
    conf = confusion_matrix(test.grade, pipeline.predict_grade(test.X))
    grade_dist = np.bincount(test.grade, minlength=len(GRADE_NAMES)).tolist()
    return {
        "n_train": int(train.X.shape[0]),
        "n_test": int(test.X.shape[0]),
        "grade_dist_test": grade_dist,  # 等级分布（看不平衡程度）
        "regression": reg,
        "classification": clf,
        "confusion_matrix": conf.tolist(),
        "baselines": {
            "reg_rmse_mean_pred": reg_baseline(train, test),  # 回归 baseline：预测均值
            "clf_acc_majority": clf_baseline(train, test),  # 分类 baseline：多数类
        },
    }
