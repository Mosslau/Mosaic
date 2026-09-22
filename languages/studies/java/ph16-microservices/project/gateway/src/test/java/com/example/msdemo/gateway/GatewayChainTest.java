package com.example.msdemo.gateway;

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
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 网关验签链路实测（同 JVM 起真实 user-service + order-service + gateway 三个进程，随机端口）：
 * client → gateway(验签) → order-service(聚合) → user-service(取用户名)，外加共享 JWT 密钥、
 * X-Trace-Id 全链路透传、路由按路径分发、下游错误码透传。
 * 踩坑：跨模块起 user-service/order-service 时 classpath 的 application.properties 会被
 * gateway 的盖住（ex01 README 踩坑），所以各自需要的配置一律用命令行参数传（优先级最高）。
 */
class GatewayChainTest {

    private static final String JWT_SECRET = "msdemo-test-secret-0123456789abcdef0123456789abcdef";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static ConfigurableApplicationContext userApp;
    private static ConfigurableApplicationContext orderApp;
    private static ConfigurableApplicationContext gatewayApp;
    private static RestClient gatewayClient;
    private static RestClient userClientRaw;
    private static RestClient orderClientRaw;

    @BeforeAll
    static void startThreeServices() {
        userApp = new SpringApplicationBuilder(UserServiceApplication.class)
                .run("--server.port=0", "--jwt.secret=" + JWT_SECRET);
        int userPort = ((WebServerApplicationContext) userApp).getWebServer().getPort();
        orderApp = new SpringApplicationBuilder(OrderServiceApplication.class)
                .run("--server.port=0", "--user-service.base-url=http://localhost:" + userPort);
        int orderPort = ((WebServerApplicationContext) orderApp).getWebServer().getPort();
        gatewayApp = new SpringApplicationBuilder(GatewayApplication.class)
                .run("--server.port=0",
                        "--jwt.secret=" + JWT_SECRET,
                        "--downstream.user-service.base-url=http://localhost:" + userPort,
                        "--downstream.order-service.base-url=http://localhost:" + orderPort);
        int gatewayPort = ((WebServerApplicationContext) gatewayApp).getWebServer().getPort();
        gatewayClient = RestClient.create("http://localhost:" + gatewayPort);
        userClientRaw = RestClient.create("http://localhost:" + userPort);
        orderClientRaw = RestClient.create("http://localhost:" + orderPort);
    }

    @AfterAll
    static void stopThreeServices() {
        gatewayApp.close();
        orderApp.close();
        userApp.close();
    }

    private record RawResponse(int status, String body, org.springframework.http.HttpHeaders headers) {
    }

    private RawResponse send(org.springframework.http.HttpMethod method, String path, String token,
                             String traceId, Object jsonBody) throws Exception {
        var spec = gatewayClient.method(method).uri(path)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .header("Authorization", token == null ? "" : "Bearer " + token)
                .header("X-Trace-Id", traceId == null ? "" : traceId);
        if (jsonBody != null) {
            spec.body(jsonBody);
        }
        return spec.exchange((req, res) -> new RawResponse(res.getStatusCode().value(),
                res.bodyTo(String.class), res.getHeaders()));
    }

    private String login(String username, String password) throws Exception {
        RawResponse response = send(org.springframework.http.HttpMethod.POST, "/api/auth/login",
                null, null, Map.of("username", username, "password", password));
        assertThat(response.status()).isEqualTo(200);
        JsonNode body = MAPPER.readTree(response.body());
        return body.get("data").get("token").asText();
    }

    @Test
    void loginThroughGatewayIssuesJwt() throws Exception {
        String token = login("alice", "alice123");
        assertThat(token.split("\\.")).hasSize(3);   // header.payload.signature
    }

