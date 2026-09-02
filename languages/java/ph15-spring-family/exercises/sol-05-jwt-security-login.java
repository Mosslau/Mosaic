// exercises/sol-05-jwt-security-login.java —— 练习 5 参考实现：Spring Security + JWT 无状态登录认证
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + Spring Security 6.3.4 + jjwt 0.12.5
// 验证状态：已验证（本机离线 mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 7, Failures: 0, Errors: 0
//   （loginIssuesJwtToken：user/user123 登录 → 200，token 三段式；wrongPasswordGets401；
//     noTokenGetsCustom401Json：401 {"code":40100,...}；validTokenAccessesMe；
//     userRoleBlockedFromAdminUrl：403 {"code":40300,...}；adminTokenPassesUrlAuthorization；
//     garbageTokenGets401）
//   运行实录（spring-boot:run 端口 18105）：admin 登录 → token（172 字符）；
//     GET /api/me 带 Bearer → {"authorities":["ROLE_ADMIN"],"username":"admin"}；
//     GET /api/admin/users → ["admin","operator"]；无 token → 401 统一 JSON
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex06-spring-security-authz/pom.xml 并追加
//   jjwt-api/jjwt-impl/jjwt-jackson 0.12.5 三坐标，artifactId 改 sol05-jwt-login，端口 18105）+ 下列文件。
//   验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 教学点：把 ph14「Controller 拦截器验 JWT」升级为 Security 原生认证——自定义 OncePerRequestFilter
//   插进 SecurityFilterChain，验签通过写 SecurityContext；认证（filter 验 JWT）与授权（URL hasRole /
//   方法 @PreAuthorize）从此由框架统一管理；对比 ex06 的 HTTP Basic：JWT 无状态、不发密码、
//   可跨服务共享（ph16 微服务阶段 JWT 仍是事实标准）。
// ===========================================================================
// src/main/resources/application.properties
// ===========================================================================
server.port=18105
jwt.secret=sol05-demo-secret-key-change-me-0123456789abcdef-32bytes!
jwt.ttl-hours=2
logging.level.com.example=INFO

// ===========================================================================
// src/main/java/com/example/jwtauth/SecurityJwtApp.java
// ===========================================================================
package com.example.jwtauth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SecurityJwtApp {

    public static void main(String[] args) {
        SpringApplication.run(SecurityJwtApp.class, args);
    }
}

// ===========================================================================
// src/main/java/com/example/jwtauth/JwtService.java
// ===========================================================================
package com.example.jwtauth;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;

/** JWT 签发/验签（jjwt 0.12.x）：登录成功后发 token，每次请求由 JwtAuthFilter 验签 */
@Service
public class JwtService {

    private final SecretKey key;
    private final long ttlHours;

    public JwtService(@Value("${jwt.secret}") String secret,
                      @Value("${jwt.ttl-hours:2}") long ttlHours) {
        // HS256 要求密钥 ≥ 256 bit（32 字节）；生产密钥走环境变量注入，绝不写进代码
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttlHours = ttlHours;
    }

    public String issue(String username, String role) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(username)
                .claim("role", role)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttlHours, ChronoUnit.HOURS)))
                .signWith(key)
                .compact();
    }

    /** 验签 + 取 claims；token 非法/过期抛 JwtException 由过滤器转 401 */
    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}

// ===========================================================================
// src/main/java/com/example/jwtauth/JwtAuthFilter.java
// ===========================================================================
package com.example.jwtauth;

import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * 无状态认证过滤器：每个请求解析 Authorization: Bearer <jwt>，
 * 验签通过就把 Authentication 塞进 SecurityContext（后续授权判定读它）。
 * 教学点：这就是「把 ph14 的拦截器验 JWT 升级为 Security 认证」的接缝——
 * Security 的 Filter 链里插一个自定义过滤器，认证/授权框架其余部分原样复用。
 */
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;

    public JwtAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            try {
                var claims = jwtService.parse(header.substring(7));
                String role = claims.get("role", String.class);
                var auth = new UsernamePasswordAuthenticationToken(
                        claims.getSubject(), null,
                        List.of(new SimpleGrantedAuthority("ROLE_" + role)));
                SecurityContextHolder.getContext().setAuthentication(auth);
            } catch (JwtException | IllegalArgumentException ex) {
                SecurityContextHolder.clearContext(); // 非法/过期 token：当作未认证
            }
        }
        chain.doFilter(request, response);
    }
}

