package com.example.msdemo.order;

import com.example.msdemo.order.OrderServiceApplication;
import com.example.msdemo.user.UserServiceApplication;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * order-service 聚合链路实测（同 JVM 起真实 user-service + order-service，随机端口）：
 * 聚合成功取回远程用户名 / 订单不存在 40400 / 订单引用的用户不存在 40400（确定答案不降级）/
 * 缺 X-Auth-User 40100（网关内侧信任模型）/ X-Trace-Id 透传到 user-service / 双服务 health。
 * 踩坑：跨模块起 user-service 时 classpath 里 order-service 的 application.properties 会先被读到，
 * 所以 user-service 需要的 jwt.secret 必须用命令行参数传（参照 examples/ex01 README）。
 */
class OrderAggregationTest {

    private static final String JWT_SECRET = "msdemo-test-secret-0123456789abcdef0123456789abcdef";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static ConfigurableApplicationContext userApp;
    private static ConfigurableApplicationContext orderApp;
    private static RestClient orderClient;
    private static RestClient userClientRaw;

    @BeforeAll
    static void startBothServices() {
        userApp = new SpringApplicationBuilder(UserServiceApplication.class)
                .run("--server.port=0", "--jwt.secret=" + JWT_SECRET);
        int userPort = ((WebServerApplicationContext) userApp).getWebServer().getPort();
        orderApp = new SpringApplicationBuilder(OrderServiceApplication.class)
                .run("--server.port=0", "--user-service.base-url=http://localhost:" + userPort);
        int orderPort = ((WebServerApplicationContext) orderApp).getWebServer().getPort();
        orderClient = RestClient.create("http://localhost:" + orderPort);
        userClientRaw = RestClient.create("http://localhost:" + userPort);
    }

    @AfterAll
    static void stopBothServices() {
        orderApp.close();
        userApp.close();
    }

    private record RawResponse(int status, String body, org.springframework.http.HttpHeaders headers) {
    }

    private RawResponse get(String uri, String authUser, String traceId) throws Exception {
        var req = orderClient.get().uri(uri);
        if (authUser != null) {
            req.header("X-Auth-User", authUser);
        }
        if (traceId != null && !traceId.isBlank()) {
            req.header("X-Trace-Id", traceId);
        }
        return req.exchange((r, res) -> new RawResponse(res.getStatusCode().value(),
                res.bodyTo(String.class), res.getHeaders()));
    }

    @Test
    void aggregatesRemoteUsername() throws Exception {
        RawResponse response = get("/api/orders/1001", "alice", null);
        assertThat(response.status()).isEqualTo(200);
        JsonNode body = MAPPER.readTree(response.body());
        assertThat(body.get("code").asInt()).isEqualTo(0);
        JsonNode data = body.get("data");
        assertThat(data.get("orderId").asLong()).isEqualTo(1001L);
        assertThat(data.get("userName").asText()).isEqualTo("alice");   // 用户名来自 user-service 远程响应
        assertThat(data.get("degraded").asBoolean()).isFalse();
    }

    @Test
    void missingOrderReturns40400() throws Exception {
        RawResponse response = get("/api/orders/4041", "alice", null);
        assertThat(response.status()).isEqualTo(404);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40400);
    }

    @Test
    void orderReferencingMissingUserMapsTo40400() throws Exception {
        // 1002 引用 userId=999（user-service 里不存在）：下游 404 是确定答案 → 透传 40400，不降级不重试
        RawResponse response = get("/api/orders/1002", "alice", null);
        assertThat(response.status()).isEqualTo(404);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40400);
    }

    @Test
    void missingAuthHeaderReturns40100() throws Exception {
        RawResponse response = get("/api/orders/1001", null, null);
        assertThat(response.status()).isEqualTo(401);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40100);
    }

    @Test
    void traceIdPropagatesToUserService() throws Exception {
        RawResponse response = get("/api/orders/1001", "alice", "trace-order-0001");
        assertThat(response.status()).isEqualTo(200);
        // 入口（order-service）把 traceId 原样回响应头
        assertThat(response.headers().getFirst("X-Trace-Id")).isEqualTo("trace-order-0001");
        // user-service 实际见到的也是它 —— 拦截器把 MDC 里的 traceId 透传下去了
        JsonNode data = MAPPER.readTree(response.body()).get("data");
        assertThat(data.get("userServiceTraceId").asText()).isEqualTo("trace-order-0001");
    }

    @Test
    void bothServicesExposeHealth() throws Exception {
        JsonNode orderHealth = MAPPER.readTree(
                orderClient.get().uri("/actuator/health").retrieve().body(String.class));
        JsonNode userHealth = MAPPER.readTree(
                userClientRaw.get().uri("/actuator/health").retrieve().body(String.class));
        assertThat(orderHealth.get("status").asText()).isEqualTo("UP");
        assertThat(userHealth.get("status").asText()).isEqualTo("UP");
    }
}
