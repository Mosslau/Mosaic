-- Java 控制平面第一版数据库结构。
-- 生产环境可由 Flyway/Liquibase 执行；当前代码在 postgres 模式下幂等执行这些 DDL。

create table if not exists agent_definition (
    id varchar(128) primary key,
    name varchar(255) not null,
    version integer not null,
    status varchar(32) not null,
    snapshot_json text not null,
    updated_at timestamptz not null
);

create table if not exists skill_definition (
    id varchar(128) primary key,
    name varchar(255) not null,
    version varchar(128) not null,
    description text,
    content text not null,
    required_tools_json text not null,
    status varchar(32) not null,
    updated_at timestamptz not null
);

create table if not exists agent_run (
    run_id varchar(128) primary key,
    session_id varchar(128),
    agent_id varchar(128) not null,
    tenant_id varchar(128),
    user_id varchar(128),
    status varchar(32) not null,
    stream boolean not null,
    message text not null,
    agent_snapshot_json text,
    result_json text,
    error text,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create table if not exists audit_event (
    id bigserial primary key,
    run_id varchar(128),
    tenant_id varchar(128),
    event_type varchar(128) not null,
    payload_json text not null,
    created_at timestamptz not null
);

create index if not exists idx_agent_run_session on agent_run (tenant_id, session_id, created_at);
create index if not exists idx_agent_run_status on agent_run (status, updated_at);
create index if not exists idx_audit_run on audit_event (run_id, created_at);
