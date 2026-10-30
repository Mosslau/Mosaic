package com.ninebot.dataagent.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ninebot.dataagent.domain.ApiModels.AgentDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertAgentRequest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** PostgreSQL Agent 定义仓储，快照以 JSONB 保存并按版本整体替换。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
public class PostgresAgentCatalogRepository implements AgentCatalogRepository {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public PostgresAgentCatalogRepository(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    @Override
    public AgentDefinition upsert(UpsertAgentRequest request) {
        JsonNode snapshot = request.snapshot() == null ? mapper.createObjectNode() : request.snapshot().deepCopy();
        String json = write(snapshot);
        String status = request.status() == null ? "DRAFT" : request.status();
        jdbc.update("""
                INSERT INTO agent_definition(id, name, version, status, snapshot_json, updated_at)
                VALUES (?, ?, ?, ?, ?::jsonb, now())
                ON CONFLICT (id) DO UPDATE SET name=excluded.name, version=excluded.version,
                  status=excluded.status, snapshot_json=excluded.snapshot_json, updated_at=now()
                """, request.id(), request.name(), request.version(), status, json);
        return get(request.id());
    }

    @Override
    public List<AgentDefinition> list() {
        return jdbc.query("SELECT id, name, version, status, snapshot_json, updated_at FROM agent_definition ORDER BY id",
                this::map);
    }

    @Override
    public AgentDefinition get(String id) {
        try {
            return jdbc.queryForObject("SELECT id, name, version, status, snapshot_json, updated_at FROM agent_definition WHERE id=?",
                    this::map, id);
        } catch (EmptyResultDataAccessException ex) {
            throw new IllegalArgumentException("agent not found: " + id);
        }
    }

    @Override
    public AgentDefinition publish(String id) {
        int updated = jdbc.update("UPDATE agent_definition SET status='PUBLISHED', updated_at=now() WHERE id=?", id);
        if (updated == 0) throw new IllegalArgumentException("agent not found: " + id);
        return get(id);
    }

    private AgentDefinition map(ResultSet rs, int row) throws SQLException {
        return new AgentDefinition(rs.getString("id"), rs.getString("name"), rs.getInt("version"),
                rs.getString("status"), readJson(rs.getString("snapshot_json")),
                rs.getTimestamp("updated_at").toInstant());
    }

    private JsonNode readJson(String value) {
        try { return mapper.readTree(value); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("invalid agent snapshot JSON", ex); }
    }

    private String write(JsonNode value) {
        try { return mapper.writeValueAsString(value); }
        catch (JsonProcessingException ex) { throw new IllegalArgumentException("agent snapshot is not serializable", ex); }
    }
}
