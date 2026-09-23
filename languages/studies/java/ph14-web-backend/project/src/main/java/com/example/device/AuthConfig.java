// project/src/main/java/com/example/device/AuthConfig.java —— JWT 登录与 CORS 配置（项目级）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + jjwt 0.12.5（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：生产级上报 API 需要「谁在报」——登录接口签发 JWT，上报接口带 token。
// 认证（你是谁）本阶段用 jjwt + 拦截器解决；授权（你能报哪台设备）是 ph15 Spring Security 内容。
// 密钥放常量仅教学演示，生产走配置/环境变量（ph15 讲 Spring 配置）。
package com.example.device;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

/** 认证（JWT 签发/验签）、拦截器注册与 CORS 配置。 */
@Configuration
public class AuthConfig implements WebMvcConfigurer {

    private static final SecretKey KEY =
            Keys.hmacShaKeyFor("0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8));

    /** 登录：演示用固定账号（真实密码哈希与用户库是 ph15 内容）。 */
    @RestController
    @RequestMapping("/api/auth")
    public static class LoginController {
        public record LoginRequest(String username, String password) {}

        @PostMapping("/login")
        public ResponseEntity<ApiResponse<Map<String, String>>> login(@RequestBody LoginRequest req) {
            if ("demo".equals(req.username()) && "demo123".equals(req.password())) {
                String token = Jwts.builder()
                        .subject(req.username())
                        .issuedAt(new Date())
                        .expiration(new Date(System.currentTimeMillis() + 3600_000))
                        .signWith(KEY)
                        .compact();
                return ResponseEntity.ok(ApiResponse.ok(Map.of("token", token, "username", req.username())));
            }
            // 密码错 → HTTP 401 + 业务码 40100（与 ex06 及「401 未认证」语义一致）
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(40100, "用户名或密码错误"));
        }
    }

    /** 拦截器：/api/devices/** 需要 Bearer token（登录接口除外）。 */
    public static class JwtInterceptor implements HandlerInterceptor {
        @Override
        public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
                throws Exception {
            if ("OPTIONS".equalsIgnoreCase(request.getMethod())) return true; // CORS 预检放行
            String header = request.getHeader("Authorization");
            if (header == null || !header.startsWith("Bearer ")) {
                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                response.setContentType("application/json; charset=UTF-8");
                response.getWriter().write("{\"code\":40101,\"message\":\"未登录或 token 无效\",\"data\":null}");
                return false;
            }
            try {
                Claims claims = Jwts.parser().verifyWith(KEY).build()
                        .parseSignedClaims(header.substring(7)).getPayload();
                request.setAttribute("username", claims.getSubject());
                return true;
            } catch (Exception e) {
                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                response.setContentType("application/json; charset=UTF-8");
                response.getWriter().write("{\"code\":40101,\"message\":\"未登录或 token 无效\",\"data\":null}");
                return false;
            }
        }
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new JwtInterceptor())
                .addPathPatterns("/api/devices/**")
                .excludePathPatterns("/api/auth/login");
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("http://localhost:5173")
                .allowedMethods("GET", "POST", "OPTIONS")
                .allowedHeaders("*");
    }
}
