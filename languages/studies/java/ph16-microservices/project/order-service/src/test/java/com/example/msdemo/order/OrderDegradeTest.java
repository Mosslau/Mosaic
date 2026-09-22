package com.example.msdemo.order;

import com.example.msdemo.order.OrderServiceApplication;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.net.ServerSocket;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 降级语义实测：order-service 起真实服务，但 user-service.base-url 指向一个无人监听的端口
 * （连接被拒 → ResourceAccessException → DownstreamTimeoutException）→ 订单详情降级：
 * HTTP 仍 200、code 0、degraded=true、用户名占位文案、userServiceTraceId 为空；订单本体不丢。
 * 与 exercises/sol-02 的 degraded=true 降级路径一致（主文档 3.3「有损服务」）。
 */
class OrderDegradeTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static ConfigurableApplicationContext orderApp;
    private static RestClient orderClient;

    @BeforeAll
    static void startOrderServiceWithDeadUserService() throws IOException {
        int deadPort;
        try (ServerSocket socket = new ServerSocket(0)) {   // 先占一个端口再释放 → 该端口无人监听
            deadPort = socket.getLocalPort();
        }
        orderApp = new SpringApplicationBuilder(OrderServiceApplication.class)
                .run("--server.port=0", "--user-service.base-url=http://127.0.0.1:" + deadPort);
        int orderPort = ((WebServerApplicationContext) orderApp).getWebServer().getPort();
        orderClient = RestClient.create("http://localhost:" + orderPort);
    }

    @AfterAll
    static void stopOrderService() {
        orderApp.close();
    }

    @Test
    void orderDetailDegradesWhenUserServiceDown() throws Exception {
        var snapshot = orderClient.get().uri("/api/orders/1001")
                .header("X-Auth-User", "alice")
                .exchange((req, res) -> new Object[]{res.getStatusCode().value(), res.bodyTo(String.class)});
        assertThat(snapshot[0]).isEqualTo(200);   // 降级不是错误：HTTP 仍 200
        JsonNode body = MAPPER.readTree((String) snapshot[1]);
        assertThat(body.get("code").asInt()).isEqualTo(0);
        JsonNode data = body.get("data");
        assertThat(data.get("degraded").asBoolean()).isTrue();
        assertThat(data.get("userName").asText()).contains("降级");   // 占位文案
        assertThat(data.get("userServiceTraceId").isNull()).isTrue(); // 没调通就没有下游 trace
    }

    @Test
    void orderNotPresentStill404WhenUserServiceDown() throws Exception {
        // 订单数据是 order-service 自己的：下游不可用不影响本地 404（数据跟着服务走，故障隔离）
        var status = orderClient.get().uri("/api/orders/4041")
                .header("X-Auth-User", "alice")
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(404);
    }
}
