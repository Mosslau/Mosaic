# CHANGELOG

## [Unreleased]
- 规划：持久化引擎性能档（批量 fsync）、多级 SSTable 与后台 compaction 接入。

## [0.1.0] - 2026-09-04
### Added
- WAL + MemTable 持久化引擎：put/delete/get/range scan，崩溃恢复与残尾修复
- Axum HTTP：/kv/{key} CRUD、/kv?start=&end= range scan、/healthz
- Agent 工具：/tools/call（x-client-id 权限 + 审计）+ /metrics 决策计数
- deny.toml / release-check.sh（形态源自 ph24，注明来源）
