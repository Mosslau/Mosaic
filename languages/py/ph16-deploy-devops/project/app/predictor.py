"""电池健康预测服务的部署模板（ph16 project/app/predictor.py）。

两种推理后端：
- JoblibPredictor：加载 train.py 训好的 joblib 产物（ph15 的「模型产物」在服务化
  场景的消费方式——训练在 CI/训练机，产物随发布分发，服务进程只加载不训练）；
- RulePredictor：无产物时的规则兜底（与训练数据同源的老化公式），保证服务
  「裸奔也能起」，同时让 /ready 能如实报告自己用的是哪一档。

MODEL_PATH 语义（配置与代码分离，12-factor）：
- 未设置 → RulePredictor（model_type="rule"，就绪）；
- 已设置但文件不存在 → 不就绪（/ready 503）——配置了的依赖缺失必须暴露，
  不能静默降级把「模型没挂上」藏成「服务正常」。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

FEATURES = ["cycles", "avg_temp", "depth", "c_rate"]


class Predictor(Protocol):
    """推理后端协议：给定 4 个工况特征，返回 SOH（%）。"""

    model_type: str

    def predict_soh(self, features: list[float]) -> float: ...


class RulePredictor:
    """规则模型兜底：SOH = 100 − cycles × 分段老化率（高温/深放/大倍率加速）。"""

    model_type = "rule"

    def predict_soh(self, features: list[float]) -> float:
        cycles, avg_temp, depth, c_rate = features
        loss = (
            0.008
            + 0.00025 * max(avg_temp - 25, 0)
            + 0.0005 * max(depth - 70, 0)
            + 0.0015 * max(c_rate - 1.5, 0)
        )
        return min(100.0, max(40.0, 100.0 - cycles * loss))


class JoblibPredictor:
    """joblib 产物后端：产物是 sklearn Pipeline/模型，特征顺序见 FEATURES。"""

    model_type = "joblib"

    def __init__(self, path: Path) -> None:
        import joblib  # 延迟导入：规则模式下服务不需要 sklearn

        self._model = joblib.load(path)

    def predict_soh(self, features: list[float]) -> float:
        pred = self._model.predict([features])
        return float(pred[0])


def load_predictor() -> Predictor | None:
    """按 MODEL_PATH 环境变量装后端；配置了产物但缺失时返回 None（不就绪）。"""
    raw = os.environ.get("MODEL_PATH", "").strip()
    if not raw:
        return RulePredictor()
    path = Path(raw)
    if not path.exists():
        return None
    return JoblibPredictor(path)
