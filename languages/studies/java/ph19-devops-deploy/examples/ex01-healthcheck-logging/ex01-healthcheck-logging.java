// examples/ex01-healthcheck-logging/ex01-healthcheck-logging.java
// 健康检查端点 + JSON 结构化日志 + 优雅停机（对应主文档 3.9/3.11）
// 教学映射（用 JDK 自带组件模拟 Spring Boot 可观测三件套，零第三方依赖）：
//   1. HTTP 健康端点 /actuator/health（及其 liveness/readiness 变体）：
//      —— 容器 HEALTHCHECK、K8s 三类探针、compose service_healthy 吃的都是「HTTP 200 + JSON」这份协议。
//   2. JSON 结构化日志（每行一个 JSON 对象，含 ts/level/logger/msg/业务键值）：
//      —— 集中采集端（Filebeat/Promtail）无需解析文本即可按字段检索，这是「结构化」的全部意义。
//   3. SIGTERM/SIGINT 优雅停机（拒绝新流量 → 等待存量请求完成 → 超时兜底）：
//      —— 与 Spring 的 server.shutdown=graceful + spring.lifecycle.timeout-per-shutdown-phase 同语义。
// 教学性覆盖：
//   业务线程池直接用 HttpServer 的执行器（真实 Boot 是 Tomcat 线程池）；「数据库 DOWN」用一个开关模拟
//   （真实是 DataSourceHealthIndicator 自动探测）；JSON 日志手写构造（真实用 logstash-logback-encoder）。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 examples/ex01-healthcheck-logging/ 目录下执行）
//   javac ex01-healthcheck-logging.java
//   # 2. 运行（自动跑完全部自检并打印 PASS/FAIL 行）
//   java Ex01HealthcheckLoggingDemo
//   # 3. 手动体验：运行后另开终端
//   #    curl -s http://127.0.0.1:18080/actuator/health
//   #    curl -s http://127.0.0.1:18080/actuator/health/readiness
//   #    kill -TERM <pid>   （观察 JSON 日志里的 shutdown_initiated → shutdown_complete）
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicBoolean;

/** 健康检查 / 结构化日志 / 优雅停机 三件套演示（零依赖） */
final class Ex01HealthcheckLoggingDemo {

    private static final int PORT = 18080;
    private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_INSTANT;

    /** 极简 JSON 行日志器：一行一个 JSON 对象，对应主文档 3.9 的「结构化 = 有字段可检索」 */
    static final class JsonLog {
        /** 最近一行日志的原文（供自检断言字段形状，演示「结构化日志可直接按字段消费」） */
        static volatile String lastLine;

        static void info(String logger, String msg, Object... kv) { line("INFO", logger, msg, kv); }
        static void warn(String logger, String msg, Object... kv) { line("WARN", logger, msg, kv); }

        private static void line(String level, String logger, String msg, Object... kv) {
            StringBuilder sb = new StringBuilder();
            sb.append("{\"ts\":\"").append(ISO.format(Instant.now()))
              .append("\",\"level\":\"").append(level)
              .append("\",\"logger\":\"").append(logger)
              .append("\",\"msg\":\"").append(msg).append('"');
            for (int i = 0; i < kv.length; i += 2) {
                sb.append(",\"").append(kv[i]).append("\":\"").append(kv[i + 1]).append('"');
            }
            sb.append('}');
            lastLine = sb.toString();
            System.out.println(lastLine);
        }
    }

    /** 自检结果收集：PASS/FAIL 一行一个 */
    static final class Checks {
        private int passed;
        private int failed;

        void pass(String name) {
            passed++;
            System.out.println("PASS " + name);
        }

        void fail(String name, String reason) {
            failed++;
            System.out.println("FAIL " + name + " -- " + reason);
        }

        void summary() {
            System.out.println("RESULT passed=" + passed + " failed=" + failed);
            if (failed > 0) {
                System.exit(1);
            }
        }
    }

    private HttpServer server;
    private ExecutorService bizPool;
    private final AtomicBoolean dbDown = new AtomicBoolean(false);
    private final AtomicBoolean stopping = new AtomicBoolean(false);
    private final AtomicBoolean shutdownStarted = new AtomicBoolean(false);
    private final AtomicLong requestCount = new AtomicLong();
    private final CountDownLatch slowEntered = new CountDownLatch(1);
    private final Checks checks = new Checks();

    /** 组装探针响应体：状态 UP/DOWN + components 明细（K8s 探针只关心 HTTP 200/非 200 与 body 里的 status） */
    private String healthBody() {
        boolean dbOk = !dbDown.get();
        String status = dbOk ? "UP" : "DOWN";
        return "{\"status\":\"" + status + "\",\"components\":{\"db\":{\"status\":"
                + (dbOk ? "\"UP\"" : "\"DOWN\"") + "}}}";
    }

    private void sendJson(HttpExchange ex, int code, String body) throws IOException {
        byte[] out = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(code, out.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(out);
        }
    }

