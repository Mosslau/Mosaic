// exercises/sol-04-gateway-auth.java —— 练习 4 参考实现：网关鉴权（手写 mini 网关 + JWT）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + jjwt 0.12.5（离线缓存内）
// 验证状态：已验证（本机离线 mvn -o -Dmaven.repo.local=/tmp/m2clone test，BUILD SUCCESS）
// 实测结果：Tests run: 5, Failures: 0, Errors: 0
//   （loginReturnsThreePartJwt：token 三段式 / validTokenPassesGatewayAndReachesDownstreamWithIdentity：
//     网关验签后注入 X-Auth-User，下游实测见到 "alice" / missingTokenGets401WithUnifiedCode：
//     401 code 40100 / tamperedTokenGets401 / wrongPasswordGets40101）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex01-service-split-restcall/pom.xml 并追加
//   jjwt-api/jjwt-impl/jjwt-jackson 0.12.5 三坐标——与 ph15 exercises/sol-05 相同，artifactId 改
//   sol04-gateway-auth；用户服务跑 18325、网关跑 18326）+ 下列文件。
//   验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 教学点：认证收敛到网关（验签一次），下游服务信任网关注入的身份头——这就是 Spring Cloud Gateway
//   + 认证过滤器的同构手写版（真实 Gateway 不在离线缓存，机制见主文档 3.2）。踩坑记录：转发客户端
//   必须用 JdkClientHttpRequestFactory——SimpleClientHttpRequestFactory（HttpURLConnection）在
//   POST + 下游 401 时抛「cannot retry due to server authentication, in streaming mode」（已实测复现）。

// =============================================================================
// src/main/java/com/example/gatewaydemo/JwtSupport.java
// =============================================================================

package com.example.gatewaydemo;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;

/** JWT 签发/校验工具：用户服务签发，网关验签（同一密钥——生产环境通过配置中心共享） */
public final class JwtSupport {

    private JwtSupport() {
    }

