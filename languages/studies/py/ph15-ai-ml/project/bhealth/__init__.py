"""bhealth —— ph15 阶段项目：电池健康预测（Battery Health Prediction）。

合成数据 + 机器学习建模的最小完整工程：
    合成电池老化数据 → train/test 划分 → SOH 回归 + 健康等级分类 →
    评估指标 → joblib 保存模型 → 命令行预测（模型部署的最小闭环）。
"""

__version__ = "0.1.0"

from bhealth.data import FEATURES, GRADE_NAMES, load_battery_data
from bhealth.evaluate import evaluate_classifier, evaluate_regressor, summary_metrics
from bhealth.model import BatteryHealthPipeline, train_pipeline

__all__ = [
    "FEATURES",
    "GRADE_NAMES",
    "BatteryHealthPipeline",
    "load_battery_data",
    "train_pipeline",
    "evaluate_regressor",
    "evaluate_classifier",
    "summary_metrics",
]
