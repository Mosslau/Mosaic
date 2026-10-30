package com.ninebot.dataagent.service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import org.springframework.stereotype.Service;

/**
 * MCP 数据工具网关的第一版实现。
 *
 * <p>工具注册、用户/租户权限和 SQL 执行目前是开发桩；所有 SQL 工具默认只读并拒绝
 * 多语句。接入真实元数据和数仓时，只替换本 Service 的后端，不改变 MCP 契约。</p>
 */
@Service
public class McpToolService {
    private static final Pattern READ_ONLY = Pattern.compile("(?is)^\\s*(select|with)\\b.*");
    private static final Pattern DANGEROUS = Pattern.compile("(?is)(;|\\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy)\\b)");

    public List<Map<String, Object>> tools() {
        return List.of(
                tool("metadata_search", "查询表、字段和数据域元数据"),
                tool("search_metric_definition", "查询指标定义、单位和口径"),
                tool("sql_validate", "校验只读 SQL"),
                tool("query_readonly", "执行受权限控制的只读查询"),
                tool("search_knowledge", "查询测试知识库内容"),
                // 与架构文档中的生产命名保持兼容，避免 Snapshot 迁移时改动 Agent。
                tool("query_metric_definition", "search_metric_definition 的生产命名"),
                tool("search_metadata", "metadata_search 的生产命名"),
                tool("get_table_schema", "查询表结构的生产命名"),
                tool("validate_readonly_sql", "sql_validate 的生产命名"),
                tool("execute_readonly_sql", "query_readonly 的生产命名"));
    }

    public Object call(String name, Map<String, Object> arguments) {
        String canonicalName = switch (name) {
            case "query_metric_definition" -> "search_metric_definition";
            case "search_metadata", "get_table_schema" -> "metadata_search";
            case "validate_readonly_sql" -> "sql_validate";
            case "execute_readonly_sql" -> "query_readonly";
            default -> name;
        };
        return switch (canonicalName) {
            case "metadata_search" -> Map.of("items", List.of(Map.of(
                    "name", String.valueOf(arguments.getOrDefault("keyword", "vehicle")),
                    "description", "本地 Java MCP Gateway 测试元数据，生产环境接入元数据服务")));
            case "search_metric_definition" -> Map.of("items", List.of(Map.of(
                    "metric", arguments.getOrDefault("metric", "vehicle_count"),
                    "definition", "测试指标定义；生产环境由指标中心提供")));
            case "sql_validate" -> validate(String.valueOf(arguments.getOrDefault("sql", "")));
            case "query_readonly" -> Map.of("columns", List.of(), "rows", List.of(), "total", 0,
                    "message", "Java MCP Gateway 测试实现未连接业务数仓");
            case "search_knowledge" -> Map.of("items", List.of(Map.of(
                    "title", "测试知识库", "content", "这是 Java MCP Gateway 提供的本地测试检索结果")));
            default -> throw new IllegalArgumentException("unknown MCP tool: " + name);
        };
    }

    private Map<String, Object> validate(String sql) {
        boolean allowed = READ_ONLY.matcher(sql).matches() && !DANGEROUS.matcher(sql).find();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("valid", allowed);
        result.put("read_only", allowed);
        result.put("message", allowed ? "SQL 通过本地只读校验" : "仅允许单条 SELECT/WITH 查询");
        return result;
    }

    private Map<String, Object> tool(String name, String description) {
        return Map.of("name", name, "description", description, "inputSchema", Map.of(
                "type", "object", "additionalProperties", true));
    }
}
