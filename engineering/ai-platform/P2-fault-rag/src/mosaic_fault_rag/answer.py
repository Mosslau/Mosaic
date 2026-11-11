"""故障 → 带引用的答案（Answer 契约的最小生产者）。"""

import hashlib
from typing import Any, Dict, List

from .retrieval import Retriever

MODEL = "local-tfidf-rag/v0"
DEFAULT_THRESHOLD = 0.12

# 故障码到信号语义的映射：让查询带上「电池电压 / 电机温度」，而不是只靠故障码
FAULT_CONTEXT = {
    "P0A1": "battery_voltage 电池电压 过压",
    "P0A2": "motor_temp 电机温度 过温",
}


def build_query(event: Dict[str, Any]) -> str:
    parts = [
        str(event.get("fault_code", "")),
        str(event.get("severity", "")),
        "故障 维修 处置",
        FAULT_CONTEXT.get(event.get("fault_code"), ""),
    ]
    return " ".join(part for part in parts if part)


def prediction_id(event: Dict[str, Any]) -> str:
    raw = "%s|%s" % (event["event_id"], MODEL)
    return "pred-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _doc_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_answer(
    event: Dict[str, Any],
    retriever: Retriever,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = 2,
) -> Dict[str, Any]:
    hits: List[Dict[str, Any]] = retriever.search(build_query(event), top_k=top_k)
    top = hits[0] if hits else {"doc": None, "score": 0.0}

    if top["doc"] is None or top["score"] < threshold:
        return {
            "text": "未检索到足够依据，建议转人工复核并补全故障上下文。",
            "citations": [],
            "confidence": round(float(top["score"]), 4),
            "no_evidence": True,
            "model": MODEL,
        }

    citations = [
        {
            "source_type": "doc",
            "locator": hit["doc"]["doc_id"],
            "hash": _doc_hash(hit["doc"]["text"]),
        }
        for hit in hits
        if hit["score"] > 0
    ][:top_k]

    return {
        "text": top["doc"]["text"],
        "citations": citations,
        "confidence": round(min(0.95, float(top["score"])), 4),
        "no_evidence": False,
        "model": MODEL,
    }


def action_for(answer: Dict[str, Any]) -> Dict[str, str]:
    """答案决定动作：有依据 → 建议工单；无依据 → 转人工。"""
    if answer["no_evidence"]:
        return {"type": "manual_review", "status": "manual_review"}
    return {"type": "workorder", "status": "suggested"}


def should_auto_workorder(answer: Dict[str, Any], min_confidence: float = 0.2) -> bool:
    return (not answer["no_evidence"]) and answer["confidence"] >= min_confidence


def reason_code(verdict: str, answer: Dict[str, Any]) -> str:
    if verdict == "correct":
        return "none"
    if verdict == "unknown":
        return "业务变更"
    if answer["no_evidence"]:
        return "检索错"
    return "推理错"
