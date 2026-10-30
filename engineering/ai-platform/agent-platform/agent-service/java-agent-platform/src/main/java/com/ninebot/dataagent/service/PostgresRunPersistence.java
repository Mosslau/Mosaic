package com.ninebot.dataagent.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ninebot.dataagent.domain.ApiModels.RunView;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** PostgreSQL AgentRun 状态仓储；结果 JSON 和错误信息均支持故障恢复后查询。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
public class PostgresRunPersistence implements RunPersistence {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public PostgresRunPersistence(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    @Override
    public void save(RunView run) {
        jdbc.update("""
                INSERT INTO agent_run(run_id, session_id, agent_id, status, result_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?)
                ON CONFLICT (run_id) DO UPDATE SET session_id=excluded.session_id,
                  agent_id=excluded.agent_id, status=excluded.status, result_json=excluded.result_json,
                  error=excluded.error, updated_at=excluded.updated_at
                """, run.runId(), run.sessionId(), run.agentId(), run.status(),
                writeNullable(run.result()), run.error(), run.createdAt(), run.updatedAt());
    }

    @Override
    public RunView get(String runId) {
        try {
            return jdbc.queryForObject("""
                    SELECT run_id, session_id, agent_id, status, result_json, error, created_at, updated_at
                    FROM agent_run WHERE run_id=?
                    """, this::map, runId);
        } catch (EmptyResultDataAccessException ex) {
            return null;
        }
    }

    @Override
    public boolean contains(String runId) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM agent_run WHERE run_id=?", Integer.class, runId);
        return count != null && count > 0;
    }

    private RunView map(ResultSet rs, int row) throws SQLException {
        return new RunView(rs.getString("run_id"), rs.getString("session_id"), rs.getString("agent_id"),
                rs.getString("status"), timestamp(rs, "created_at"), timestamp(rs, "updated_at"),
                readNullable(rs.getString("result_json")), rs.getString("error"));
    }

    private Instant timestamp(ResultSet rs, String column) throws SQLException {
        return rs.getTimestamp(column).toInstant();
    }

    private String writeNullable(JsonNode value) {
        if (value == null) return null;
        try { return mapper.writeValueAsString(value); }
        catch (JsonProcessingException ex) { throw new IllegalArgumentException("run result is not serializable", ex); }
    }

    private JsonNode readNullable(String value) {
        if (value == null) return null;
        try { return mapper.readTree(value); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("invalid run result JSON", ex); }
    }
}
