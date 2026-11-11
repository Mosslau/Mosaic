"""D1 dummy 服务：注册 + 调用 + trace + 账本 + 指标。

刻意保持薄：只做「契约校验 → 记账 → 返回 trace」这条最小闭环，
生产级路由、鉴权、持久化分别属于平台的 D5/D8/D11。
"""

import argparse
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .contracts import ContractSet, canonical_digest
from .ledger import JsonlLedger

SERVICE_VERSION = "0.1.0"


class DummyService:
    def __init__(
        self,
        name: str,
        contracts: ContractSet,
        ledger_path: str,
        version: str = SERVICE_VERSION,
    ):
        self.name = name
        self.version = version
        self.contracts = contracts
        self.ledger = JsonlLedger(ledger_path)
        self.started_at = time.time()
        self._lock = threading.Lock()
        self._registry: List[Dict[str, Any]] = []
        self._counters: Dict[Tuple[str, str, int], int] = {}

    # ---- 记录 ----
    def count(self, method: str, path: str, status: int) -> None:
        with self._lock:
            key = (method, path, status)
            self._counters[key] = self._counters.get(key, 0) + 1

    def register(self, contract: str, payload: Dict[str, Any], trace_id: str, kind: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
        errors = self.contracts.validate(contract, payload)
        if errors:
            self.ledger.append(trace_id, "register.rejected", {"contract": contract, "errors": errors})
            return 400, {"trace_id": trace_id, "contract": contract, "errors": errors}
        digest = canonical_digest(payload)
        record = {
            "contract": contract,
            "kind": kind or contract,
            "digest": digest,
            "registered_at": self._now(),
        }
        with self._lock:
            self._registry.append(record)
        self.ledger.append(trace_id, "register.accepted", {"contract": contract, "kind": record["kind"], "digest": digest})
        return 201, {"trace_id": trace_id, "contract": contract, "digest": digest, "registered": True}

    def echo(self, contract: str, payload: Dict[str, Any], trace_id: str) -> Tuple[int, Dict[str, Any]]:
        errors = self.contracts.validate(contract, payload)
        if errors:
            self.ledger.append(trace_id, "echo.rejected", {"contract": contract, "errors": errors})
            return 400, {"trace_id": trace_id, "contract": contract, "errors": errors}
        digest = canonical_digest(payload)
        self.ledger.append(trace_id, "echo.accepted", {"contract": contract, "digest": digest})
        return 200, {
            "trace_id": trace_id,
            "contract": contract,
            "digest": digest,
            "service": self.name,
            "received_at": self._now(),
        }

    # ---- 只读视图 ----
    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": self.name,
            "version": self.version,
            "contracts": self.contracts.names(),
            "registry_size": len(self._registry),
            "uptime_seconds": round(time.time() - self.started_at, 1),
        }

    def metrics(self) -> str:
        lines = [
            "# HELP mosaic_service_up 1 when the dummy service is serving",
            "# TYPE mosaic_service_up gauge",
            'mosaic_service_up{service="%s"} 1' % self.name,
            "# HELP mosaic_service_uptime_seconds seconds since start",
            "# TYPE mosaic_service_uptime_seconds gauge",
            'mosaic_service_uptime_seconds{service="%s"} %.1f' % (self.name, time.time() - self.started_at),
            "# HELP mosaic_service_registry_size registered contracts",
            "# TYPE mosaic_service_registry_size gauge",
            'mosaic_service_registry_size{service="%s"} %d' % (self.name, len(self._registry)),
            "# HELP mosaic_service_requests_total handled requests",
            "# TYPE mosaic_service_requests_total counter",
        ]
        for (method, path, status), value in sorted(self._counters.items()):
            lines.append(
                'mosaic_service_requests_total{service="%s",method="%s",path="%s",status="%d"} %d'
                % (self.name, method, path, status, value)
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _Handler(BaseHTTPRequestHandler):
    service: DummyService  # 由 server 注入
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # 默认静默，避免测试输出被刷
        return

    def _trace_id(self) -> str:
        incoming = self.headers.get("X-Trace-Id")
        return incoming.strip() if incoming and incoming.strip() else uuid.uuid4().hex

    def _send(self, status: int, body: Any, trace_id: str, content_type: str = "application/json") -> None:
        if isinstance(body, (dict, list)):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            raw = str(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Trace-Id", trace_id)
        self.end_headers()
        self.wfile.write(raw)
        self.service.count(self.command, urlparse(self.path).path, status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        trace_id = self._trace_id()
        if parsed.path == "/health":
            self._send(200, self.service.health(), trace_id)
        elif parsed.path == "/metrics":
            self._send(200, self.service.metrics(), trace_id, "text/plain")
        elif parsed.path == "/v1/contracts":
            self._send(200, self.service.contracts.describe(), trace_id)
        elif parsed.path == "/v1/ledger":
            query = parse_qs(parsed.query)
            wanted = (query.get("trace_id") or [None])[0]
            self._send(200, {"events": self.service.ledger.read(wanted)}, trace_id)
        else:
            self._send(404, {"error": "not found", "path": parsed.path}, trace_id)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        trace_id = self._trace_id()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"trace_id": trace_id, "error": "invalid json: %s" % exc}, trace_id)
            return
        if not isinstance(body, dict):
            self._send(400, {"trace_id": trace_id, "error": "body must be a JSON object"}, trace_id)
            return
        contract = body.get("contract")
        if not isinstance(contract, str) or not contract:
            self._send(400, {"trace_id": trace_id, "error": "missing 'contract'"}, trace_id)
            return
        payload = body.get("payload", {})
        if parsed.path == "/v1/register":
            status, response = self.service.register(contract, payload, trace_id, body.get("kind"))
            self._send(status, response, trace_id)
        elif parsed.path == "/v1/echo":
            status, response = self.service.echo(contract, payload, trace_id)
            self._send(status, response, trace_id)
        else:
            self._send(404, {"error": "not found", "path": parsed.path}, trace_id)


def build_server(service: DummyService, port: int = 0, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    handler = type("BoundHandler", (_Handler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler)


def run(name: str, contracts: ContractSet, default_port: int, argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Mosaic D1 dummy service: %s" % name)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--ledger", default="var/ledger.jsonl")
    args = parser.parse_args(argv)

    service = DummyService(name=name, contracts=contracts, ledger_path=args.ledger)
    server = build_server(service, args.port)
    host, port = server.server_address[0], server.server_address[1]
    print("[%s] listening on http://%s:%d  ledger=%s" % (name, host, port, service.ledger.path))
    print("[%s] contracts: %s" % (name, ", ".join(contracts.names())))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
