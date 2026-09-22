// project/springboot-deploy-template/purejava/src/purejava/MiniApp.java
// 纯 Java 参考实现：用 JDK 自带能力模拟「Spring Boot 可执行 jar」的部署语义（对应主文档 3.2/3.9/3.11）
// 教学映射（为什么要有一个纯 Java 版：见 project/README 与 app-smoke.sh）：
//   1. 可执行 jar：jar cfe 写 Main-Class，java -jar 直接跑（对应 Boot 的 JarLauncher 效果）；
//   2. actuator 语义端点 /actuator/health(+liveness/readiness) 与 /ping：探针/探活吃的协议；
//   3. 配置外置：启动参数 -Dapp.profile=prod / 环境变量 / config/application.properties 覆盖默认值
//      —— 对应 Boot 的「jar 不变，配置随环境注入」（主文档 3.2 末尾）；
//   4. SIGTERM 优雅停机：shutdown hook 里先拒新流量再收尾（对应 server.shutdown=graceful，主文档 3.11）。
// 教学性覆盖：单文件实现 http 端点；无第三方依赖（java.net.http / com.sun.net.httpserver 均为 JDK 自带）。
// 验证环境：OpenJDK 17（javac -version -> 17.x）
// 验证命令（完整冒烟链见同目录 app-smoke.sh，本机已全部 PASS）：
//   javac -d out src/purejava/MiniApp.java
//   jar --create --file mini-app.jar --main-class purejava.MiniApp -C out .
//   java -jar mini-app.jar &
//   curl -s http://127.0.0.1:18099/actuator/health
// 验证状态：已验证（OpenJDK 17.0.18 本机实测，含优雅停机退出路径）

package purejava;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 迷你服务：可执行 jar + 健康端点 + 外置配置 + 优雅停机（Boot 部署语义的纯 Java 版）。
 */
public final class MiniApp {

    private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_INSTANT;
    private static final long STARTED_AT = System.currentTimeMillis();

    // ---- 运行配置：env / -D / properties 文件 / 默认 四层，越靠左优先级越高（对应 Boot 配置优先级心智） ----
    static final String PORT = firstNonNull(
            System.getProperty("purejava.port"), System.getenv("PUREJAVA_PORT"), "18099");
    static final String APP_NAME = firstNonNull(
            System.getProperty("app.name"), System.getenv("APP_NAME"), "mini-app");
    static final String APP_PROFILE = firstNonNull(
            System.getProperty("app.profile"), System.getenv("APP_PROFILE"), loadFileProfile());
    static final String APP_VERSION = "1.0.0";

    static String loadFileProfile() {
        // 模拟外置 application.properties：工作目录下 config/application.properties 的 app.profile
        Properties p = new Properties();
        try (var in = Files.newInputStream(Path.of("config/application.properties"))) {
            p.load(in);
            return p.getProperty("app.profile", "dev");
        } catch (IOException e) {
            return "dev";                       // 没有外置文件 → 默认 dev
        }
    }

    static String firstNonNull(String... candidates) {
        for (String c : candidates) {
            if (c != null && !c.isBlank()) {
                return c;
            }
        }
        return "";
    }

    // ---- 极简 JSON 日志（对应结构化日志：一行一个 JSON，见主文档 3.9） ----
    static void log(String level, String msg) {
        System.out.println("{\"ts\":\"" + ISO.format(Instant.now())
                + "\",\"level\":\"" + level
                + "\",\"logger\":\"purejava.MiniApp\""
                + ",\"msg\":\"" + msg + "\"}");
    }

    private final AtomicBoolean stopping = new AtomicBoolean(false);
    private final AtomicLong requestCount = new AtomicLong();
    private HttpServer server;

    private void send(HttpExchange ex, int code, String body) throws IOException {
        byte[] out = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(code, out.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(out);
        }
    }

    private String healthBody() {
        return "{\"status\":\"UP\",\"app\":\"" + APP_NAME + "\",\"profile\":\"" + APP_PROFILE
                + "\",\"uptimeMs\":" + (System.currentTimeMillis() - STARTED_AT) + "}";
    }

    private void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", Integer.parseInt(PORT)), 0);
        server.createContext("/actuator/health", ex -> {
            requestCount.incrementAndGet();
            send(ex, 200, healthBody());
        });
        server.createContext("/actuator/health/liveness", ex -> {
            requestCount.incrementAndGet();
            send(ex, 200, "{\"status\":\"UP\"}");            // liveness：进程活着即 UP
        });
        server.createContext("/actuator/health/readiness", ex -> {
            requestCount.incrementAndGet();
            String body = stopping.get()
                    ? "{\"status\":\"DOWN\",\"reason\":\"shutting_down\"}"
                    : "{\"status\":\"UP\"}";                  // readiness：停机/未就绪时 DOWN（摘流量语义）
            send(ex, 200, body);
        });
        server.createContext("/ping", ex -> {
            requestCount.incrementAndGet();
            send(ex, 200, "{\"app\":\"" + APP_NAME + "\",\"profile\":\"" + APP_PROFILE
                    + "\",\"version\":\"" + APP_VERSION + "\",\"requests\":" + requestCount.get() + "}");
        });
        server.start();
        log("INFO", "server_started port=" + PORT + " profile=" + APP_PROFILE);
    }

    /** 优雅停机：与 Spring server.shutdown=graceful 同语义（先拒新、再收尾、日志可观测） */
    private void gracefulShutdown() {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        log("INFO", "shutdown_initiated reason=SIGTERM");
        server.stop(0);                                        // 关闭监听：不再接受新连接
        log("INFO", "shutdown_complete in_flight_allowed_to_finish");
    }

    public static void main(String[] args) throws IOException {
        MiniApp app = new MiniApp();
        Runtime.getRuntime().addShutdownHook(new Thread(app::gracefulShutdown, "shutdown-hook"));
        app.start();
        log("INFO", "mini-app ready curl http://127.0.0.1:" + PORT + "/actuator/health");
    }
}
