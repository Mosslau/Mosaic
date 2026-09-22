package com.example;

import com.example.caller.CallOutcome;
import com.example.caller.ResilientCaller;
import com.example.flakyserver.FlakyServerApplication;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 用真实 HTTP 故障注入服务端实测：重试次数、4xx 不重试、非幂等不重试、超时重试、耗尽降级 */
class RetryFallbackTest {

    private static ConfigurableApplicationContext serverApp;
    private static ResilientCaller caller;
    private static RestClient adminClient;

    @BeforeAll
    static void startServer() {
        serverApp = new SpringApplicationBuilder(FlakyServerApplication.class).run("--server.port=0");
        int port = ((WebServerApplicationContext) serverApp).getWebServer().getPort();
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(500));
        factory.setReadTimeout(Duration.ofMillis(300));   // 慢端点 sleep 900ms，必触发读超时
        RestClient client = RestClient.builder()
                .baseUrl("http://localhost:" + port)
                .requestFactory(factory)
                .build();
        caller = new ResilientCaller(client, 3, 5);
        adminClient = RestClient.create("http://localhost:" + port);
    }

    @AfterAll
    static void stopServer() {
        serverApp.close();
    }

    @BeforeEach
    void resetCounters() {
        adminClient.post().uri("/admin/reset").retrieve().toBodilessEntity();
    }

    private int hitsOf(String key) {
        Map<?, ?> hits = adminClient.get().uri("/admin/hits").retrieve().body(Map.class);
        Object v = hits == null ? null : hits.get(key);
        return v == null ? 0 : ((Number) v).intValue();
    }

    @Test
    void transientFailuresAreRetriedUntilSuccess() {
        CallOutcome outcome = caller.get("/flaky?failBefore=2", "fallback");
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.SUCCESS);
        assertThat(outcome.attempts()).isEqualTo(3);
        assertThat(outcome.body()).contains("ok after 3 attempts");
        assertThat(hitsOf("flaky")).isEqualTo(3);   // 下游真实被打了 3 次
    }

    @Test
    void persistent5xxFallsBackAfterMaxAttempts() {
        CallOutcome outcome = caller.get("/always-error", "degraded-default");
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.FALLBACK);
        assertThat(outcome.attempts()).isEqualTo(3);
        assertThat(outcome.body()).isEqualTo("degraded-default");
        assertThat(outcome.lastError()).contains("500");
        assertThat(hitsOf("always-error")).isEqualTo(3);
    }

    @Test
    void clientError4xxIsNotRetried() {
        CallOutcome outcome = caller.get("/missing", "fallback");
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.CLIENT_ERROR);
        assertThat(outcome.httpStatus()).isEqualTo(404);
        assertThat(outcome.attempts()).isEqualTo(1);   // 4xx 是请求问题，重试无意义
        assertThat(hitsOf("missing")).isEqualTo(1);
    }

    @Test
    void readTimeoutIsRetriedThenFallsBack() {
        CallOutcome outcome = caller.get("/slow?ms=900", "timeout-fallback");
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.FALLBACK);
        assertThat(outcome.attempts()).isEqualTo(3);
        assertThat(hitsOf("slow")).isEqualTo(3);
    }

    @Test
    void nonIdempotentPostIsNotRetried() {
        CallOutcome outcome = caller.post("/flaky-post?failBefore=1", "payload", false, "safe-fallback");
        // 下游第 1 次就 500，但非幂等 → 不重试，直接降级；下游只收到 1 次
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.FALLBACK);
        assertThat(outcome.attempts()).isEqualTo(1);
        assertThat(hitsOf("flaky-post")).isEqualTo(1);
    }

    @Test
    void idempotentPostIsRetriedUntilSuccess() {
        CallOutcome outcome = caller.post("/flaky-post?failBefore=2", "payload", true, "safe-fallback");
        assertThat(outcome.kind()).isEqualTo(CallOutcome.Kind.SUCCESS);
        assertThat(outcome.attempts()).isEqualTo(3);
        assertThat(hitsOf("flaky-post")).isEqualTo(3);
    }
}
