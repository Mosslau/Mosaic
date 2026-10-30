package com.ninebot.dataagent.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ninebot.dataagent.config.AgentProperties;
import com.ninebot.dataagent.domain.ApiModels.RunAccepted;
import com.ninebot.dataagent.domain.ApiModels.RunRequest;
import com.ninebot.dataagent.domain.ApiModels.RunView;
import java.nio.charset.StandardCharsets;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/** Java → Python Runtime HTTP client with AK/SK HMAC request signing. */
@Service
public class PythonRuntimeClient {
    private final RestClient client;
    private final AgentProperties properties;
    private final ObjectMapper objectMapper;

    public PythonRuntimeClient(
            RestClient pythonRuntimeClient, AgentProperties properties, ObjectMapper objectMapper) {
        this.client = pythonRuntimeClient;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public RunAccepted submit(RunRequest request) {
        String path = "/internal/runs";
        byte[] body = jsonBytes(request);
        return client.post().uri(path)
                .headers(headers -> applyAuth(headers, "POST", path, body))
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve().body(RunAccepted.class);
    }

    public RunView status(String runId) {
        String path = "/internal/runs/" + runId;
        return client.get().uri(path)
                .headers(headers -> applyAuth(headers, "GET", path, new byte[0]))
                .retrieve().body(RunView.class);
    }

    public void cancel(String runId) {
        String path = "/internal/runs/" + runId + "/cancel";
        client.post().uri(path)
                .headers(headers -> applyAuth(headers, "POST", path, new byte[0]))
                .contentType(MediaType.APPLICATION_JSON)
                .body(new byte[0])
                .retrieve().toBodilessEntity();
    }

    private byte[] jsonBytes(Object value) {
        try {
            return objectMapper.writeValueAsBytes(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Unable to serialize Runtime request", exception);
        }
    }

    private void applyAuth(HttpHeaders headers, String method, String path, byte[] body) {
        String accessKey = properties.getRuntime().getAccessKey();
        String secretKey = properties.getRuntime().getSecretKey();
        if (hasText(accessKey) && hasText(secretKey)) {
            HmacRequestSigner.headers(method, path, "", body, accessKey, secretKey)
                    .forEach(headers::set);
            return;
        }
        // Kept only for local migration. Never configure this in production.
        if (hasText(properties.getRuntime().getInternalToken())) {
            headers.set("X-Internal-Service-Token", properties.getRuntime().getInternalToken());
            return;
        }
        throw new IllegalStateException(
                "Runtime AK/SK are not configured; set AGENT_RUNTIME_ACCESS_KEY and AGENT_RUNTIME_SECRET_KEY");
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
