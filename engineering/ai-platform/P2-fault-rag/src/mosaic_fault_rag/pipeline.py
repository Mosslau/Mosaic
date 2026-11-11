"""AI 侧纵切：故障事件 → 检索 → Answer（带引用） → 动作 → 反馈。"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from mosaic_ai_contracts.contracts import CONTRACTS
from mosaic_kernel.docker_cli import pg_query, psql

from .answer import (
    MODEL,
    action_for,
    build_answer,
    prediction_id,
    reason_code,
    should_auto_workorder,
)
from .corpus import get_docs
from .retrieval import Retriever

DDL = """
create table if not exists diagnosis_answers (
  event_id text primary key,
  prediction_id text not null,
  device_id text not null,
  fault_code text not null,
  answer_text text not null,
  citations jsonb not null,
  confidence double precision not null,
  no_evidence boolean not null,
  model text,
  trace_id text,
  created_at timestamptz not null default now()
);
create table if not exists workorders (
  workorder_id text primary key,
  event_id text not null,
  prediction_id text not null,
  action_type text not null,
  status text not null,
  created_at timestamptz not null default now()
);
create table if not exists feedback_events (
  feedback_id text primary key,
  prediction_id text not null,
  verdict text not null,
  reason_code text not null,
  actor text,
  evidence_ref text,
  created_at timestamptz not null default now()
);
alter table workorders add column if not exists trace_id text;
alter table feedback_events add column if not exists trace_id text;
create table if not exists ai_pipeline_ledger (
  id bigserial primary key,
  ts timestamptz not null default now(),
  trace_id text not null,
  stage text not null,
  detail jsonb not null
);
"""


def _q(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _json(value: Any) -> str:
    return _q(json.dumps(value, ensure_ascii=False, sort_keys=True))


def fetch_faults(limit: int = 20) -> List[Dict[str, Any]]:
    sql = (
        "select row_to_json(t)::text from ("
        "select event_id, device_id, fault_code, severity, ts::text as ts, value "
        "from fault_events order by ts desc limit %d) t;" % limit
    )
    output = pg_query(sql)
    faults = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            faults.append(json.loads(line))
    return faults


def ledger(trace_id: str, stage: str, detail: Dict[str, Any]) -> None:
    psql(
        "insert into ai_pipeline_ledger(trace_id, stage, detail) values (%s,%s,%s::jsonb);\n"
        % (_q(trace_id), _q(stage), _json(detail))
    )


def run(limit: int, verdict: str, threshold: float, actor: str = "simulator") -> Dict[str, Any]:
    trace_id = "trace-rag-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    psql(DDL)
    faults = fetch_faults(limit)
    if not faults:
        raise RuntimeError("fault_events 为空：先跑数据侧纵切 P2-device-slice/slice.sh")

    ledger(trace_id, "read_faults", {"faults": len(faults), "limit": limit})
    retriever = Retriever(get_docs())

    answers = 0
    workorders = 0
    feedback = 0
    no_evidence = 0
    confidences: List[float] = []
    samples: List[Dict[str, Any]] = []

    for event in faults:
        answer = build_answer(event, retriever, threshold=threshold)
        errors = CONTRACTS.validate("Answer", answer)
        if errors:
            raise RuntimeError("Answer 契约校验失败：%s" % "; ".join(errors))

        pid = prediction_id(event)
        action = action_for(answer)
        auto = should_auto_workorder(answer) and action["type"] == "workorder"

        psql(
            "insert into diagnosis_answers(event_id,prediction_id,device_id,fault_code,answer_text,citations,confidence,no_evidence,model,trace_id) "
            "values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) on conflict (event_id) do nothing;\n"
            % (
                _q(event["event_id"]),
                _q(pid),
                _q(event["device_id"]),
                _q(event["fault_code"]),
                _q(answer["text"]),
                _json(answer["citations"]),
                _q(answer["confidence"]),
                _q(answer["no_evidence"]),
                _q(MODEL),
                _q(trace_id),
            )
        )
        answers += 1
        if answer["no_evidence"]:
            no_evidence += 1
        confidences.append(answer["confidence"])

        workorder_id = "WO-" + pid
        status = action["status"] if auto else "manual_review"
        psql(
            "insert into workorders(workorder_id,event_id,prediction_id,action_type,status,trace_id) "
            "values (%s,%s,%s,%s,%s,%s) on conflict (workorder_id) do nothing;\n"
            % (_q(workorder_id), _q(event["event_id"]), _q(pid), _q(action["type"]), _q(status), _q(trace_id))
        )
        workorders += 1

        feedback_id = "fb-%s-%s" % (pid, verdict)
        psql(
            "insert into feedback_events(feedback_id,prediction_id,verdict,reason_code,actor,evidence_ref,trace_id) "
            "values (%s,%s,%s,%s,%s,%s,%s) on conflict (feedback_id) do nothing;\n"
            % (
                _q(feedback_id),
                _q(pid),
                _q(verdict),
                _q(reason_code(verdict, answer)),
                _q(actor),
                _q(answer["citations"][0]["locator"] if answer["citations"] else None),
                _q(trace_id),
            )
        )
        feedback += 1

        if len(samples) < 3:
            samples.append(
                {
                    "event_id": event["event_id"],
                    "prediction_id": pid,
                    "fault_code": event["fault_code"],
                    "confidence": answer["confidence"],
                    "no_evidence": answer["no_evidence"],
                    "citation": answer["citations"][0]["locator"] if answer["citations"] else None,
                    "workorder_status": status,
                }
            )

    new_answers = int(pg_query("select count(*) from diagnosis_answers where trace_id='%s'" % trace_id))
    new_workorders = int(pg_query("select count(*) from workorders where trace_id='%s'" % trace_id))
    new_feedback = int(pg_query("select count(*) from feedback_events where trace_id='%s'" % trace_id))
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    ledger(
        trace_id,
        "answer+action+feedback",
        {"answers": answers, "workorders": workorders, "feedback": feedback, "new_answers": new_answers, "no_evidence": no_evidence},
    )

    summary = {
        "trace_id": trace_id,
        "faults": len(faults),
        "answers": answers,
        "workorders": workorders,
        "feedback": feedback,
        "new_answers": new_answers,
        "new_workorders": new_workorders,
        "new_feedback": new_feedback,
        "no_evidence": no_evidence,
        "avg_confidence": avg_conf,
        "model": MODEL,
        "verdict": verdict,
        "samples": samples,
    }
    print("[summary] " + json.dumps(summary, ensure_ascii=False))
    for sample in samples:
        print(
            "[sample] %s %s conf=%.3f no_evidence=%s citation=%s status=%s"
            % (
                sample["event_id"],
                sample["fault_code"],
                sample["confidence"],
                sample["no_evidence"],
                sample["citation"],
                sample["workorder_status"],
            )
        )
    return summary
