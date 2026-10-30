package com.ninebot.dataagent.api;

import com.ninebot.dataagent.domain.ApiModels.McpRequest;
import com.ninebot.dataagent.domain.ApiModels.McpResponse;
import com.ninebot.dataagent.service.McpToolService;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

/**
 * 最小 MCP JSON-RPC Gateway。
 *
 * <p>同时暴露 /mcp 和 /internal/mcp，方便 Python Snapshot 在本地和部署环境使用同一 URL
 * 结构。生产接入时应补齐 MCP Streamable HTTP 的会话/协议版本协商。</p>
 */
@RestController
public class McpGatewayController {
    private final McpToolService tools;

    public McpGatewayController(McpToolService tools) { this.tools = tools; }

    @PostMapping(value = {"/mcp", "/internal/mcp"}, consumes = "application/json", produces = "application/json")
    public McpResponse handle(@RequestBody McpRequest request) {
        if (request.method() == null) return McpResponse.failure(request.id(), -32600, "method is required");
        try {
            return switch (request.method()) {
                case "initialize" -> McpResponse.success(request.id(), Map.of(
                        "protocolVersion", "2025-03-26",
                        "capabilities", Map.of("tools", Map.of()),
                        "serverInfo", Map.of("name", "data-agent-java-mcp-gateway", "version", "0.1.0")));
                case "notifications/initialized" -> McpResponse.success(request.id(), Map.of());
                case "tools/list" -> McpResponse.success(request.id(), Map.of("tools", tools.tools()));
                case "tools/call" -> call(request);
                default -> McpResponse.failure(request.id(), -32601, "method not found: " + request.method());
            };
        } catch (IllegalArgumentException ex) {
            return McpResponse.failure(request.id(), -32602, ex.getMessage());
        }
    }

    private McpResponse call(McpRequest request) {
        Map<String, Object> params = request.params() == null ? Map.of() : request.params();
        String name = String.valueOf(params.getOrDefault("name", ""));
        @SuppressWarnings("unchecked")
        Map<String, Object> arguments = params.get("arguments") instanceof Map<?, ?> map
                ? (Map<String, Object>) map : Map.of();
        Object result = tools.call(name, arguments);
        return McpResponse.success(request.id(), Map.of(
                "content", java.util.List.of(Map.of("type", "text", "text", result.toString())),
                "structuredContent", result,
                "isError", false));
    }
}