// ===========================================================================
// src/main/java/com/example/jwtauth/SecurityConfig.java
// ===========================================================================
package com.example.jwtauth;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/** Security 配置：登录端点放行，其余全认证；JwtAuthFilter 插在用户名密码过滤器之前 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtAuthFilter jwtAuthFilter,
                                                   ObjectMapper mapper) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/auth/login").permitAll()
                        .requestMatchers("/api/admin/**").hasRole("ADMIN")
                        .anyRequest().authenticated())
                .exceptionHandling(e -> e
                        .authenticationEntryPoint((req, res, ex) ->
                                JsonErrors.write(res, mapper, 401, 40100, "未认证或 token 无效"))
                        .accessDeniedHandler((req, res, ex) ->
                                JsonErrors.write(res, mapper, 403, 40300, "无权限：需要 ADMIN 角色")))
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    /** 登录用：AuthenticationManager 走 DaoAuthenticationProvider（内存用户 + BCrypt） */
    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration configuration) throws Exception {
        return configuration.getAuthenticationManager();
    }

    @Bean
    public UserDetailsService userDetailsService(PasswordEncoder encoder) {
        var admin = User.withUsername("admin").password(encoder.encode("admin123")).roles("ADMIN").build();
        var user = User.withUsername("user").password(encoder.encode("user123")).roles("USER").build();
        return new InMemoryUserDetailsManager(admin, user);
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}

// ===========================================================================
// src/main/java/com/example/jwtauth/AuthController.java
// ===========================================================================
package com.example.jwtauth;

import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 登录 + 当前用户端点：登录成功后由 JwtService 发 token */
@RestController
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtService jwtService;

    public AuthController(AuthenticationManager authenticationManager, JwtService jwtService) {
        this.authenticationManager = authenticationManager;
        this.jwtService = jwtService;
    }

    /** 登录：AuthenticationManager 验密码（比对 BCrypt）→ 发 JWT */
    @PostMapping("/api/auth/login")
    public Map<String, Object> login(@RequestBody LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.username(), request.password()));
        // 认证通过：取用户角色拼 ROLE_（与 authorities 的 ROLE_ 前缀一致）
        String role = authentication.getAuthorities().iterator().next()
                .getAuthority().replace("ROLE_", "");
        String token = jwtService.issue(authentication.getName(), role);
        return Map.of("token", token, "username", authentication.getName(), "role", role);
    }

    /** 当前用户：过滤器已把 Authentication 放进 SecurityContext */
    @GetMapping("/api/me")
    public Map<String, Object> me(Authentication authentication) {
        List<String> authorities = authentication.getAuthorities().stream().map(Object::toString).toList();
        return Map.of("username", authentication.getName(), "authorities", authorities);
    }

    @GetMapping("/api/admin/users")
    public List<String> adminUsers() {
        return List.of("admin", "operator"); // URL 级 hasRole('ADMIN')
    }

    /** 登录请求体（用户名/密码） */
    public record LoginRequest(String username, String password) {
    }
}

// ===========================================================================
// src/main/java/com/example/jwtauth/JsonErrors.java
// ===========================================================================
package com.example.jwtauth;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.LinkedHashMap;

/** 401/403 统一 JSON（同 examples/ex06 的 JsonErrors） */
public final class JsonErrors {

    private JsonErrors() {
    }

    public static void write(HttpServletResponse response, ObjectMapper mapper, int httpStatus, int code, String message)
            throws IOException {
        response.setStatus(httpStatus);
        response.setContentType("application/json;charset=UTF-8");
        var body = new LinkedHashMap<String, Object>();
        body.put("code", code);
        body.put("message", message);
        body.put("data", null);
        mapper.writeValue(response.getWriter(), body);
    }
}

// ===========================================================================
// src/test/java/com/example/jwtauth/JwtLoginTest.java
// ===========================================================================
package com.example.jwtauth;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * sol-05 测试：登录发 JWT → 带 token 访问 → 角色授权（401/403 统一 JSON）。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class JwtLoginTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private String loginAndGetToken(String username, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("username", username, "password", password))))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString()).get("token").asText();
    }

    @Test
    void loginIssuesJwtToken() throws Exception {
        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"user\",\"password\":\"user123\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("user"))
                .andExpect(jsonPath("$.role").value("USER"))
                .andReturn();
        String token = objectMapper.readTree(result.getResponse().getContentAsString()).get("token").asText();
        assertThat(token.split("\\.")).hasSize(3); // Header.Payload.Signature
    }

    @Test
    void wrongPasswordGets401() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"user\",\"password\":\"wrong\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void noTokenGetsCustom401Json() throws Exception {
        mockMvc.perform(get("/api/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100));
    }

    @Test
    void validTokenAccessesMe() throws Exception {
        String token = loginAndGetToken("user", "user123");
        mockMvc.perform(get("/api/me").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("user"))
                .andExpect(jsonPath("$.authorities[0]").value("ROLE_USER"));
    }

    @Test
    void userRoleBlockedFromAdminUrl() throws Exception {
        String token = loginAndGetToken("user", "user123");
        mockMvc.perform(get("/api/admin/users").header("Authorization", "Bearer " + token))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value(40300));
    }

    @Test
    void adminTokenPassesUrlAuthorization() throws Exception {
        String token = loginAndGetToken("admin", "admin123");
        mockMvc.perform(get("/api/admin/users").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0]").value("admin"));
    }

    @Test
    void garbageTokenGets401() throws Exception {
        mockMvc.perform(get("/api/me").header("Authorization", "Bearer not.a.jwt"))
                .andExpect(status().isUnauthorized());
    }
}

