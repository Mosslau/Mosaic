package com.ninebot.dataagent.service;

import com.ninebot.dataagent.config.AgentProperties;
import com.ninebot.dataagent.domain.ApiModels.SandboxCommandRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxCommandResponse;
import com.ninebot.dataagent.domain.ApiModels.SandboxCreateRequest;
import com.ninebot.dataagent.domain.ApiModels.SandboxFileInfo;
import com.ninebot.dataagent.domain.ApiModels.SandboxInfo;
import com.ninebot.dataagent.domain.ApiModels.SandboxReadFileResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

/**
 * Sandbox Gateway 控制面和文件操作实现。
 *
 * <p>默认只做契约和安全校验，不执行宿主机命令。命令执行显式由
 * JAVA_SANDBOX_COMMAND_EXECUTION_ENABLED=false 保护，等接入 Docker/Kubernetes 后再打开。</p>
 */
@Service
public class SandboxGatewayService {
    private final AgentProperties properties;
    private final Map<String, SandboxState> sandboxes = new ConcurrentHashMap<>();

    public SandboxGatewayService(AgentProperties properties) { this.properties = properties; }

    public SandboxInfo create(SandboxCreateRequest request) {
        if (!properties.getGateway().getSandbox().isEnabled()) {
            throw new IllegalStateException("Java Sandbox Gateway is disabled; use Python docker provider for local development");
        }
        String id = "sandbox-" + UUID.randomUUID().toString().replace("-", "");
        SandboxState state = new SandboxState(id, request.allowCommands() == null ? List.of() : request.allowCommands());
        sandboxes.put(id, state);
        return state.info();
    }

    public SandboxFileInfo write(String id, String path, String base64) {
        SandboxState state = state(id);
        String safePath = safePath(path);
        byte[] content = Base64.getDecoder().decode(base64);
        state.files.put(safePath, content);
        return new SandboxFileInfo(safePath, content.length, sha256(content));
    }

    public SandboxReadFileResponse read(String id, String path) {
        byte[] content = state(id).files.get(safePath(path));
        if (content == null) throw new IllegalArgumentException("sandbox file not found");
        return new SandboxReadFileResponse(safePath(path), Base64.getEncoder().encodeToString(content), content.length, sha256(content));
    }

    public SandboxCommandResponse run(String id, SandboxCommandRequest request) {
        SandboxState state = state(id);
        if (!state.allowCommands.contains(request.executable())) throw new IllegalArgumentException("command is not allowed");
        if (!properties.getGateway().getSandbox().isCommandExecutionEnabled()) {
            throw new IllegalStateException("SANDBOX_COMMAND_EXECUTION_DISABLED");
        }
        throw new UnsupportedOperationException("Docker/Kubernetes execution backend is not configured");
    }

    public void delete(String id) { sandboxes.remove(id); }

    private SandboxState state(String id) {
        SandboxState value = sandboxes.get(id);
        if (value == null) throw new IllegalArgumentException("sandbox not found: " + id);
        return value;
    }

    private String safePath(String path) {
        if (path == null || (!path.startsWith("/workspace/") && !path.equals("/workspace")) || path.contains("..")) {
            throw new IllegalArgumentException("SANDBOX_FILE_NOT_ALLOWED");
        }
        return path;
    }

    private String sha256(byte[] content) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(content);
            return java.util.HexFormat.of().formatHex(hash);
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }

    private static final class SandboxState {
        private final String id;
        private final List<String> allowCommands;
        private final Map<String, byte[]> files = new ConcurrentHashMap<>();
        private SandboxState(String id, List<String> allowCommands) { this.id = id; this.allowCommands = allowCommands; }
        private SandboxInfo info() { return new SandboxInfo(id, "READY", "/workspace", null); }
    }
}
