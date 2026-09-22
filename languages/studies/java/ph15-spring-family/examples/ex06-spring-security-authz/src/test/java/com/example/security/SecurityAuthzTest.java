package com.example.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * ex06 测试：Security 认证 + 授权的分层断言——匿名 401、登录后 200、
 * URL 级 hasRole 403/200、方法级 @PreAuthorize 403/200、BCrypt 存储。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class SecurityAuthzTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserDetailsService userDetailsService;

    private static String basic(String user, String password) {
        String raw = user + ":" + password;
        return "Basic " + Base64.getEncoder().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void publicEndpointNeedsNoAuth() throws Exception {
        mockMvc.perform(get("/public/ping"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("pong"));
    }

    /** 未认证请求被 Filter 链拦下 → 401 + 统一 JSON（自定义 AuthenticationEntryPoint 生效） */
    @Test
    void unauthenticatedGetsCustom401Json() throws Exception {
        mockMvc.perform(get("/api/hello"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100))
                .andExpect(jsonPath("$.message").value("未认证：请携带有效凭证"));
    }

    /** 认证成功：hello 可访问、/api/me 返回用户名与角色 */
    @Test
    void authenticatedUserCanAccessHelloAndMe() throws Exception {
        mockMvc.perform(get("/api/hello").header("Authorization", basic("user", "user123")))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/me").header("Authorization", basic("user", "user123")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("user"))
                .andExpect(jsonPath("$.authorities[0]").value("ROLE_USER"));
    }

    /** 密码错误 → 401（Basic 认证失败由 httpBasic 默认入口处理，返回 401） */
    @Test
    void wrongPasswordIsRejected() throws Exception {
        mockMvc.perform(get("/api/me").header("Authorization", basic("user", "wrong")))
                .andExpect(status().isUnauthorized());
    }

    /** URL 级授权：USER 访问 /api/admin/** → 403 + 统一 JSON（AccessDeniedHandler 生效） */
    @Test
    void userRoleBlockedFromAdminUrlWith403Json() throws Exception {
        mockMvc.perform(get("/api/admin/users").header("Authorization", basic("user", "user123")))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value(40300));
    }

    /** 方法级授权：USER 读书可以，删书被 @PreAuthorize 拦下 403 */
    @Test
    void methodSecurityAllowsReadButBlocksDeleteForUser() throws Exception {
        mockMvc.perform(get("/api/books").header("Authorization", basic("user", "user123")))
                .andExpect(status().isOk());
        mockMvc.perform(delete("/api/books/1").header("Authorization", basic("user", "user123")))
                .andExpect(status().isForbidden());
    }

    /** ADMIN：URL 级与方法级都放行 */
    @Test
    void adminPassesUrlAndMethodAuthorization() throws Exception {
        mockMvc.perform(get("/api/admin/users").header("Authorization", basic("admin", "admin123")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0]").value("admin"));
        mockMvc.perform(delete("/api/books/1").header("Authorization", basic("admin", "admin123")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.deleted").value(1));
    }

    /** 密码以 BCrypt 哈希存储（$2a$ 前缀），绝不明文——loadUserByUsername 查出来的即哈希 */
    @Test
    void passwordsStoredAsBcryptHashes() {
        String stored = userDetailsService.loadUserByUsername("admin").getPassword();
        assertThat(stored).startsWith("$2a$");
        assertThat(stored).doesNotContain("admin123");
    }
}
