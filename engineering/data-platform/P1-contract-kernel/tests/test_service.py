import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from mosaic_data_contracts.contracts import CONTRACTS, EXAMPLES
from mosaic_kernel.service import DummyService, build_server


class DataServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ledger_path = os.path.join(cls.tmp.name, "ledger.jsonl")
        cls.service = DummyService("data-registry-dummy", CONTRACTS, cls.ledger_path)
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
        self.assertEqual("ok", body["status"])
        self.assertIn("Envelope", body["contracts"])

    def test_register_then_trace_in_ledger(self):
        status, body, headers = self.request(
            "POST",
            "/v1/register",
            {"contract": "TableRef", "kind": "source", "payload": EXAMPLES["TableRef"]},
            trace="trace-data-001",
        )
        self.assertEqual(201, status)
        self.assertTrue(body["registered"])
        self.assertEqual("trace-data-001", headers["X-Trace-Id"])

        status, ledger, _ = self.request("GET", "/v1/ledger?trace_id=trace-data-001")
        self.assertEqual(200, status)
        events = [e["event"] for e in ledger["events"]]
        self.assertIn("register.accepted", events)

    def test_register_rejects_invalid_contract(self):
        payload = dict(EXAMPLES["TableRef"])
        payload.pop("catalog")
        status, body, _ = self.request(
            "POST", "/v1/register", {"contract": "TableRef", "payload": payload}, trace="trace-data-002"
        )
        self.assertEqual(400, status)
        self.assertTrue(any("catalog" in e for e in body["errors"]))

    def test_echo_returns_digest_and_trace(self):
        status, body, _ = self.request(
            "POST", "/v1/echo", {"contract": "Envelope", "payload": EXAMPLES["Envelope"]}
        )
        self.assertEqual(200, status)
        self.assertTrue(body["trace_id"])
        self.assertTrue(body["digest"].startswith("sha256:"))

    def test_unknown_contract_rejected(self):
        status, body, _ = self.request("POST", "/v1/echo", {"contract": "Nope", "payload": {}})
        self.assertEqual(400, status)
        self.assertEqual(["unknown contract: Nope"], body["errors"])

    def test_metrics_exports_service_up(self):
        with urllib.request.urlopen(self.base + "/metrics", timeout=5) as resp:
            text = resp.read().decode("utf-8")
            self.assertEqual(200, resp.status)
        self.assertIn("mosaic_service_up", text)
        self.assertIn("mosaic_service_requests_total", text)


if __name__ == "__main__":
    unittest.main()
