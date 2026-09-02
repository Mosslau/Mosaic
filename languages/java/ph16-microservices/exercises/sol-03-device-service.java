// exercises/sol-03-device-service.java —— 练习 3 参考实现：设备管理服务（车联网方向，幂等注册）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0（starter-web/test 离线缓存内）
// 验证状态：已验证（本机离线 mvn -o -Dmaven.repo.local=/tmp/m2clone test，BUILD SUCCESS）
// 实测结果：Tests run: 4, Failures: 0, Errors: 0
//   （registerAndQuery / missingIdempotencyKeyGets400：缺 Idempotency-Key → 400 code 40001 /
//     sameKeyReplaysWithoutRecreating：同 key 重放，createCount 只 +1 /
//     concurrentRegistrationOfSameSnCreatesOnce：12 并发不同 key 注册同一 sn，createCount 只 +1）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex01-service-split-restcall/pom.xml，
//   artifactId 改 sol03-device-service，运行端口 18324）+ 下列文件。
//   验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 教学点：幂等两层防——请求级幂等键（网络重试）+ 业务级唯一约束（换 key 重发）。设备注册是
//   车联网典型写入路径：弱网环境下设备会反复上报注册，服务端必须幂等（对应 roadmap 练习「设备管理服务」）。

// =============================================================================
// src/main/java/com/example/devicesvc/Device.java
// =============================================================================

package com.example.devicesvc;

/** 设备（sn 是唯一业务键，天然幂等约束） */
public record Device(String sn, String model, String status) {
}

// =============================================================================
// src/main/java/com/example/devicesvc/DeviceController.java
// =============================================================================

package com.example.devicesvc;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 设备注册端点：双重幂等——
 * ① 请求级：Idempotency-Key 头去重（网络重试/用户重复点击，键级重放首个结果）；
 * ② 业务级：sn 唯一约束兜底（换 key 重发同一设备也只会有一条记录）。
 * createCount 暴露真实建单次数，供测试断言幂等。
 */
@RestController
public class DeviceController {

    private final Map<String, Device> devices = new ConcurrentHashMap<>();
    private final Map<String, Device> byIdempotencyKey = new ConcurrentHashMap<>();
    private final AtomicInteger createCount = new AtomicInteger();

    @PostMapping("/devices")
    public ResponseEntity<?> register(@RequestHeader(value = "Idempotency-Key", required = false) String key,
                                      @RequestBody Map<String, String> body) {
        if (key == null || key.isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("code", 40001, "message", "缺少 Idempotency-Key 请求头"));
        }
        String sn = body.get("sn");
        String model = body.getOrDefault("model", "unknown");
        if (sn == null || sn.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("code", 40002, "message", "sn 不能为空"));
        }
        Device replay = byIdempotencyKey.get(key);
        if (replay != null) {
            return ResponseEntity.ok(replay);   // 同 key 重放，不再创建
        }
        // 业务级幂等：putIfAbsent 保证同 sn 并发只建一条
        Device created = new Device(sn, model, "ONLINE");
        Device existing = devices.putIfAbsent(sn, created);
        Device result = existing != null ? existing : created;
        if (existing == null) {
            createCount.incrementAndGet();
        }
        byIdempotencyKey.putIfAbsent(key, result);
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }

    @GetMapping("/devices/{sn}")
    public ResponseEntity<?> get(@PathVariable String sn) {
        Device device = devices.get(sn);
        if (device == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("code", 40400, "message", "设备不存在 sn=" + sn));
        }
        return ResponseEntity.ok(device);
    }

    @GetMapping("/admin/create-count")
    public Map<String, Integer> createCount() {
        return Map.of("createCount", createCount.get());
    }
}

// =============================================================================
// src/main/java/com/example/devicesvc/DeviceServiceApp.java
// =============================================================================

package com.example.devicesvc;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 练习 3：设备管理服务（默认端口 18324）——车联网方向的设备注册/查询，幂等注册 */
@SpringBootApplication
public class DeviceServiceApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(DeviceServiceApp.class)
                .properties("server.port=18324")
                .run(args);
    }
}

// =============================================================================
// src/test/java/com/example/devicesvc/DeviceServiceTest.java
// =============================================================================

package com.example.devicesvc;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;

class DeviceServiceTest {

    private static ConfigurableApplicationContext app;
    private static RestClient client;

    @BeforeAll
    static void start() {
        app = new SpringApplicationBuilder(DeviceServiceApp.class).run("--server.port=0");
        int port = ((WebServerApplicationContext) app).getWebServer().getPort();
        client = RestClient.create("http://localhost:" + port);
    }

    @AfterAll
    static void stop() {
        app.close();
    }

    private Device register(String key, String sn) {
        return client.post().uri("/devices")
                .header("Idempotency-Key", key)
                .body(Map.of("sn", sn, "model", "EV-2024"))
                .retrieve().body(Device.class);
    }

    private int createCount() {
        Map<?, ?> body = client.get().uri("/admin/create-count").retrieve().body(Map.class);
        return ((Number) body.get("createCount")).intValue();
    }

    @Test
    void registerAndQuery() {
        String sn = "SN-" + System.nanoTime();
        Device device = register("k-" + sn, sn);
        assertThat(device.status()).isEqualTo("ONLINE");
        Device fetched = client.get().uri("/devices/" + sn).retrieve().body(Device.class);
        assertThat(fetched.model()).isEqualTo("EV-2024");
    }

    @Test
    void missingIdempotencyKeyGets400() {
        var status = client.post().uri("/devices").body(Map.of("sn", "SN-X"))
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(400);
    }

    @Test
    void sameKeyReplaysWithoutRecreating() {
        String sn = "SN-" + System.nanoTime();
        int before = createCount();
        Device first = register("k-" + sn, sn);
        Device second = register("k-" + sn, sn);
        assertThat(second.sn()).isEqualTo(first.sn());
        assertThat(createCount()).isEqualTo(before + 1);
    }

    @Test
    void concurrentRegistrationOfSameSnCreatesOnce() throws Exception {
        String sn = "SN-RACE-" + System.nanoTime();
        int before = createCount();
        int threads = 12;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch gate = new CountDownLatch(1);
        List<Callable<Device>> tasks = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            // 每个线程用不同的 key（模拟不同客户端重试）——检验业务级 sn 幂等
            String key = "race-" + i + "-" + sn;
            tasks.add(() -> {
                gate.await();
                return register(key, sn);
            });
        }
        List<Future<Device>> futures = new ArrayList<>();
        for (Callable<Device> t : tasks) {
            futures.add(pool.submit(t));
        }
        gate.countDown();
        for (Future<Device> f : futures) {
            assertThat(f.get().sn()).isEqualTo(sn);
        }
        pool.shutdown();
        assertThat(createCount()).isEqualTo(before + 1);   // 12 并发同 sn，只建 1 条
    }
}
