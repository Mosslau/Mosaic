package com.example.rbac;

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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * project 验收测试：登录发 JWT → 带 token 访问 → 角色授权（URL 级）→ 用户 CRUD
 * （校验 400 / 重名 409 / 非法角色 400 / 删除后登录 401）。HSQLDB 内存库随上下文启动，
 * AdminSeed 造出 admin/admin123；各测试用唯一用户名互不干扰。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class RbacApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private String login(String username, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}"))
                .andReturn();
        if (result.getResponse().getStatus() != 200) {
            return null;
        }
        return objectMapper.readTree(result.getResponse().getContentAsString()).get("data").get("token").asText();
    }

    /** 种子 admin 登录成功，token 三段式 */
    @Test
    void seededAdminCanLogin() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"admin123\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.role").value("ADMIN"))
                .andExpect(jsonPath("$.data.token").isNotEmpty());
    }

    /** 登录参数校验：空 username/password → 400 + 业务码 40001 */
    @Test
    void blankLoginFieldsAreRejected400() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"\",\"password\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40001));
    }

    /** 密码错误 → 401 + 业务码 40101 */
    @Test
    void wrongPasswordGets40101() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"wrong\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40101));
    }

    /** 无 token → 401 + 40100（Security Filter 层统一 JSON） */
    @Test
    void noTokenGets40100() throws Exception {
        mockMvc.perform(get("/api/users"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(40100));
    }

    /** admin 登录后能列出用户（种子 admin 在列表里），密码字段不外泄 */
    @Test
    void adminListsUsersWithoutPasswords() throws Exception {
        String token = login("admin", "admin123");
        assertThat(token).isNotNull();
        mockMvc.perform(get("/api/users").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data[0].username").value("admin"))
                .andExpect(jsonPath("$.data[0].password").doesNotExist());
    }

    /** admin 创建 USER bob → bob 能登录但访问 /api/users 被 403（URL 级授权） */
    @Test
    void createdUserCannotListUsers() throws Exception {
        String adminToken = login("admin", "admin123");
        String bob = "bob" + System.nanoTime() % 100000;
        mockMvc.perform(post("/api/users")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "username", bob, "password", "bob123456", "role", "USER", "displayName", "Bob"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.username").value(bob))
                .andExpect(jsonPath("$.data.role").value("USER"));

        String bobToken = login(bob, "bob123456");
        assertThat(bobToken).isNotNull(); // bob 登录成功（认证 OK）
        mockMvc.perform(get("/api/users").header("Authorization", "Bearer " + bobToken))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value(40300)); // 但授权不通过
    }

    /** 重复用户名 → 409 + 40901 */
    @Test
    void duplicateUsernameGets40901() throws Exception {
        String adminToken = login("admin", "admin123");
        mockMvc.perform(post("/api/users")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"whatever123\",\"role\":\"USER\",\"displayName\":\"x\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value(40901));
    }

    /** 非法角色 → 400 + 40002 */
    @Test
    void illegalRoleGets40002() throws Exception {
        String adminToken = login("admin", "admin123");
        mockMvc.perform(post("/api/users")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"mallory\",\"password\":\"pass123456\",\"role\":\"ROOT\",\"displayName\":\"x\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40002));
    }

    /** admin 删除用户 → 该用户再登录 401（账号随删除失效） */
    @Test
    void deletedUserCannotLoginAnymore() throws Exception {
        String adminToken = login("admin", "admin123");
        String victim = "victim" + System.nanoTime() % 100000;
        mockMvc.perform(post("/api/users")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "username", victim, "password", "victim123456", "role", "USER", "displayName", "V"))))
                .andExpect(status().isOk());
        MvcResult created = mockMvc.perform(get("/api/users").header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk()).andReturn();
        // 列表里按用户名挑 victim 的 id
        long id = -1;
        var arr = objectMapper.readTree(created.getResponse().getContentAsString()).get("data");
        for (var node : arr) {
            if (victim.equals(node.get("username").asText())) {
                id = node.get("id").asLong();
            }
        }
        assertThat(id).isGreaterThan(0);
        mockMvc.perform(delete("/api/users/" + id).header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk());
        assertThat(login(victim, "victim123456")).isNull(); // 删除后登录失败
    }

    /** /api/me 返回当前登录人与角色 */
    @Test
    void meReturnsCurrentUser() throws Exception {
        String token = login("admin", "admin123");
        mockMvc.perform(get("/api/me").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.username").value("admin"))
                .andExpect(jsonPath("$.data.authorities[0]").value("ROLE_ADMIN"));
    }
}
