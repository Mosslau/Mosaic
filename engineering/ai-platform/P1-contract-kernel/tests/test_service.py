import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from mosaic_ai_contracts.contracts import CONTRACTS, EXAMPLES
from mosaic_kernel.service import DummyService, build_server


class AIServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ledger_path = os.path.join(cls.tmp.name, "ledger.jsonl")
        cls.service = DummyService("ai-service-registry-dummy", CONTRACTS, cls.ledger_path)
        cls.server = build_server(cls.service, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[0], cls.server.server_address[1]
        cls.base = "http://127.0.0.1:%d" % port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, trace=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if trace:
            req.add_header("X-Trace-Id", trace)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8")), exc.headers

    def test_health(self):
        status, body, _ = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertIn("RuntimePort", body["contracts"])

    def test_register_service(self):
        status, body, headers = self.request(
            "POST",
            "/v1/register",
            {"contract": "Service", "kind": "runtime", "payload": EXAMPLES["Service"]},
            trace="trace-ai-001",
        )
        self.assertEqual(201, status)
        self.assertTrue(body["registered"])
        self.assertEqual("trace-ai-001", headers["X-Trace-Id"])
        status, ledger, _ = self.request("GET", "/v1/ledger?trace_id=trace-ai-001")
        self.assertEqual(200, status)
        self.assertIn("register.accepted", [e["event"] for e in ledger["events"]])

    def test_register_rejects_bad_health_enum(self):
        payload = dict(EXAMPLES["Service"], health="unknown")
        status, body, _ = self.request(
            "POST", "/v1/register", {"contract": "Service", "payload": payload}, trace="trace-ai-002"
        )
        self.assertEqual(400, status)
        self.assertTrue(any("health" in e for e in body["errors"]))

    def test_echo_answer(self):
        status, body, _ = self.request(
            "POST", "/v1/echo", {"contract": "Answer", "payload": EXAMPLES["Answer"]}
        )
        self.assertEqual(200, status)
        self.assertTrue(body["digest"].startswith("sha256:"))

    def test_ledger_is_persisted(self):
        self.request(
            "POST", "/v1/echo", {"contract": "RuntimePort", "payload": EXAMPLES["RuntimePort"]}, trace="trace-ai-003"
        )
        status, body, _ = self.request("GET", "/v1/ledger?trace_id=trace-ai-003")
        self.assertEqual(200, status)
        self.assertEqual(1, len(body["events"]))
        self.assertEqual("echo.accepted", body["events"][0]["event"])

    def test_metrics_endpoint(self):
        with urllib.request.urlopen(self.base + "/metrics", timeout=5) as resp:
            text = resp.read().decode("utf-8")
            self.assertEqual(200, resp.status)
        self.assertIn("mosaic_service_up", text)


if __name__ == "__main__":
    unittest.main()
