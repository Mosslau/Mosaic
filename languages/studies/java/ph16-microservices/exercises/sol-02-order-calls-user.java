// exercises/sol-02-order-calls-user.java —— 练习 2 参考实现：订单服务远程调用用户服务（超时/重试/降级）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0（starter-web/test 离线缓存内）
// 验证状态：已验证（本机离线 mvn -o -Dmaven.repo.local=/tmp/m2clone test，BUILD SUCCESS）
// 实测结果：Tests run: 4, Failures: 0, Errors: 0
//   （composesUserNameAcrossServices：聚合成功 / transientFailureIsRetriedOnce：下游首次 500，
//     重试第 2 次成功，/admin/hits 实测 hits=2 / slowDownstreamDegradesGracefully：慢用户 1500ms
//     触发读超时 500ms，重试 1 次仍超时 → degraded=true 降级展示 / missingUserMapsTo404WithoutRetry）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex01-service-split-restcall/pom.xml，
//   artifactId 改 sol02-order-calls-user；两个 Application 分别跑 18322/18323）+ 下列文件。
//   验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 教学点：roadmap 必会概念「远程调用必须有超时和降级」「重试需要幂等」——超时是底线（裸调用会
//   拖死线程池），GET 幂等才敢重试，重试耗尽必须降级而不是把异常甩给用户。

// =============================================================================
// src/main/java/com/example/ordersvc/orderapp/OrderApp.java
// =============================================================================

package com.example.ordersvc.orderapp;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 练习 2 的订单服务（默认端口 18323）：调用用户服务并处理失败 */
@SpringBootApplication
public class OrderApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(OrderApp.class)
                .properties("server.port=18323")
                .run(args);
    }
}

// =============================================================================
// src/main/java/com/example/ordersvc/orderapp/OrderController.java
// =============================================================================

package com.example.ordersvc.orderapp;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

/** 订单聚合端点：本地订单 + 远程用户名；用户服务不可用时降级展示 */
@RestController
public class OrderController {

    private record Order(long orderId, long userId, String item) {
    }

    private static final Map<Long, Order> ORDERS = Map.of(
            1001L, new Order(1001L, 1L, "充电器"),
            1002L, new Order(1002L, 9L, "查无此人的订单"),
            1003L, new Order(1003L, 99L, "慢用户的订单"),
            1004L, new Order(1004L, 7L, "抖动用户的订单"));

    private final ResilientUserClient userClient;

    public OrderController(ResilientUserClient userClient) {
        this.userClient = userClient;
    }

    @GetMapping("/orders/{id}")
    public ResponseEntity<?> detail(@PathVariable long id) {
        Order order = ORDERS.get(id);
        if (order == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("code", 40400, "message", "订单不存在 id=" + id));
        }
        Map<String, Object> user = userClient.findUser(order.userId());
        if (user == null) {
            return ResponseEntity.ok(new OrderDetail(order.orderId(), order.item(),
                    "（用户服务暂不可用，降级展示）", true));
        }
        return ResponseEntity.ok(new OrderDetail(order.orderId(), order.item(),
                String.valueOf(user.get("name")), false));
    }

    @RestControllerAdvice
    static class ErrorHandler {

        @ExceptionHandler(ResilientUserClient.UserMissingException.class)
        ResponseEntity<Map<String, Object>> missing(ResilientUserClient.UserMissingException ex) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("code", 40400, "message", ex.getMessage()));
        }
    }
}

// =============================================================================
// src/main/java/com/example/ordersvc/orderapp/OrderDetail.java
// =============================================================================

package com.example.ordersvc.orderapp;

/** 订单聚合视图：degraded=true 表示用户名是降级占位（用户服务没调通） */
public record OrderDetail(long orderId, String item, String userName, boolean degraded) {
}

// =============================================================================
// src/main/java/com/example/ordersvc/orderapp/ResilientUserClient.java
// =============================================================================

package com.example.ordersvc.orderapp;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

/**
 * 带超时 + 重试（幂等 GET 一次）+ 降级的用户服务客户端。
 * 重试只针对瞬时故障（5xx/超时）；降级返回 null 由调用方决定降级文案。
 */
@Component
public class ResilientUserClient {

    private final RestClient restClient;