    @Test
    void wrongPasswordThroughGatewayReturns40101() throws Exception {
        // POST + 下游 401：走 JdkClientHttpRequestFactory 不会抛 HttpRetryException，40101 原样透传
        RawResponse response = send(org.springframework.http.HttpMethod.POST, "/api/auth/login",
                null, null, Map.of("username", "alice", "password", "wrong"));
        assertThat(response.status()).isEqualTo(401);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40101);
    }

    @Test
    void requestWithoutTokenRejected40100() throws Exception {
        RawResponse response = send(org.springframework.http.HttpMethod.GET, "/api/orders/1001",
                null, null, null);
        assertThat(response.status()).isEqualTo(401);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40100);
    }

    @Test
    void tamperedTokenRejected40100() throws Exception {
        String token = login("alice", "alice123") + "tampered";
        RawResponse response = send(org.springframework.http.HttpMethod.GET, "/api/orders/1001",
                token, null, null);
        assertThat(response.status()).isEqualTo(401);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40100);
    }

    @Test
    void validTokenAggregatesOrderAcrossServices() throws Exception {
        String token = login("alice", "alice123");
        RawResponse response = send(org.springframework.http.HttpMethod.GET, "/api/orders/1001",
                token, null, null);
        assertThat(response.status()).isEqualTo(200);
        JsonNode data = MAPPER.readTree(response.body()).get("data");
        assertThat(data.get("orderId").asLong()).isEqualTo(1001L);
        // 链路：gateway 验签 → order-service 聚合 → user-service 返回 alice 的用户名
        assertThat(data.get("userName").asText()).isEqualTo("alice");
        assertThat(data.get("degraded").asBoolean()).isFalse();
    }

    @Test
    void orderNotFoundPassesThroughGateway() throws Exception {
        String token = login("alice", "alice123");
        RawResponse response = send(org.springframework.http.HttpMethod.GET, "/api/orders/4041",
                token, null, null);
        assertThat(response.status()).isEqualTo(404);
        assertThat(MAPPER.readTree(response.body()).get("code").asInt()).isEqualTo(40400);
    }

    @Test
    void traceIdSpansGatewayToUserService() throws Exception {
        String token = login("alice", "alice123");
        RawResponse response = send(org.springframework.http.HttpMethod.GET, "/api/orders/1001",
                token, "trace-gw-0001", null);
        assertThat(response.status()).isEqualTo(200);
        // gateway 入口把 traceId 原样回响应头
        assertThat(response.headers().getFirst("X-Trace-Id")).isEqualTo("trace-gw-0001");
        // 全链路透传成功：user-service 实际见到的也是它（order-service 聚合结果里回显）
        JsonNode data = MAPPER.readTree(response.body()).get("data");
        assertThat(data.get("userServiceTraceId").asText()).isEqualTo("trace-gw-0001");
    }

    @Test
    void roleHeaderInjectedForAdminOnlyEndpoints() throws Exception {
        // alice 是 USER：经网关调用户列表（仅 ADMIN）→ 403 code 40300（X-Auth-Role 注入生效）
        String aliceToken = login("alice", "alice123");
        RawResponse forbidden = send(org.springframework.http.HttpMethod.GET, "/api/users",
                aliceToken, null, null);
        assertThat(forbidden.status()).isEqualTo(403);
        assertThat(MAPPER.readTree(forbidden.body()).get("code").asInt()).isEqualTo(40300);

        // admin 是 ADMIN：同一端点经网关 → 200 code 0
        String adminToken = login("admin", "admin123");
        RawResponse ok = send(org.springframework.http.HttpMethod.GET, "/api/users",
                adminToken, null, null);
        assertThat(ok.status()).isEqualTo(200);
        assertThat(MAPPER.readTree(ok.body()).get("code").asInt()).isEqualTo(0);
    }

    @Test
    void allThreeServicesExposeHealth() throws Exception {
        for (RestClient client : new RestClient[]{userClientRaw, orderClientRaw, gatewayClient}) {
            String health = client.get().uri("/actuator/health").retrieve().body(String.class);
            assertThat(MAPPER.readTree(health).get("status").asText()).isEqualTo("UP");
        }
    }
}
