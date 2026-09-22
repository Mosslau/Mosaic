// exercises/sol-01-todo-jdk-httpserver.java —— 练习 1 参考实现：纯 JDK HttpServer 手写 Todo REST API
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖
// 验证状态：已验证（本机实测，javac + java + curl）
// 实测结果（按下面顺序 curl）：
//   POST /api/todos {"title":"write tests"} → 201 {"id":1,"title":"write tests","done":false}
//   POST /api/todos {"title":"  "} → 400 {"error":"invalid_body: title required"}（校验实测）
//   GET  /api/todos        → 200 [{"id":1,"title":"write tests","done":false}]
//   PATCH /api/todos/1 {"done":true} → 200 {"id":1,"title":"write tests","done":true}
//   DELETE /api/todos/1   → 204（无响应体）
//   GET  /api/todos/99    → 404 {"error":"not_found","id":99}
// ---------------------------------------------------------------------------
// 本练习的源码拆两个文件：
//   ① src/com/example/TodoServer.java（本文件内容，main + 路由 + 内存表）
//   ② src/com/example/MiniJson.java —— 直接复制 examples/ex01-jdk-httpserver 里的同名文件
//      （教学用最小 JSON 解析；练习重点在 HTTP 服务，不在 JSON 库）
//
// 编译与运行：
//   javac -d out src/com/example/TodoServer.java src/com/example/MiniJson.java
//   java -cp out com.example.TodoServer 18087        # 另开终端跑下面的 curl
//
// 教学点：Todo 是 REST 的经典入门资源——用四个 HTTP 方法表达 CRUD：
//   GET 列表 / POST 创建 / PATCH 局部更新 / DELETE 删除，资源路径 /api/todos/{id}。
// 与 ex01 的差异：引入了「路径参数 + 请求体解析 + 204 无内容响应」，REST 语义更完整。
package com.example;

import com.sun.net.httpserver.HttpExchange;
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

/** 手写 Todo REST API（纯 JDK）：GET/POST/PATCH/DELETE + 校验 + 状态码。 */
public final class TodoServer {

    private static final Pattern TODO_BY_ID = Pattern.compile("^/api/todos/(\\d+)$");

    /** 内存 todo 表：id → {id, title, done}。 */
    private final Map<Long, Map<String, Object>> todos = new LinkedHashMap<>();
    private long nextId = 1;

    public static void main(String[] args) throws IOException {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18087;
        new TodoServer().start(port);
    }

    void start(int port) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        var ctx = server.createContext("/api");
        ctx.setHandler(this::handle);
        server.setExecutor(Executors.newFixedThreadPool(2));
        server.start();
        System.out.println("Todo server listening on http://127.0.0.1:" + port);
    }

    private void handle(HttpExchange ex) throws IOException {
        String path = ex.getRequestURI().getPath();
        String method = ex.getRequestMethod();
        try {
            if (path.equals("/api/todos")) {
                if (method.equals("GET")) sendJson(ex, 200, new ArrayList<>(todos.values()));
                else if (method.equals("POST")) handleCreate(ex);
                else sendJson(ex, 405, Map.of("error", "method_not_allowed"));
            } else {
                Matcher m = TODO_BY_ID.matcher(path);
                if (m.matches()) {
                    long id = Long.parseLong(m.group(1));
                    switch (method) {
                        case "GET" -> handleGetById(ex, id);
                        case "PATCH" -> handlePatch(ex, id);
                        case "DELETE" -> handleDelete(ex, id);
                        default -> sendJson(ex, 405, Map.of("error", "method_not_allowed"));
                    }
                } else {
                    sendJson(ex, 404, Map.of("error", "not_found", "path", path));
                }
            }
        } catch (IllegalArgumentException iae) {
            sendJson(ex, 400, Map.of("error", iae.getMessage()));
        }
    }

    private void handleCreate(HttpExchange ex) throws IOException {
        Map<String, String> body = parseBody(ex);
        String title = body.get("title");
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("invalid_body: title required");
        }
        long id = nextId++;
        Map<String, Object> todo = new LinkedHashMap<>();
        todo.put("id", id);
        todo.put("title", title);
        todo.put("done", false);
        todos.put(id, todo);
        sendJson(ex, 201, todo);
    }

    private void handleGetById(HttpExchange ex, long id) throws IOException {
        Map<String, Object> todo = todos.get(id);
        if (todo == null) sendJson(ex, 404, Map.of("error", "not_found", "id", id));
        else sendJson(ex, 200, todo);
    }

    private void handlePatch(HttpExchange ex, long id) throws IOException {
        Map<String, Object> todo = todos.get(id);
        if (todo == null) { sendJson(ex, 404, Map.of("error", "not_found", "id", id)); return; }
        Map<String, String> body = parseBody(ex);
        String done = body.get("done");
        if (done != null) todo.put("done", Boolean.parseBoolean(done));
        String title = body.get("title");
        if (title != null && !title.isBlank()) todo.put("title", title);
        sendJson(ex, 200, todo);
    }

    private void handleDelete(HttpExchange ex, long id) throws IOException {
        if (todos.remove(id) == null) sendJson(ex, 404, Map.of("error", "not_found", "id", id));
        else sendJson(ex, 204, null); // 204 No Content：删除成功无响应体
    }

    private Map<String, String> parseBody(HttpExchange ex) throws IOException {
        String raw = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        return raw.isBlank() ? Map.of() : MiniJson.parseObject(raw);
    }

    private void sendJson(HttpExchange ex, int status, Object payload) throws IOException {
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
        if (status == 204) {
            ex.sendResponseHeaders(204, -1); // 204 不允许带响应体（-1 = 无 body）
            ex.close();
            return;
        }
        byte[] body = payload == null ? new byte[0] : MiniJson.toJson(payload).getBytes(StandardCharsets.UTF_8);
        ex.sendResponseHeaders(status, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }
}
