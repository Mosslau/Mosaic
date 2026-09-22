package com.example.caller;

import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * 带「超时 + 重试 + 降级」三件套语义的远程调用器（Resilience4j @Retry/@Fallback 的同构手写版，
 * Resilience4j jar 不在离线缓存，机制见主文档 3.3）：
 * - 4xx：请求本身有问题，重试无意义 → 立即失败
 * - 5xx / 超时（ResourceAccessException）：瞬时故障 → 重试，但**只有幂等请求才敢重试**
 * - 重试耗尽 → 降级（fallback），绝不把异常直接抛给终端用户
 */
public class ResilientCaller {

    private final RestClient restClient;
    private final int maxAttempts;
    private final long backoffMs;

    public ResilientCaller(RestClient restClient, int maxAttempts, long backoffMs) {
        this.restClient = restClient;
        this.maxAttempts = maxAttempts;
        this.backoffMs = backoffMs;
    }

    /** GET 天然幂等 */
    public CallOutcome get(String uri, String fallbackBody) {
        return execute("GET", uri, null, true, fallbackBody);
    }

    /** POST 是否重试由调用方按幂等性显式声明（有幂等键才敢 true） */
    public CallOutcome post(String uri, Object body, boolean idempotent, String fallbackBody) {
        return execute("POST", uri, body, idempotent, fallbackBody);
    }

    private CallOutcome execute(String method, String uri, Object body, boolean idempotent, String fallbackBody) {
        int attempt = 0;
        while (true) {
            attempt++;
            try {
                int currentAttempt = attempt;
                var spec = method.equals("POST")
                        ? restClient.post().uri(uri).body(body == null ? "" : body)
                        : restClient.get().uri(uri);
                return spec.exchange((req, res) -> {
                    int status = res.getStatusCode().value();
                    String responseBody = res.bodyTo(String.class);
                    if (status >= 500) {
                        throw new Downstream5xxException(status);
                    }
                    if (status >= 400) {
                        return CallOutcome.clientError(status, responseBody, currentAttempt);
                    }
                    return CallOutcome.success(status, responseBody, currentAttempt);
                });
            } catch (Downstream5xxException | ResourceAccessException e) {
                // 非幂等请求不敢重试（下游可能已处理只是响应丢了）；幂等请求重试到 maxAttempts 为止
                if (!idempotent || attempt >= maxAttempts) {
                    return CallOutcome.fallback(fallbackBody, attempt, e.getMessage());
                }
                sleepQuietly(backoffMs);
            }
        }
    }

    private static void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
