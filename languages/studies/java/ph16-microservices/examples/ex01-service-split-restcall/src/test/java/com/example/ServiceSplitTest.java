package com.example;

import com.example.common.TraceIdFilter;
import com.example.orderservice.OrderDetail;
import com.example.orderservice.OrderServiceApplication;
import com.example.userservice.UserServiceApplication;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 同 JVM 起两个真实 HTTP 服务（随机端口），验证拆分后的远程调用语义：
 * 聚合成功 / 下游 404 映射 / 超时快速失败 / TraceId 透传与生成 / 双服务健康端点。
 */
class ServiceSplitTest {

    private static ConfigurableApplicationContext userApp;
    private static ConfigurableApplicationContext orderApp;
    private static RestClient orderClient;
    private static RestClient userClientRaw;

    /** 一次调用的完整快照（在 exchange 回调内读取，避免响应关闭后再读 body） */
    private record RawResponse(int status, String body, org.springframework.http.HttpHeaders headers) {
    }

    @BeforeAll
    static void startBothServices() {
        // 注意：必须用命令行参数传端口/地址——classpath 的 application.properties
        // 优先级高于 SpringApplicationBuilder 的默认属性，会盖住测试注入的随机端口
        userApp = new SpringApplicationBuilder(UserServiceApplication.class)
                .run("--server.port=0");
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

    @Test
    void orderDetailComposesUserAcrossServices() {
        OrderDetail detail = orderClient.get().uri("/orders/1001").retrieve().body(OrderDetail.class);
        assertThat(detail).isNotNull();
        assertThat(detail.orderId()).isEqualTo(1001L);
        assertThat(detail.item()).isEqualTo("电动补能电器");
        assertThat(detail.userName()).isEqualTo("张三");   // 用户名来自 user-service 的远程响应
    }

    @Test
    void downstreamUserNotFoundMapsTo404() throws java.io.IOException {
        RawResponse response = orderClient.get().uri("/orders/1002")
                .exchange((req, res) -> new RawResponse(res.getStatusCode().value(), res.bodyTo(String.class), res.getHeaders()));
        assertThat(response.status()).isEqualTo(HttpStatus.NOT_FOUND.value());
        assertThat(response.body()).contains("40400");
    }

    @Test
    void slowDownstreamFailsFastWithTimeout() throws java.io.IOException {
        long start = System.nanoTime();
        RawResponse response = orderClient.get().uri("/orders/1003")
                .exchange((req, res) -> new RawResponse(res.getStatusCode().value(), res.bodyTo(String.class), res.getHeaders()));
        long elapsedMs = (System.nanoTime() - start) / 1_000_000;
        assertThat(response.status()).isEqualTo(HttpStatus.GATEWAY_TIMEOUT.value());
        assertThat(response.body()).contains("50400");
        // 读超时 800ms：远小于慢用户的 1500ms，证明调用方没有被拖死
        assertThat(elapsedMs).isLessThan(1400L);
    }

    @Test
    void traceIdPropagatesDownstream() throws java.io.IOException {
        RawResponse response = orderClient.get().uri("/orders/1001")
                .header(TraceIdFilter.HEADER, "trace-test-0001")
                .exchange((req, res) -> new RawResponse(res.getStatusCode().value(), res.bodyTo(String.class), res.getHeaders()));
        assertThat(response.status()).isEqualTo(HttpStatus.OK.value());
        // 入口服务把 traceId 原样回到响应头
        assertThat(response.headers().getFirst(TraceIdFilter.HEADER)).isEqualTo("trace-test-0001");
        // user-service 实际见到的也是它 —— 透传成功
        OrderDetail detail = new com.fasterxml.jackson.databind.ObjectMapper()
                .readValue(response.body(), OrderDetail.class);
        assertThat(detail.userServiceTraceId()).isEqualTo("trace-test-0001");
    }

    @Test
    void missingTraceIdIsGeneratedAtEntry() throws java.io.IOException {
        RawResponse response = orderClient.get().uri("/orders/1001")
                .exchange((req, res) -> new RawResponse(res.getStatusCode().value(), res.bodyTo(String.class), res.getHeaders()));
        String echoed = response.headers().getFirst(TraceIdFilter.HEADER);
        assertThat(echoed).isNotBlank();
        OrderDetail detail = new com.fasterxml.jackson.databind.ObjectMapper()
                .readValue(response.body(), OrderDetail.class);
        assertThat(detail.userServiceTraceId()).isEqualTo(echoed);   // 生成的 id 同样透传到下游
    }

    @Test
    void bothServicesExposeHealthEndpoint() {
        Map<?, ?> userHealth = userClientRaw.get().uri("/actuator/health").retrieve().body(Map.class);
        Map<?, ?> orderHealth = orderClient.get().uri("/actuator/health").retrieve().body(Map.class);
        assertThat(userHealth).isNotNull();
        assertThat(orderHealth).isNotNull();
        assertThat(userHealth.get("status")).isEqualTo("UP");
        assertThat(orderHealth.get("status")).isEqualTo("UP");
    }
}
