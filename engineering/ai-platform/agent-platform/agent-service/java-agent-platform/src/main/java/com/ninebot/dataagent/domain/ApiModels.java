package com.ninebot.dataagent.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/** Java 控制平面与 Python Runtime 共用的 HTTP 契约模型。 */
public final class ApiModels {
    private ApiModels() {}

    public record AgentDefinition(
            String id,
            String name,
            int version,
            String status,
            JsonNode snapshot,
            Instant updatedAt) {}

    public record UpsertAgentRequest(
            @NotBlank String id,
            @NotBlank String name,
            int version,
            String status,
            JsonNode snapshot) {}

    public record PublishAgentRequest(String reason) {}

    public record SkillDefinition(
            String id,
            String name,
            String version,
            String description,
            String content,
            String bundleUrl,
            String sha256,
            List<String> requiredTools,
            String status,
            Instant updatedAt) {}

    public record UpsertSkillRequest(
            @NotBlank String id,
            @NotBlank String name,
            @NotBlank String version,
            String description,
            String content,
            String bundleUrl,
            String sha256,
            List<String> requiredTools,
            String status) {}

    public record PublishSkillRequest(String reason) {}

    public record RunRequest(
            String runId,
            String sessionId,
            boolean stream,
            @NotBlank String message,
            @NotBlank String agentId,
            JsonNode agent,
            UserContext userContext) {}

    public record UserContext(String userId, String tenantId, List<String> roles, List<String> scopes) {}

    public record RunAccepted(String runId, String status) {}

    public record RunView(
            String runId,
            String sessionId,
            String agentId,
            String status,
            Instant createdAt,
            Instant updatedAt,
            JsonNode result,
            String error) {}

    public record McpRequest(String jsonrpc, Object id, String method, Map<String, Object> params) {}

    public record McpResponse(String jsonrpc, Object id, Object result, McpError error) {
        public static McpResponse success(Object id, Object result) {
            return new McpResponse("2.0", id, result, null);
        }
        public static McpResponse failure(Object id, int code, String message) {
            return new McpResponse("2.0", id, null, new McpError(code, message, null));
        }
    }

    public record McpError(int code, String message, Object data) {}

    public record SandboxCreateRequest(
            String runId,
            String tenantId,
            String sessionId,
            String image,
            String imageDigest,
            Integer timeoutSeconds,
            Integer memoryLimitMb,
            Double cpuLimit,
            String networkMode,
            List<String> allowCommands) {}

    public record SandboxInfo(String sandboxId, String status, String workspacePath, Instant expiresAt) {}

    public record SandboxWriteFileRequest(String path, String contentBase64, String encoding) {}
    public record SandboxReadFileRequest(String path) {}
    public record SandboxCommandRequest(String executable, List<String> args, Integer timeoutSeconds, Integer maxOutputBytes) {}
    public record SandboxArtifactRequest(String path, String name) {}
    public record SandboxFileInfo(String path, long sizeBytes, String sha256) {}
    public record SandboxReadFileResponse(String path, String contentBase64, long sizeBytes, String sha256) {}
    public record SandboxCommandResponse(String status, Integer exitCode, String stdout, String stderr, boolean truncated, long durationMs) {}
}
