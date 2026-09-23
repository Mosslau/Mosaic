package com.example;

import com.example.idempotency.IdempotencyApplication;
import com.example.idempotency.IdempotencyService;
import com.example.idempotency.OrderResult;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

/** 幂等语义实测：重复提交重放结果、并发撞 key 只处理一次、缺 key 拒绝、过期可重处理 */
class IdempotencyTest {

    private static ConfigurableApplicationContext app;
    private static RestClient client;

    @BeforeAll
    static void startApp() {
        app = new SpringApplicationBuilder(IdempotencyApplication.class).run("--server.port=0");
        int port = ((WebServerApplicationContext) app).getWebServer().getPort();
        client = RestClient.create("http://localhost:" + port);
    }

    @AfterAll
    static void stopApp() {
        app.close();
    }

    private OrderResult submit(String key, String item) {
        return client.post().uri("/orders")
                .header("Idempotency-Key", key)
                .body(Map.of("item", item, "quantity", 1))
                .retrieve().body(OrderResult.class);
    }

    private int processCount() {
        Map<?, ?> body = client.get().uri("/admin/process-count").retrieve().body(Map.class);
        return ((Number) body.get("processCount")).intValue();
    }

    @Test
    void sameKeyReplaysResultWithoutReprocessing() {
        String key = "key-" + System.nanoTime();
        int before = processCount();
        OrderResult first = submit(key, "补能器");
        OrderResult second = submit(key, "补能器");
        assertThat(second.orderId()).isEqualTo(first.orderId());
        assertThat(first.replayed()).isFalse();
        assertThat(second.replayed()).isTrue();
        assertThat(processCount()).isEqualTo(before + 1);   // 业务只执行了一次
    }

    @Test
    void concurrentDuplicatesAreProcessedExactlyOnce() throws Exception {
        String key = "race-" + System.nanoTime();
        int before = processCount();
        int threads = 16;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch gate = new CountDownLatch(1);   // 发令枪：16 个线程同时提交同一 key
        List<Callable<OrderResult>> tasks = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            tasks.add(() -> {
                gate.await();
                return submit(key, "部件");
            });
        }
        List<Future<OrderResult>> futures = new ArrayList<>();
        for (Callable<OrderResult> task : tasks) {
            futures.add(pool.submit(task));
        }
        gate.countDown();
        List<String> orderIds = new ArrayList<>();
        for (Future<OrderResult> f : futures) {
            orderIds.add(f.get().orderId());
        }
        pool.shutdown();
        assertThat(orderIds).hasSize(threads);
        assertThat(orderIds).allSatisfy(id -> assertThat(id).isEqualTo(orderIds.get(0)));
        assertThat(processCount()).isEqualTo(before + 1);   // 16 并发撞同一 key，业务只执行 1 次
    }

    @Test
    void differentKeysAreIndependent() {
        int before = processCount();
        OrderResult a = submit("key-a-" + System.nanoTime(), "轮胎");
        OrderResult b = submit("key-b-" + System.nanoTime(), "轮胎");
        assertThat(a.orderId()).isNotEqualTo(b.orderId());
        assertThat(processCount()).isEqualTo(before + 2);
    }

    @Test
    void missingIdempotencyKeyIsRejected() {
        var response = client.post().uri("/orders")
                .body(Map.of("item", "设备配件", "quantity", 1))
                .exchange((req, res) -> new int[]{res.getStatusCode().value()});
        assertThat(response[0]).isEqualTo(400);
    }

    @Test
    void expiredEntryCanBeReprocessed() {
        // 直接对服务类做 TTL 语义单测（TTL 150ms，真实时钟）
        AtomicInteger counter = new AtomicInteger();
        IdempotencyService service = new IdempotencyService(150L, Clock.systemUTC());
        Integer first = service.execute("ttl-key", counter::incrementAndGet).value();
        Integer replay = service.execute("ttl-key", counter::incrementAndGet).value();
        assertThat(first).isEqualTo(1);
        assertThat(replay).isEqualTo(1);                 // 窗口内重放
        assertThat(counter.get()).isEqualTo(1);
        sleep(250);                                      // 等 TTL 过期
        Integer third = service.execute("ttl-key", counter::incrementAndGet).value();
        assertThat(third).isEqualTo(2);                  // 窗口外重新处理
        assertThat(counter.get()).isEqualTo(2);
    }

    @Test
    void failureIsNotCachedAndCanBeRetried() {
        AtomicInteger counter = new AtomicInteger();
        IdempotencyService service = new IdempotencyService(60_000L, Clock.fixed(Instant.now(), ZoneId.of("UTC")));
        try {
            service.execute("fail-key", () -> {
                counter.incrementAndGet();
                throw new IllegalStateException("下游抖动");
            });
        } catch (IllegalStateException expected) {
            // 第一次失败
        }
        Integer second = service.execute("fail-key", counter::incrementAndGet).value();
        assertThat(second).isEqualTo(2);                 // 失败未缓存，重试成功
        assertThat(counter.get()).isEqualTo(2);
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
