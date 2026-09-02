package com.example.msdemo.user;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * user-service 单服务实测（随机端口起真实 HTTP 服务）：
 * 登录签发/失败 40101 / 缺 X-Auth-User 40100 / USER 角色管用户 40300 / ADMIN 建用户后可登录 / health。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class UserServiceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Autowired
    private TestRestTemplate rest;

    private JsonNode bodyOf(ResponseEntity<String> response) throws Exception {
        return MAPPER.readTree(response.getBody());
    }

    private HttpEntity<?> jsonHeaders(String authUser, String role) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (authUser != null) {
            headers.set("X-Auth-User", authUser);
        }
        if (role != null) {
            headers.set("X-Auth-Role", role);
        }
        return new HttpEntity<>(headers);
    }

    @Test
    void loginSuccessIssuesJwtToken() throws Exception {
        ResponseEntity<String> response = rest.postForEntity("/api/auth/login",
                Map.of("username", "admin", "password", "admin123"), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        JsonNode body = bodyOf(response);
        assertThat(body.get("code").asInt()).isEqualTo(0);
        assertThat(body.get("data").get("token").asText().split("\\.")).hasSize(3); // JWT 三段式
        assertThat(body.get("data").get("role").asText()).isEqualTo("ADMIN");
    }

    @Test
    void loginWrongPasswordReturns40101() throws Exception {
        ResponseEntity<String> response = rest.postForEntity("/api/auth/login",
                Map.of("username", "admin", "password", "wrong"), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(401);
        assertThat(bodyOf(response).get("code").asInt()).isEqualTo(40101);
    }

    @Test
    void getUserWithoutAuthHeaderReturns40100() throws Exception {
        ResponseEntity<String> response = rest.getForEntity("/api/users/1", String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(401);
        assertThat(bodyOf(response).get("code").asInt()).isEqualTo(40100);
    }

    @Test
    void listUsersAsUserRoleReturns40300() throws Exception {
        ResponseEntity<String> response = rest.exchange("/api/users", HttpMethod.GET,
                jsonHeaders("alice", "USER"), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(403);
        assertThat(bodyOf(response).get("code").asInt()).isEqualTo(40300);
    }

    @Test
    void getUserByIdWithAuthHeader() throws Exception {
        ResponseEntity<String> response = rest.exchange("/api/users/2", HttpMethod.GET,
                jsonHeaders("alice", "USER"), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        JsonNode body = bodyOf(response);
        assertThat(body.get("code").asInt()).isEqualTo(0);
        assertThat(body.get("data").get("username").asText()).isEqualTo("alice");
        assertThat(body.get("data").has("passwordHash")).isFalse();  // 口令哈希不外泄
    }

    @Test
    void adminCreatesUserAndNewUserCanLogin() throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Auth-User", "admin");
        headers.set("X-Auth-Role", "ADMIN");
        ResponseEntity<String> created = rest.exchange("/api/users", HttpMethod.POST,
                new HttpEntity<>(Map.of("username", "bob", "password", "bob123", "role", "USER"), headers),
                String.class);
        assertThat(created.getStatusCode().value()).isEqualTo(200);
        JsonNode body = bodyOf(created);
        assertThat(body.get("code").asInt()).isEqualTo(0);
        assertThat(body.get("data").get("username").asText()).isEqualTo("bob");

        ResponseEntity<String> login = rest.postForEntity("/api/auth/login",
                Map.of("username", "bob", "password", "bob123"), String.class);
        assertThat(login.getStatusCode().value()).isEqualTo(200);
        assertThat(bodyOf(login).get("data").get("role").asText()).isEqualTo("USER");
    }

    @Test
    void healthEndpointIsUp() throws Exception {
        ResponseEntity<String> response = rest.getForEntity("/actuator/health", String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(bodyOf(response).get("status").asText()).isEqualTo("UP");
    }
}
