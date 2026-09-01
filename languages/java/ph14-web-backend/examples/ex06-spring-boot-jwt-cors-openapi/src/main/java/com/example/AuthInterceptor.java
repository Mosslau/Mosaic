// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/AuthInterceptor.java
// —— JWT 鉴权拦截器（HandlerInterceptor）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + jjwt 0.12.5（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试 + curl 实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：HandlerInterceptor 是 Spring MVC 的「过滤器」——preHandle 在 Controller
// 执行前跑，这里做 token 验签；失败抛异常由全局异常处理器转 401。
// 对比 ex01 的 HttpServer Filter：同一思想（横切关注点），不同实现层。
package com.example;

import io.jsonwebtoken.JwtException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/** 从 Authorization: Bearer <token> 头里取 JWT 并验签。 */
@Component
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtService jwtService;

    public AuthInterceptor(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        // CORS 预检（OPTIONS）不携带 Authorization 头，交给 CORS 处理器应答，拦截器直接放行
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            throw new AuthController.AuthException("未登录或 token 无效");
        }
        String token = header.substring(7);
        try {
            jwtService.parse(token); // 验签 + 过期检查（JwtException 表示非法）
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            throw new AuthController.AuthException("未登录或 token 无效");
        }
    }
}