    private static SecretKey key(String secret) {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    public static String issue(String secret, String username, String role) {
        return Jwts.builder()
                .subject(username)
                .claim("role", role)
                .issuedAt(new Date())
                .expiration(Date.from(Instant.now().plus(2, ChronoUnit.HOURS)))
                .signWith(key(secret))
                .compact();
    }

    /** 验签 + 过期检查；失败抛 io.jsonwebtoken.JwtException */
    public static Claims parse(String secret, String token) {
        return Jwts.parser().verifyWith(key(secret)).build().parseSignedClaims(token).getPayload();
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/gateway/GatewayApp.java
// =============================================================================

package com.example.gatewaydemo.gateway;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;

/** 练习 4 的网关（默认端口 18326）：JWT 鉴权过滤器 + 路由转发 */
@SpringBootApplication
public class GatewayApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(GatewayApp.class)
                .properties("server.port=18326")
                .run(args);
    }

    @Bean
    JwtAuthFilter jwtAuthFilter(@Value("${jwt.secret}") String jwtSecret) {
        return new JwtAuthFilter(jwtSecret);
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/gateway/GatewayProxyController.java
// =============================================================================

package com.example.gatewaydemo.gateway;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;

/**
 * 手写 mini 网关的转发控制器（Spring Cloud Gateway 的同构教学版——真实 Gateway 不在离线缓存）：
 * 按方法/路径/query 原样转发到用户服务，并注入网关注入的 X-Auth-User / X-Auth-Role 头。
 * 注意用 JdkClientHttpRequestFactory：SimpleClientHttpRequestFactory（HttpURLConnection）
 * 在 POST + 下游 401 时会抛「cannot retry due to server authentication, in streaming mode」。
 */
@RestController
public class GatewayProxyController {

    private final RestClient downstream;

    public GatewayProxyController(@Value("${downstream.user-service.base-url}") String baseUrl) {
        HttpClient httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(500)).build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofMillis(1000));
        this.downstream = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }

    @RequestMapping("/api/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request,
                                        @RequestBody(required = false) byte[] body) {
        String uri = request.getQueryString() == null
                ? request.getRequestURI()
                : request.getRequestURI() + "?" + request.getQueryString();
        HttpMethod method = HttpMethod.valueOf(request.getMethod());
        var spec = downstream.method(method).uri(uri).headers(headers -> {
            String authUser = (String) request.getAttribute("authUser");
            String authRole = (String) request.getAttribute("authRole");
            if (authUser != null) {
                headers.set("X-Auth-User", authUser);
            }
            if (authRole != null) {
                headers.set("X-Auth-Role", authRole);
            }
            headers.setContentType(MediaType.APPLICATION_JSON);
        });
        if (body != null && (method == HttpMethod.POST || method == HttpMethod.PUT || method == HttpMethod.PATCH)) {
            spec.body(body);
        }
        return spec.exchange((req, res) -> ResponseEntity.status(res.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(res.bodyTo(byte[].class)));
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/gateway/JwtAuthFilter.java
// =============================================================================

package com.example.gatewaydemo.gateway;

import com.example.gatewaydemo.JwtSupport;
import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 网关鉴权过滤器：除 /api/auth/login 外一律验 Bearer JWT，
 * 验过把用户名/角色写进 request attribute（转发控制器据此注入 X-Auth-User 头给下游）。
 * 失败统一 401 {"code":40100} —— 认证集中在网关，下游服务不再各自验签。
 */
public class JwtAuthFilter extends OncePerRequestFilter {

    private final String jwtSecret;

    public JwtAuthFilter(String jwtSecret) {
        this.jwtSecret = jwtSecret;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (request.getRequestURI().startsWith("/api/auth/login")) {
            chain.doFilter(request, response);
            return;
        }
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            reject(response, "缺少 Authorization Bearer 头");
            return;
        }
        try {
            Claims claims = JwtSupport.parse(jwtSecret, header.substring(7));
            request.setAttribute("authUser", claims.getSubject());
            request.setAttribute("authRole", claims.get("role", String.class));
            chain.doFilter(request, response);
        } catch (Exception e) {
            reject(response, "token 无效或已过期");
        }
    }

    private void reject(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":40100,\"message\":\"" + message + "\"}");
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/userside/AuthController.java
// =============================================================================

package com.example.gatewaydemo.userside;

import com.example.gatewaydemo.JwtSupport;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 登录端点：校验账号密码（示例内存账号），签发 JWT。密码错 → 40101 */
@RestController
public class AuthController {

    private static final Map<String, String[]> ACCOUNTS = Map.of(
            "alice", new String[]{"alice123", "USER"},
            "admin", new String[]{"admin123", "ADMIN"});

    private final String jwtSecret;

    public AuthController(@Value("${jwt.secret}") String jwtSecret) {
        this.jwtSecret = jwtSecret;
    }

    @PostMapping("/api/auth/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String[] account = ACCOUNTS.get(username);
        if (account == null || !account[0].equals(body.get("password"))) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("code", 40101, "message", "用户名或密码错误"));
        }
        String token = JwtSupport.issue(jwtSecret, username, account[1]);
        return ResponseEntity.ok(Map.of("code", 0, "message", "ok",
                "data", Map.of("token", token, "username", username, "role", account[1])));
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/userside/UserQueryController.java
// =============================================================================

package com.example.gatewaydemo.userside;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 用户查询端点：回显网关注入的 X-Auth-User 头（证明网关鉴权结果传到了下游） */
@RestController
public class UserQueryController {

    @GetMapping("/api/users/{id}")
    public Map<String, Object> get(@PathVariable long id,
                                   @RequestHeader(value = "X-Auth-User", required = false) String authUser) {
        return Map.of("id", id, "name", "用户" + id, "authUserSeen", authUser == null ? "" : authUser);
    }
}

// =============================================================================
// src/main/java/com/example/gatewaydemo/userside/UserServiceApp.java
// =============================================================================

package com.example.gatewaydemo.userside;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 练习 4 的用户服务（默认端口 18325）：登录签 JWT + 用户信息查询 */
@SpringBootApplication
public class UserServiceApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(UserServiceApp.class)
                .properties("server.port=18325")
                .run(args);
    }
}

// =============================================================================
// src/main/resources/application.properties
// =============================================================================

# 用户服务与网关共用（同模块 classpath）；生产环境密钥走配置中心/环境变量
jwt.secret=ph16-sol04-gateway-demo-secret-key-32bytes!!
downstream.user-service.base-url=http://localhost:18325
logging.level.com.example=INFO

// =============================================================================
// src/test/java/com/example/gatewaydemo/GatewayAuthTest.java
// =============================================================================

package com.example.gatewaydemo;

import com.example.gatewaydemo.gateway.GatewayApp;
import com.example.gatewaydemo.userside.UserServiceApp;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 网关鉴权实测：登录签发 → 网关验签转发 → 下游见到注入身份；无 token / 篡改 token → 401 */
class GatewayAuthTest {

    private static ConfigurableApplicationContext userApp;
    private static ConfigurableApplicationContext gatewayApp;
    private static RestClient gateway;

    @BeforeAll
    static void start() {
        userApp = new SpringApplicationBuilder(UserServiceApp.class).run("--server.port=0");
        int userPort = ((WebServerApplicationContext) userApp).getWebServer().getPort();
        gatewayApp = new SpringApplicationBuilder(GatewayApp.class)
                .run("--server.port=0", "--downstream.user-service.base-url=http://localhost:" + userPort);
        int gatewayPort = ((WebServerApplicationContext) gatewayApp).getWebServer().getPort();
        gateway = RestClient.create("http://localhost:" + gatewayPort);
    }

    @AfterAll
    static void stop() {
        gatewayApp.close();
        userApp.close();
    }

    private String login(String username, String password) {
        Map<?, ?> response = gateway.post().uri("/api/auth/login")
                .body(Map.of("username", username, "password", password))
                .retrieve().body(Map.class);
        Map<?, ?> data = (Map<?, ?>) response.get("data");
        return (String) data.get("token");
    }

    @Test
    void loginReturnsThreePartJwt() {
        String token = login("alice", "alice123");
        assertThat(token.split("\\.")).hasSize(3);   // header.payload.signature
    }

    @Test
    void validTokenPassesGatewayAndReachesDownstreamWithIdentity() {
        String token = login("alice", "alice123");
        Map<?, ?> body = gateway.get().uri("/api/users/1")
                .header("Authorization", "Bearer " + token)
                .retrieve().body(Map.class);
        assertThat(body.get("name")).isEqualTo("用户1");
        assertThat(body.get("authUserSeen")).isEqualTo("alice");   // 网关注入的身份头到达下游
    }

    @Test
    void missingTokenGets401WithUnifiedCode() {
        var snapshot = gateway.get().uri("/api/users/1")
                .exchange((req, res) -> new Object[]{res.getStatusCode().value(), res.bodyTo(String.class)});
        assertThat(snapshot[0]).isEqualTo(401);
        assertThat((String) snapshot[1]).contains("40100");
    }

    @Test
    void tamperedTokenGets401() {
        String token = login("alice", "alice123");
        var status = gateway.get().uri("/api/users/1")
                .header("Authorization", "Bearer " + token + "tampered")
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(401);
    }

    @Test
    void wrongPasswordGets40101() {
        var snapshot = gateway.post().uri("/api/auth/login")
                .body(Map.of("username", "alice", "password", "wrong"))
                .exchange((req, res) -> new Object[]{res.getStatusCode().value(), res.bodyTo(String.class)});
        assertThat(snapshot[0]).isEqualTo(401);
        assertThat((String) snapshot[1]).contains("40101");
    }
}
