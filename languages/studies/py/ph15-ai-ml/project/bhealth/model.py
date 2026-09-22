"""模型定义与训练（project/bhealth/model.py）。

管线：RandomForestRegressor 预测 SOH（连续值）+ RandomForestClassifier 预测
健康等级（分类）。两个都是树模型——对特征缩放不敏感（ex02 的结论），
因此这里不套 StandardScaler；换成 Ridge/线性模型才需要缩放（见 README 扩展）。

保存/加载用 joblib（sklearn 自带），这是「模型部署」的最小闭环：
模型产物 = 两个模型对象 + 特征名 + 元信息，落盘后另一个进程加载即可推理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from bhealth.data import FEATURES, GRADE_NAMES, BatteryDataset

# 两个模型共用的随机森林超参（n_estimators=300 足够稳，训练 <1s）
MODEL_PARAMS: dict[str, object] = {"n_estimators": 300, "random_state": 42, "n_jobs": -1}


@dataclass
class BatteryHealthPipeline:
    """保存/加载用的模型包：回归器 + 分类器 + 元信息。"""

    regressor: RandomForestRegressor
    classifier: RandomForestClassifier
    features: list[str] = field(default_factory=lambda: list(FEATURES))
    grade_names: list[str] = field(default_factory=lambda: list(GRADE_NAMES))
    n_train: int = 0

    def predict_soh(self, X: object) -> object:
        return self.regressor.predict(X)

    def predict_grade(self, X: object) -> object:
        return self.classifier.predict(X)

    def save(self, out_dir: Path) -> Path:
        """模型产物写 out_dir/model.joblib（产物纪律：默认写 /tmp，不入库）。"""
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "model.joblib"
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: Path) -> BatteryHealthPipeline:
        return joblib.load(path)


def train_pipeline(train: BatteryDataset, n_estimators: int = 300) -> BatteryHealthPipeline:
    """在训练集上同时拟合 SOH 回归器与等级分类器。"""
    reg = RandomForestRegressor(
        n_estimators=n_estimators, random_state=MODEL_PARAMS["random_state"], n_jobs=-1
    ).fit(train.X, train.soh)
    clf = RandomForestClassifier(
        n_estimators=n_estimators, random_state=MODEL_PARAMS["random_state"], n_jobs=-1
    ).fit(train.X, train.grade)
    return BatteryHealthPipeline(regressor=reg, classifier=clf, n_train=train.X.shape[0])
