import unittest

from mosaic_ai_contracts.contracts import CONTRACTS
from mosaic_fault_rag.answer import (
    build_answer,
    build_query,
    action_for,
    prediction_id,
    reason_code,
    should_auto_workorder,
)
from mosaic_fault_rag.corpus import get_docs
from mosaic_fault_rag.retrieval import Retriever

P0A1_EVENT = {
    "event_id": "veh-0001-2026-11-11T05:55:40Z-P0A1",
    "device_id": "veh-0001",
    "fault_code": "P0A1",
    "severity": "P1",
    "ts": "2026-11-11T05:55:40Z",
    "value": 60.0,
}

P0A2_EVENT = {
    "event_id": "veh-0002-2026-11-11T05:55:42Z-P0A2",
    "device_id": "veh-0002",
    "fault_code": "P0A2",
    "severity": "P0",
    "ts": "2026-11-11T05:55:42Z",
    "value": 110.0,
}

UNKNOWN_EVENT = {
    "event_id": "veh-0003-2026-11-11T05:55:44Z-P9X9",
    "device_id": "veh-0003",
    "fault_code": "P9X9",
    "severity": "P2",
    "ts": "2026-11-11T05:55:44Z",
    "value": 1.0,
}


class RetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = Retriever(get_docs())

    def test_p0a1_ranks_battery_doc(self):
        hits = self.retriever.search(build_query(P0A1_EVENT))
        self.assertEqual("manual://battery/p0a1", hits[0]["doc"]["doc_id"])

    def test_p0a2_ranks_motor_doc(self):
        hits = self.retriever.search(build_query(P0A2_EVENT))
        self.assertEqual("manual://motor/p0a2", hits[0]["doc"]["doc_id"])


class AnswerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = Retriever(get_docs())

    def test_answer_passes_contract(self):
        answer = build_answer(P0A1_EVENT, self.retriever)
        self.assertEqual([], CONTRACTS.validate("Answer", answer))

    def test_citations_have_locator_and_hash(self):
        answer = build_answer(P0A1_EVENT, self.retriever)
        self.assertFalse(answer["no_evidence"])
        self.assertGreaterEqual(len(answer["citations"]), 1)
        for citation in answer["citations"]:
            self.assertTrue(citation["locator"].startswith("manual://"))
            self.assertTrue(citation["hash"].startswith("sha256:"))

    def test_unknown_fault_is_no_evidence(self):
        answer = build_answer(UNKNOWN_EVENT, self.retriever)
        self.assertTrue(answer["no_evidence"])
        self.assertEqual([], answer["citations"])
        self.assertLess(answer["confidence"], 0.12)

    def test_prediction_id_is_stable(self):
        self.assertEqual(prediction_id(P0A1_EVENT), prediction_id(P0A1_EVENT))
        self.assertNotEqual(prediction_id(P0A1_EVENT), prediction_id(P0A2_EVENT))

    def test_no_evidence_becomes_manual_review(self):
        answer = build_answer(UNKNOWN_EVENT, self.retriever)
        action = action_for(answer)
        self.assertEqual("manual_review", action["type"])
        self.assertEqual("manual_review", action["status"])
        self.assertFalse(should_auto_workorder(answer))

    def test_grounded_answer_becomes_workorder(self):
        answer = build_answer(P0A1_EVENT, self.retriever)
        self.assertTrue(should_auto_workorder(answer))
        self.assertEqual("workorder", action_for(answer)["type"])

    def test_reason_code_mapping(self):
        grounded = build_answer(P0A1_EVENT, self.retriever)
        ungrounded = build_answer(UNKNOWN_EVENT, self.retriever)
        self.assertEqual("none", reason_code("correct", grounded))
        self.assertEqual("推理错", reason_code("wrong", grounded))
        self.assertEqual("检索错", reason_code("wrong", ungrounded))
        self.assertEqual("业务变更", reason_code("unknown", grounded))


if __name__ == "__main__":
    unittest.main()
