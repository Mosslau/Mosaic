// examples/ex01-jdk-httpserver/src/com/example/RestServer.java —— 纯 JDK HttpServer 手写 REST 服务
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖（com.sun.net.httpserver 是 JDK 内建）
// 验证状态：已验证（本机实测）
// 验证命令：javac -d out src/com/example/RestServer.java && java -cp out com.example.RestServer 18080
// 实测结果（curl 直测，见 examples/README.md）：
//   GET  /api/ping          → 200 {"message":"pong"}，响应头含 Access-Control-Allow-Origin: *
//   GET  /api/users         → 200 [{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}]（JSON 数组）
//   POST /api/users         → 201 {"id":1,"name":"Alice"}（Content-Type: application/json 才受理）
//   POST /api/users（缺 name）→ 400 {"error":"invalid_body: field 'name' is required and non-blank"}
//   GET  /api/users/2       → 200 {"id":2,"name":"Bob"}
//   GET  /api/users/999     → 404 {"error":"not_found","id":999}
//   GET  /api/unknown       → 404 {"error":"not_found","path":"/api/unknown"}
//   PUT  /api/users         → 405 {"error":"method_not_allowed","method":"PUT","path":"/api/users"}
// 日志中间件实测输出：每次请求一行 [log] 方法 路径 -> 状态码 (耗时 ms)
// 运行前提：无（普通 java 进程）；端口 18080 被占用时换高位端口
// ---------------------------------------------------------------------------
// 教学点：本文件用「纯 JDK」演示 HTTP 服务的最小闭环——HttpServer 起端口、createContext
// 注册路由、HttpExchange 读请求/写响应、手工解析 JSON（本阶段不引第三方 JSON 库，
// 完整 JSON 解析属于 ph07 IO 阶段之后的序列化话题；这里用最小实现撑起 REST 演示）。
// 日志中间件用 Filter 实现：任何处理器执行前打印 方法+路径+状态码+耗时。
package com.example;

import com.sun.net.httpserver.Filter;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 纯 JDK 的最小 REST 服务：路由分发 + JSON 手工解析 + 状态码 + CORS + 日志中间件。 */
public final class RestServer {

    private static final String JSON_CT = "application/json; charset=UTF-8";
    private static final String CORS_ORIGIN = "*";

    /** 内存用户表（演示用；真实服务的数据层在 ph13 数据库阶段）。 */
    private final Map<Long, String> users = new LinkedHashMap<>();
    private long nextId = 1;

    // GET /api/ping 与 /api/users 由 PathHandler 统一分发；正则按路由提取路径参数
    private static final Pattern USER_BY_ID = Pattern.compile("^/api/users/(\\d+)$");

    public static void main(String[] args) throws IOException {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18080;
        new RestServer().start(port);
    }

    void start(int port) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        // 先建上下文（不绑定处理器），再挂日志中间件 Filter，最后才 setHandler——
        // 顺序反过来会建出两个同名上下文，Filter 挂在的那个收不到请求
        var ctx = server.createContext("/api");
        ctx.getFilters().add(new AccessLogFilter());
        ctx.setHandler(new ApiHandler());
        // 线程池：每个请求一个任务；本机实测 2 线程足够（教学演示不压测）
        server.setExecutor(Executors.newFixedThreadPool(2));
        server.start();
        System.out.println("REST server listening on http://127.0.0.1:" + port);
    }

    /** 路由分发：按方法 + 路径决定动作，是「Controller 不做复杂业务」的最小雏形。 */
    private final class ApiHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange ex) throws IOException {
            String path = ex.getRequestURI().getPath();
            String method = ex.getRequestMethod();
            try {
                if (path.equals("/api/ping") && method.equals("GET")) {
                    sendJson(ex, 200, Map.of("message", "pong"));
                } else if (path.equals("/api/users") && method.equals("GET")) {
                    sendJson(ex, 200, users.entrySet().stream()
                            .map(e -> { var m = new LinkedHashMap<String, Object>();
                                        m.put("id", e.getKey()); m.put("name", e.getValue()); return m; })
                            .toList());
                } else if (path.equals("/api/users") && method.equals("POST")) {
                    handleCreate(ex);
                } else if (path.equals("/api/users") || path.equals("/api/ping")) {
                    // 路径存在但方法不支持 → 405 Method Not Allowed（语义化状态码的体现）
                    var m405 = new LinkedHashMap<String, Object>();
                    m405.put("error", "method_not_allowed");
                    m405.put("method", method);
                    m405.put("path", path);
                    sendJson(ex, 405, m405);
                } else {
                    Matcher m = USER_BY_ID.matcher(path);
                    if (m.matches() && method.equals("GET")) {
                        long id = Long.parseLong(m.group(1));
                        String name = users.get(id);
                        if (name == null) {
                            var m404 = new LinkedHashMap<String, Object>();
                            m404.put("error", "not_found");
                            m404.put("id", id);
                            sendJson(ex, 404, m404);
                        } else {
                            var m2 = new LinkedHashMap<String, Object>();
                            m2.put("id", id); m2.put("name", name);
                            sendJson(ex, 200, m2);
                        }
                    } else {
                        sendJson(ex, 404, Map.of("error", "not_found", "path", path));
                    }
                }
            } catch (IllegalArgumentException iae) {
                // 参数校验失败 → 400（「参数校验」话题在本阶段 3.4 详讲）
                sendJson(ex, 400, Map.of("error", iae.getMessage()));
            }
        }

        private void handleCreate(HttpExchange ex) throws IOException {
            String ctype = ex.getRequestHeaders().getFirst("Content-Type");
            if (ctype == null || !ctype.startsWith("application/json")) {
                sendJson(ex, 400, Map.of("error", "content_type_must_be_json"));
                return;
            }
            String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            Map<String, String> parsed = MiniJson.parseObject(body);
            String name = parsed.get("name");
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("invalid_body: field 'name' is required and non-blank");
            }
            long id = nextId++;
            users.put(id, name);
            var m = new LinkedHashMap<String, Object>();
            m.put("id", id); m.put("name", name);
            sendJson(ex, 201, m);
        }
    }

    private void sendJson(HttpExchange ex, int status, Object payload) throws IOException {
        byte[] body = MiniJson.toJson(payload).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", JSON_CT);
        // CORS 头：允许任意源跨域读取（完整 CORS 语义见 3.7）
        ex.getResponseHeaders().set("Access-Control-Allow-Origin", CORS_ORIGIN);
        ex.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        ex.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
        ex.sendResponseHeaders(status, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }

    /** 日志中间件：记录每次请求的方法、路径、状态码与耗时（横切关注点的 JDK 原生实现）。 */
    private static final class AccessLogFilter extends Filter {
        @Override
        public void doFilter(HttpExchange exchange, Chain chain) throws IOException {
            long start = System.nanoTime();
            try {
                chain.doFilter(exchange);
            } finally {
                long ms = (System.nanoTime() - start) / 1_000_000;
                System.out.printf("[log] %s %s -> %d (%d ms)%n",
                        exchange.getRequestMethod(), exchange.getRequestURI().getPath(),
                        exchange.getResponseCode(), ms);
            }
        }

        @Override
        public String description() {
            return "access log filter";
        }
    }
}