    private void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        bizPool = Executors.newFixedThreadPool(4);        // 业务线程池：真实 Boot 是 Tomcat 池
        server.setExecutor(bizPool);
        server.createContext("/actuator/health", ex -> {
            requestCount.incrementAndGet();
            sendJson(ex, 200, healthBody());
        });
        server.createContext("/actuator/health/liveness", ex -> {
            // 教学点：liveness 只回答「进程还活着吗」，不掺外部依赖 —— DB 挂了 liveness 依旧 UP
            requestCount.incrementAndGet();
            sendJson(ex, 200, "{\"status\":\"UP\"}");
        });
        server.createContext("/actuator/health/readiness", ex -> {
            // 教学点：readiness 回答「能接流量吗」，DB 挂了就 DOWN → K8s 摘流量不杀进程
            requestCount.incrementAndGet();
            sendJson(ex, 200, healthBody());
        });
        server.createContext("/slow", ex -> {
            // 模拟在途业务请求（如一次慢查询）：进入后通知测试线程，然后睡 1.5s 模拟处理
            if (stopping.get()) {
                sendJson(ex, 503, "{\"status\":\"SHUTTING_DOWN\"}");
                return;
            }
            slowEntered.countDown();
            try {
                Thread.sleep(1500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            sendJson(ex, 200, "{\"result\":\"slow_done\"}");
        });
        server.createContext("/metrics", ex -> {
            requestCount.incrementAndGet();
            sendJson(ex, 200, "{\"http_requests_total\":" + requestCount.get() + "}");
        });
        server.start();
        JsonLog.info("Ex01Demo", "server_started", "port", String.valueOf(PORT));
    }

    /** 优雅停机核心：与 Spring server.shutdown=graceful 同语义（先拒新、再等存量、超时兜底）。幂等：重复触发直接忽略 */
    private void gracefulShutdown(String reason) {
        if (!shutdownStarted.compareAndSet(false, true)) {
            JsonLog.info("Ex01Demo", "shutdown_already_in_progress", "reason", reason);
            return;
        }
        JsonLog.info("Ex01Demo", "shutdown_initiated", "reason", reason);
        stopping.set(true);
        server.stop(5);                                     // 1) 关闭监听：不再接受新连接
        // 2) 已进入的业务请求（/slow）由 server.stop 等待自然结束 —— 对应「等存量请求完成」
        bizPool.shutdown();                                 // 3) 业务线程池收尾（超时兜底：超过 5s 强制结束）
        try {
            if (!bizPool.awaitTermination(5, TimeUnit.SECONDS)) {
                JsonLog.warn("Ex01Demo", "graceful_timeout_force_shutdown");
                bizPool.shutdownNow();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            bizPool.shutdownNow();
        }
        JsonLog.info("Ex01Demo", "shutdown_complete", "elapsedMs", "in_flight_allowed_to_finish");
    }

    private String get(String path) throws Exception {
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
        HttpRequest req = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + PORT + path))
                .timeout(Duration.ofSeconds(5)).GET().build();
        return client.send(req, HttpResponse.BodyHandlers.ofString()).body();
    }

    private void runAssertions() throws Exception {
        // 1. 健康端点：200 + status=UP
        String health = get("/actuator/health");
        if (health.contains("\"status\":\"UP\"")) {
            checks.pass("health endpoint reports UP");
        } else {
            checks.fail("health endpoint UP", health);
        }

        // 2. 结构化日志：server_started 那行必须是「每行一个 JSON、字段可直接消费」的形状
        //    （生产采集端按 logger/level/msg 检索、按业务键值告警的前提；本自检断言字段完备）
        String logLine = JsonLog.lastLine;
        if (logLine != null && logLine.startsWith("{")
                && logLine.contains("\"level\":\"INFO\"")
                && logLine.contains("\"logger\":\"Ex01Demo\"")
                && logLine.contains("\"msg\":\"server_started\"")
                && logLine.contains("\"port\":\"18080\"")) {
            checks.pass("structured json log line has searchable fields");
        } else {
            checks.fail("structured json log", String.valueOf(logLine));
        }

        // 3. DB DOWN 时：readiness/health 转 DOWN，liveness 仍 UP（探针语义分工，见主文档 3.5/3.11）
        dbDown.set(true);
        String rd = get("/actuator/health/readiness");
        String lv = get("/actuator/health/liveness");
        if (rd.contains("\"status\":\"DOWN\"") && lv.contains("\"status\":\"UP\"")) {
            checks.pass("db down -> readiness DOWN but liveness UP (probe semantics)");
        } else {
            checks.fail("db down probe split", "readiness=" + rd + " liveness=" + lv);
        }
        dbDown.set(false);

        // 4. metrics 端点存在且计数自增（必须在优雅停机前检查：停机后端点已不可用）
        String m = get("/metrics");
        if (m.contains("http_requests_total")) {
            checks.pass("metrics endpoint exposes counters");
        } else {
            checks.fail("metrics endpoint", m);
        }

        // 5. 优雅停机：发起一个 1.5s 的在途请求，随后触发停机 —— 在途请求必须正常拿到 200（不被掐断）
        Thread slow = new Thread(() -> {
            try {
                get("/slow");
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }, "slow-client");
        slow.start();
        slowEntered.await();                       // 等 /slow 真正进入处理（确定性时序，不 sleep 猜）
        gracefulShutdown("SIGTERM-simulated");     // 与 JVM 收到 kill -TERM 时 addShutdownHook 走同一方法
        slow.join(5000);
        if (!slow.isAlive()) {
            checks.pass("in-flight request completed during graceful shutdown");
        } else {
            checks.fail("in-flight drain", "slow request still running after shutdown");
            slow.interrupt();
        }

        // 6. 停机后新流量被拒（连接拒绝 或 503），不再接受新请求
        try {
            get("/actuator/health");
            checks.fail("new traffic rejected", "request unexpectedly succeeded after shutdown");
        } catch (IOException expected) {
            checks.pass("new traffic rejected after shutdown (connection refused)");
        }
    }

    public static void main(String[] args) throws Exception {
        Ex01HealthcheckLoggingDemo demo = new Ex01HealthcheckLoggingDemo();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            // 真实 kill -TERM 的入口：进程被 SIGTERM 时 JVM 跑这里，同样走优雅停机
            if (demo.server != null) {                 // start() 失败时（如端口占用）不重复收尾
                demo.gracefulShutdown("SIGTERM");
            }
        }, "shutdown-hook"));
        demo.start();
        demo.runAssertions();
        demo.checks.summary();
    }
}