    public ResilientUserClient(@Value("${user-service.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(300));
        factory.setReadTimeout(Duration.ofMillis(500));
        this.restClient = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }

    /** 查用户；返回 null 表示下游不可用（调用方降级）；用户不存在抛 UserMissingException */
    public Map<String, Object> findUser(long id) {
        String uri = id == 7L ? "/flaky-user" : "/users/" + id;
        RuntimeException lastError = null;
        for (int attempt = 1; attempt <= 2; attempt++) {   // 最多 2 次：1 次原始 + 1 次重试
            try {
                return restClient.get().uri(uri).exchange((req, res) -> {
                    if (res.getStatusCode().value() == 404) {
                        throw new UserMissingException(id);
                    }
                    if (res.getStatusCode().isError()) {
                        throw new TransientDownstreamException(res.getStatusCode().value());
                    }
                    return res.bodyTo(new ParameterizedTypeReference<Map<String, Object>>() {
                    });
                });
            } catch (TransientDownstreamException | ResourceAccessException e) {
                lastError = e;   // 瞬时故障：重试一次
            }
        }
        return null;   // 重试耗尽 → 降级（null 语义：调用方决定兜底展示）
    }

    /** 下游明确说「不存在」（4xx 不重试） */
    public static class UserMissingException extends RuntimeException {
        public UserMissingException(long id) {
            super("用户不存在 id=" + id);
        }
    }

    /** 下游瞬时故障（5xx，可重试） */
    private static class TransientDownstreamException extends RuntimeException {
        TransientDownstreamException(int status) {
            super("下游 5xx: " + status);
        }
    }
}

// =============================================================================
// src/main/java/com/example/ordersvc/userstub/UserStubApp.java
// =============================================================================

package com.example.ordersvc.userstub;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 练习 2 的下游用户服务（默认端口 18322） */
@SpringBootApplication
public class UserStubApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(UserStubApp.class)
                .properties("server.port=18322")
                .run(args);
    }
}

// =============================================================================
// src/main/java/com/example/ordersvc/userstub/UserStubController.java
// =============================================================================

package com.example.ordersvc.userstub;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 用户端点：id=1 正常、id=9 不存在、id=99 慢（1500ms）、/flaky-user 第一次 500 之后 200。
 * /admin/hits 暴露命中次数，供测试断言「重试真的发生了」。
 */
@RestController
public class UserStubController {

    private final AtomicInteger flakyHits = new AtomicInteger();

    @GetMapping("/users/{id}")
    public ResponseEntity<?> get(@PathVariable long id) throws InterruptedException {
        if (id == 1L) {
            return ResponseEntity.ok(Map.of("id", 1L, "name", "张三"));
        }
        if (id == 99L) {
            Thread.sleep(1500L);
            return ResponseEntity.ok(Map.of("id", 99L, "name", "慢用户"));
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("code", 40400, "message", "用户不存在"));
    }

    @GetMapping("/flaky-user")
    public ResponseEntity<?> flaky() {
        if (flakyHits.incrementAndGet() == 1) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("transient");
        }
        return ResponseEntity.ok(Map.of("id", 7L, "name", "抖动用户"));
    }

    @GetMapping("/admin/hits")
    public Map<String, Integer> hits() {
        return Map.of("flaky-user", flakyHits.get());
    }
}

// =============================================================================
// src/main/resources/application.properties
// =============================================================================

user-service.base-url=http://localhost:18322
logging.level.com.example=INFO

// =============================================================================
// src/test/java/com/example/ordersvc/OrderUserCallTest.java
// =============================================================================

package com.example.ordersvc;

import com.example.ordersvc.orderapp.OrderApp;
import com.example.ordersvc.orderapp.OrderDetail;
import com.example.ordersvc.userstub.UserStubApp;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class OrderUserCallTest {

    private static ConfigurableApplicationContext userApp;
    private static ConfigurableApplicationContext orderApp;
    private static RestClient orderClient;
    private static RestClient userClientRaw;

    @BeforeAll
    static void start() {
        userApp = new SpringApplicationBuilder(UserStubApp.class).run("--server.port=0");
        int userPort = ((WebServerApplicationContext) userApp).getWebServer().getPort();
        orderApp = new SpringApplicationBuilder(OrderApp.class)
                .run("--server.port=0", "--user-service.base-url=http://localhost:" + userPort);
        int orderPort = ((WebServerApplicationContext) orderApp).getWebServer().getPort();
        orderClient = RestClient.create("http://localhost:" + orderPort);
        userClientRaw = RestClient.create("http://localhost:" + userPort);
    }

    @AfterAll
    static void stop() {
        orderApp.close();
        userApp.close();
    }

    @Test
    void composesUserNameAcrossServices() {
        OrderDetail detail = orderClient.get().uri("/orders/1001").retrieve().body(OrderDetail.class);
        assertThat(detail.userName()).isEqualTo("张三");
        assertThat(detail.degraded()).isFalse();
    }

    @Test
    void transientFailureIsRetriedOnce() {
        int hitsBefore = flakyHits();
        OrderDetail detail = orderClient.get().uri("/orders/1004").retrieve().body(OrderDetail.class);
        assertThat(detail.userName()).isEqualTo("抖动用户");
        assertThat(detail.degraded()).isFalse();
        assertThat(flakyHits() - hitsBefore).isEqualTo(2);   // 第 1 次 500，重试第 2 次成功
    }

    @Test
    void slowDownstreamDegradesGracefully() {
        OrderDetail detail = orderClient.get().uri("/orders/1003").retrieve().body(OrderDetail.class);
        assertThat(detail.degraded()).isTrue();
        assertThat(detail.userName()).contains("降级");
    }

    @Test
    void missingUserMapsTo404WithoutRetry() {
        var status = orderClient.get().uri("/orders/1002")
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(404);
    }

    private int flakyHits() {
        Map<?, ?> hits = userClientRaw.get().uri("/admin/hits").retrieve().body(Map.class);
        return ((Number) hits.get("flaky-user")).intValue();
    }
}
