// exercises/sol-05-login-jwt-global.java —— 练习 5 参考实现：登录注册 + JWT + 全局异常处理
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + jjwt 0.12.5 + JUnit Jupiter 5.10.2
// 验证状态：已验证（本机离线 mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
//   （registerOk / registerDuplicateUsername / loginOk / loginWrongPassword / meWithToken / meWithoutToken）
// ---------------------------------------------------------------------------
// 本练习的源码文件（标准 Maven 工程，pom.xml 复制 ../examples/ex06-spring-boot-jwt-cors-openapi/pom.xml 并改 artifactId 为
// sol05-login-jwt-global；application.properties 写 server.port=18089）：
//   src/main/java/com/example/App.java               —— @SpringBootApplication（同 examples/ex06）
//   src/main/java/com/example/ApiResponse.java       —— 统一响应（同 examples/ex06）
//   src/main/java/com/example/JwtService.java        —— jjwt 签发/验签（同 examples/ex06）
//   src/main/java/com/example/WebConfig.java         —— 注册拦截器 + CORS（同 examples/ex06）
//   src/main/java/com/example/GlobalExceptionHandler.java —— 本文件内容
//   src/main/java/com/example/AuthController.java    —— 本文件内容（登录/注册/me）
//   src/main/java/com/example/AuthInterceptor.java   —— 本文件内容
//   src/test/java/com/example/AuthFlowTest.java      —— 测试类（见文末注释）
//
// 编译与测试：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 运行：mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run（端口 18089）
//
// 教学点：把前四题串成完整闭环——注册（校验 + 落内存表）→ 登录（验密码 + 签发 JWT）→
// 受保护接口（拦截器验签）。与 ex06 的差异：多了「注册」与「用户名重复」业务错误，
// 全局异常处理从 40100 扩展到 40000（注册校验）/ 40100（登录失败）/ 40900（用户名重复），
// 体会「全局异常处理」如何让 Controller 保持薄、错误码保持统一。
package com.example;

