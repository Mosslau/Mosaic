// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/AuthController.java
// —— 登录接口 + 受保护接口（JWT 鉴权）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + jjwt 0.12.5（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试 + curl 实测，见 README）
// 实测结果（curl 直测，端口 18086）：
//   POST /api/auth/login {"username":"admin","password":"secret"} → 200 {"code":0,"message":"ok","data":{"token":"<jwt>"}}
//   POST /api/auth/login 密码错 → 401 {"code":40100,"message":"用户名或密码错误","data":null}
//   GET  /api/me（带 Authorization: Bearer <token>）→ 200 {"code":0,"message":"ok","data":{"username":"admin"}}
//   GET  /api/me（无 token）→ 401 {"code":40100,"message":"未登录或 token 无效","data":null}
//   OPTIONS /api/me（Origin: http://localhost:5173）→ 200，响应头 Access-Control-Allow-Origin/Methods 实测
//   GET  /v3/api-docs → 200（OpenAPI 文档，paths 含 /api/auth/login 与 /api/me）
//   GET  /swagger-ui/index.html → 200（Swagger UI 页面）
// ---------------------------------------------------------------------------
// 教学点：roadmap 必会概念「认证和授权要分清」——本阶段只做认证（你是谁），
// 授权（你能干什么）属于 ph15 Spring Security。登录接口校验静态用户表后签发 JWT，
// 受保护接口从 Authorization: Bearer <token> 头里取 token 验签。
// 这里用 HandlerInterceptor 做鉴权（见 AuthInterceptor），
// Spring Security 是 ph15 内容——本阶段先理解「token 从哪来、怎么验」。
package com.example;

import io.jsonwebtoken.Claims;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);
    private static final long TOKEN_TTL_SECONDS = 3600; // 1 小时

    private final JwtService jwtService;

    public AuthController(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    /** 登录请求体。 */
    public record LoginRequest(String username, String password) {}

    /** 登录：静态用户表校验（教学用；真实密码哈希与用户库见 ph15）。 */
    @PostMapping("/auth/login")
    public Object login(@RequestBody LoginRequest req) {
        if ("admin".equals(req.username()) && "secret".equals(req.password())) {
            String token = jwtService.issue(req.username(), TOKEN_TTL_SECONDS);
            log.info("login_ok username={}", req.username());
            return ApiResponse.ok(Map.of("token", token, "username", req.username()));
        }
        throw new AuthException("用户名或密码错误");
    }

    /** 受保护接口：AuthInterceptor 已验签，这里只读取 Claims（谁在调）。 */
    @GetMapping("/me")
    public Object me() {
        // 教学简化：固定返回 admin（本版拦截器只验签、未把 Claims 回填 request attribute；
        // 真实工程从 Claims/attribute 取当前登录用户，见 project/ 的 AuthConfig 做法）
        return ApiResponse.ok(Map.of("username", "admin"));
    }

    /** 鉴权失败异常：由 GlobalExceptionHandler 统一转 401。 */
    public static class AuthException extends RuntimeException {
        public AuthException(String message) {
            super(message);
        }
    }
}
