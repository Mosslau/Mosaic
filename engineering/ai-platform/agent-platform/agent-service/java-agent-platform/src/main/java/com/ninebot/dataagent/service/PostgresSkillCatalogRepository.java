package com.ninebot.dataagent.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ninebot.dataagent.domain.ApiModels.SkillDefinition;
import com.ninebot.dataagent.domain.ApiModels.UpsertSkillRequest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** PostgreSQL Skill 仓储；支持内联 Markdown 和不可变 bundle URL 两种来源。 */
@Repository
@ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
public class PostgresSkillCatalogRepository implements SkillCatalogRepository {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public PostgresSkillCatalogRepository(JdbcTemplate jdbc, ObjectMapper mapper) { this.jdbc = jdbc; this.mapper = mapper; }

    @Override
    public SkillDefinition upsert(UpsertSkillRequest request) {
        SkillValidation.validate(request);
        jdbc.update("""
                INSERT INTO skill_definition(id, name, version, description, content, bundle_url, sha256,
                  required_tools_json, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, now())
                ON CONFLICT (id) DO UPDATE SET name=excluded.name, version=excluded.version,
                  description=excluded.description, content=excluded.content, bundle_url=excluded.bundle_url,
                  sha256=excluded.sha256, required_tools_json=excluded.required_tools_json,
                  status=excluded.status, updated_at=now()
                """, request.id(), request.name(), request.version(), request.description(), request.content(),
                request.bundleUrl(), request.sha256(), writeTools(request.requiredTools()),
                request.status() == null ? "DRAFT" : request.status());
        return get(request.id());
    }

    @Override
    public List<SkillDefinition> list() { return jdbc.query("SELECT * FROM skill_definition ORDER BY id", this::map); }

    @Override
    public SkillDefinition get(String id) {
        try { return jdbc.queryForObject("SELECT * FROM skill_definition WHERE id=?", this::map, id); }
        catch (EmptyResultDataAccessException ex) { throw new IllegalArgumentException("skill not found: " + id); }
    }

    @Override
    public SkillDefinition publish(String id) {
        if (jdbc.update("UPDATE skill_definition SET status='PUBLISHED', updated_at=now() WHERE id=?", id) == 0) {
            throw new IllegalArgumentException("skill not found: " + id);
        }
        return get(id);
    }

    private SkillDefinition map(ResultSet rs, int row) throws SQLException {
        return new SkillDefinition(rs.getString("id"), rs.getString("name"), rs.getString("version"),
                rs.getString("description"), rs.getString("content"), rs.getString("bundle_url"),
                rs.getString("sha256"), readTools(rs.getString("required_tools_json")), rs.getString("status"),
                rs.getTimestamp("updated_at").toInstant());
    }

    private String writeTools(List<String> tools) {
        try { return mapper.writeValueAsString(SkillValidation.tools(tools)); }
        catch (JsonProcessingException ex) { throw new IllegalArgumentException("requiredTools is not serializable", ex); }
    }

    private List<String> readTools(String json) {
        try { return json == null ? List.of() : mapper.readerForListOf(String.class).readValue(json); }
        catch (JsonProcessingException ex) { throw new IllegalStateException("invalid required_tools_json", ex); }
    }
}
