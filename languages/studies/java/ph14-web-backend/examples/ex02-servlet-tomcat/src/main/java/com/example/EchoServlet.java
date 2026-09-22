// examples/ex02-servlet-tomcat/src/main/java/com/example/EchoServlet.java —— 手写 Servlet：GET/POST + 路径参数
// 验证环境：OpenJDK 17.0.18 + Tomcat 10.1.31（jakarta.servlet 6.0 API，由 tomcat-embed-core 提供）
// 验证状态：已验证（本机实测，见 README）
// 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone -q package，然后按 README 的 java -cp 启动
// 实测结果（curl 直测，端口 18081）：
//   GET  /echo/hello?name=Alice → 200 {"path":"/hello","method":"GET","name":"Alice","message":"Hello, Alice"}
//   POST /echo/hello（body {"msg":"hi"}）→ 200 {"path":"/hello","method":"POST","body":"{"msg":"hi"}"}
//   GET  /echo/other             → 404 {"error":"not_found","path":"/other"}（404 状态码实测）
// ---------------------------------------------------------------------------
// 教学点：Servlet 是 HTTP 请求进入 Java 服务的第一站——doGet/doPost 对应 HTTP 方法，
// getPathInfo() 取路径参数、getParameter 取查询参数、getReader() 读请求体。
// 注解 @WebServlet 相当于 web.xml 的 <servlet-mapping>（Tomcat 扫描注解完成注册）。
package com.example;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
/** 用 @WebServlet 注解注册到 /echo/* 路径的手写 Servlet。 */
@WebServlet("/echo/*")
public final class EchoServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        String path = req.getPathInfo();          // /hello（去掉前缀 /echo）
        if (path == null || !path.equals("/hello")) {
            // 只受理 /echo/hello：其他子路径 → 404（语义化状态码的 Servlet 层体现）
            writeJson(resp, 404, "{\"error\":\"not_found\",\"path\":\"" + (path == null ? "" : path) + "\"}");
            return;
        }
        String name = req.getParameter("name");   // 查询参数 ?name=Alice
        String body = "{\"path\":\"" + path + "\",\"method\":\"GET\",\"name\":\""
                + (name == null ? "?" : name) + "\",\"message\":\"Hello, " + (name == null ? "?" : name) + "\"}";
        writeJson(resp, 200, body);
    }

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        String path = req.getPathInfo();
        // getReader() 读请求体为字符流，readLine 逐行拼回原样（教学演示，完整 JSON 解析留给 Jackson）
        StringBuilder sb = new StringBuilder();
        String line;
        try (var reader = req.getReader()) {
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        String json = "{\"path\":\"" + path + "\",\"method\":\"POST\",\"body\":\"" + sb + "\"}";
        writeJson(resp, 200, json);
    }

    private void writeJson(HttpServletResponse resp, int status, String json) throws IOException {
        resp.setStatus(status);
        resp.setContentType("application/json; charset=UTF-8");
        resp.getWriter().write(json);
    }
}
