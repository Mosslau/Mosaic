"""health —— ph15 阶段项目：部件健康预测（Component Health Prediction）。

合成数据 + 机器学习建模的最小完整工程：
    合成部件老化数据 → train/test 划分 → HEALTH 回归 + 健康等级分类 →
    评估指标 → joblib 保存模型 → 命令行预测（模型部署的最小闭环）。
"""

__version__ = "0.1.0"

from health.data import FEATURES, GRADE_NAMES, load_component_data
from health.evaluate import evaluate_classifier, evaluate_regressor, summary_metrics
from health.model import ComponentHealthPipeline, train_pipeline

__all__ = [
    "FEATURES",
    "GRADE_NAMES",
    "ComponentHealthPipeline",
    "load_component_data",
    "train_pipeline",
    "evaluate_regressor",
    "evaluate_classifier",
    "summary_metrics",
]
