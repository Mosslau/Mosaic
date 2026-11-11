"""故障诊断纵切（P2 · 对应 AI 平台 D3/D8/D9 的一部分）。"""

from .answer import build_answer, prediction_id
from .retrieval import Retriever

__all__ = ["Retriever", "build_answer", "prediction_id"]
