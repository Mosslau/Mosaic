-- Data Agent Java 控制面第一版数据库结构。
-- 该脚本由 agent.persistence.mode=postgres 时自动执行，所有 DDL 均幂等。

CREATE TABLE IF NOT EXISTS agent_definition (
    id              VARCHAR(160) PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    version         INTEGER NOT NULL,
    status          VARCHAR(32) NOT NULL,
    snapshot_json   JSONB NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skill_definition (
    id                  VARCHAR(160) PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    version             VARCHAR(80) NOT NULL,
    description         TEXT,
    content             TEXT,
    bundle_url          TEXT,
    sha256              VARCHAR(128),
    required_tools_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status              VARCHAR(32) NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT skill_source_check CHECK ((content IS NOT NULL) <> (bundle_url IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS agent_run (
    run_id              VARCHAR(160) PRIMARY KEY,
    session_id          VARCHAR(160),
    agent_id            VARCHAR(160) NOT NULL,
    tenant_id           VARCHAR(160),
    user_id             VARCHAR(160),
    status              VARCHAR(40) NOT NULL,
    message             TEXT,
    stream              BOOLEAN NOT NULL DEFAULT TRUE,
    agent_snapshot_json JSONB,
    result_json         JSONB,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_run_session_created ON agent_run(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_run_tenant_created ON agent_run(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_event (
    id          BIGSERIAL PRIMARY KEY,
    run_id      VARCHAR(160),
    tenant_id   VARCHAR(160),
    event_type  VARCHAR(100) NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_event_run_created ON audit_event(run_id, created_at);