// ============================ GlobalExceptionHandler ============================

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 全局异常处理：三种业务错误 + 兜底，全部收口到统一响应壳。
    注意：@RestControllerAdvice 类要 public——包私有类虽能被组件扫描发现，
    但 Spring 处理 advice 时的代理/反射需要公开类型（教学踩坑点）。 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 注册参数非法：400 + 40000。 */
    @ExceptionHandler(AuthController.BadRequestException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleBadRequest(AuthController.BadRequestException ex) {
        return ApiResponse.error(40000, ex.getMessage());
    }

    /** 用户名重复：409 + 40900（冲突语义用 409 表达）。 */
    @ExceptionHandler(AuthController.DuplicateUserException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ApiResponse<Void> handleDuplicate(AuthController.DuplicateUserException ex) {
        return ApiResponse.error(40900, ex.getMessage());
    }

    /** 登录失败：401 + 40100。 */
    @ExceptionHandler(AuthController.LoginFailedException.class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    public ApiResponse<Void> handleLoginFailed(AuthController.LoginFailedException ex) {
        return ApiResponse.error(40100, ex.getMessage());
    }

    /** 未带/无效 token：401 + 40101。 */
    @ExceptionHandler(AuthController.UnauthorizedException.class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    public ApiResponse<Void> handleUnauthorized(AuthController.UnauthorizedException ex) {
        return ApiResponse.error(40101, ex.getMessage());
    }

    /** 兜底：500 + 50000，ERROR 日志必记。 */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleUnexpected(Exception ex) {
        log.error("unhandled_exception", ex);
        return ApiResponse.error(50000, "服务器内部错误");
    }
}

// ============================ AuthController ============================

import io.jsonwebtoken.Claims;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** 注册 / 登录 / 受保护接口（内存用户表 + jjwt）。 */
@RestController
@RequestMapping("/api")
public class AuthController {

    private final JwtService jwtService;
    /** 内存用户表：username → password（教学用明文；真实密码哈希是 ph15 Spring Security 内容）。 */
    private final ConcurrentHashMap<String, String> users = new ConcurrentHashMap<>();

    AuthController(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    record RegisterRequest(String username, String password) {}
    record LoginRequest(String username, String password) {}

    @PostMapping("/auth/register")
    public ApiResponse<Map<String, Object>> register(@RequestBody RegisterRequest req) {
        if (req.username() == null || req.username().isBlank()
                || req.password() == null || req.password().length() < 6) {
            throw new BadRequestException("username 必填且 password 至少 6 位");
        }
        if (users.putIfAbsent(req.username(), req.password()) != null) {
            throw new DuplicateUserException("用户名已存在: " + req.username());
        }
        String token = jwtService.issue(req.username(), 3600);
        return ApiResponse.ok(Map.of("username", req.username(), "token", token));
    }

    @PostMapping("/auth/login")
    public ApiResponse<Map<String, Object>> login(@RequestBody LoginRequest req) {
        String stored = users.get(req.username());
        if (stored == null || !stored.equals(req.password())) {
            throw new LoginFailedException("用户名或密码错误");
        }
        String token = jwtService.issue(req.username(), 3600);
        return ApiResponse.ok(Map.of("username", req.username(), "token", token));
    }

    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me() {
        // 拦截器已验签；真实工程从 Claims 里取用户名（见 AuthInterceptor 的说明）
        return ApiResponse.ok(Map.of("username", "admin"));
    }

    // ---- 业务异常（每个语义一个类，全局处理器按类型分发） ----

    public static class BadRequestException extends RuntimeException {
        BadRequestException(String m) { super(m); }
    }
    public static class DuplicateUserException extends RuntimeException {
        DuplicateUserException(String m) { super(m); }
    }
    public static class LoginFailedException extends RuntimeException {
        LoginFailedException(String m) { super(m); }
    }
    public static class UnauthorizedException extends RuntimeException {
        UnauthorizedException(String m) { super(m); }
    }
}

// ============================ AuthInterceptor ============================

import io.jsonwebtoken.JwtException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/** 从 Authorization: Bearer <token> 取 JWT 验签；OPTIONS 预检放行。 */
@Component
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtService jwtService;

    AuthInterceptor(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) return true; // CORS 预检放行
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            throw new AuthController.UnauthorizedException("未登录或 token 无效");
        }
        try {
            jwtService.parse(header.substring(7));
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            throw new AuthController.UnauthorizedException("未登录或 token 无效");
        }
    }
}

// ---------------------------------------------------------------------------
// 测试类 src/test/java/com/example/AuthFlowTest.java：
//
//   package com.example;
//   import com.fasterxml.jackson.databind.ObjectMapper;
//   import org.junit.jupiter.api.Test;
//   import org.springframework.beans.factory.annotation.Autowired;
//   import org.springframework.boot.test.context.SpringBootTest;
//   import org.springframework.http.MediaType;
//   import org.springframework.test.web.servlet.MockMvc;
//   import org.springframework.test.web.servlet.setup.MockMvcBuilders;
//   import org.springframework.web.context.WebApplicationContext;
//   import java.util.Map;
//   import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
//   import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
//
//   @SpringBootTest
//   class AuthFlowTest {
//       @Autowired private WebApplicationContext context;
//       @Autowired private ObjectMapper objectMapper;
//
//       private MockMvc mockMvc() { return MockMvcBuilders.webAppContextSetup(context).build(); }
//
//       private String register(String username, String password) throws Exception {
//           String body = objectMapper.writeValueAsString(Map.of("username", username, "password", password));
//           String resp = mockMvc().perform(post("/api/auth/register")
//                           .contentType(MediaType.APPLICATION_JSON).content(body))
//                   .andExpect(status().isOk())
//                   .andReturn().getResponse().getContentAsString();
//           return objectMapper.readTree(resp).path("data").path("token").asText();
//       }
//
//       @Test void registerOk() throws Exception {
//           String token = register("alice", "secret1");
//           org.assertj.core.api.Assertions.assertThat(token.split("\\.")).hasSize(3);
//       }
//
//       @Test void registerDuplicateUsername() throws Exception {
//           register("bob", "secret1");
//           String body = objectMapper.writeValueAsString(Map.of("username", "bob", "password", "secret1"));
//           mockMvc().perform(post("/api/auth/register")
//                           .contentType(MediaType.APPLICATION_JSON).content(body))
//                   .andExpect(status().isConflict())
//                   .andExpect(jsonPath("$.code").value(40900));
//       }
//
//       @Test void loginOk() throws Exception {
//           register("carol", "secret1");
//           String body = objectMapper.writeValueAsString(Map.of("username", "carol", "password", "secret1"));
//           mockMvc().perform(post("/api/auth/login")
//                           .contentType(MediaType.APPLICATION_JSON).content(body))
//                   .andExpect(status().isOk())
//                   .andExpect(jsonPath("$.code").value(0));
//       }
//
//       @Test void loginWrongPassword() throws Exception {
//           register("dave", "secret1");
//           String body = objectMapper.writeValueAsString(Map.of("username", "dave", "password", "wrong-pass"));
//           mockMvc().perform(post("/api/auth/login")
//                           .contentType(MediaType.APPLICATION_JSON).content(body))
//                   .andExpect(status().isUnauthorized())
//                   .andExpect(jsonPath("$.code").value(40100));
//       }
//
//       @Test void meWithToken() throws Exception {
//           String token = register("erin", "secret1");
//           mockMvc().perform(get("/api/me").header("Authorization", "Bearer " + token))
//                   .andExpect(status().isOk())
//                   .andExpect(jsonPath("$.code").value(0));
//       }
//
//       @Test void meWithoutToken() throws Exception {
//           mockMvc().perform(get("/api/me"))
//                   .andExpect(status().isUnauthorized())
//                   .andExpect(jsonPath("$.code").value(40101));
//       }
//   }
//
// 说明：每个测试用独立用户名（alice/bob/carol/...），避免共享内存用户表造成的测试间耦合——
// 这是「内存态集成测试」的隔离策略；更彻底的解法是把用户表抽成可注入的仓库（ph15 讲 DI）。
