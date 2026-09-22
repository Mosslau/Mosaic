// exercises/sol-01-user-service.java —— 练习 1 参考实现：独立用户服务（roadmap ph16 练习：用户服务）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0（starter-web/actuator/test 离线缓存内）
// 验证状态：已验证（本机离线 mvn -o -Dmaven.repo.local=/tmp/m2clone test，BUILD SUCCESS）
// 实测结果：Tests run: 4, Failures: 0, Errors: 0
//   （createAndGet：创建后按 id 查回 / duplicateNameGets409：重名 409 code 40901 /
//     missingUserGets404：404 code 40400 / listAndHealth：列表含新用户 + /actuator/health UP）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程（pom 复制 ../examples/ex01-service-split-restcall/pom.xml，
//   artifactId 改 sol01-user-service，运行端口 18321）+ 下列文件。
//   验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
//   运行命令：mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run（端口 18321）
// 教学点：把 ph15 单体里的「用户模块」拆成独立服务——独立进程、独立端口、独立数据（内存 Map 代替
//   独立库），对外只剩 HTTP 契约。微服务拆分的第一课：服务边界 = 进程边界 + 数据边界。

// =============================================================================
// src/main/java/com/example/usersvc/User.java
// =============================================================================

package com.example.usersvc;

/** 用户记录（内存存储） */
public record User(long id, String name, String city) {
}

// =============================================================================
// src/main/java/com/example/usersvc/UserController.java
// =============================================================================

package com.example.usersvc;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/** 用户 CRUD 端点：内存存储 + 统一错误码（40400 不存在 / 40901 重名） */
@RestController
public class UserController {

    private final Map<Long, User> users = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(0);

    @PostMapping("/users")
    public ResponseEntity<?> create(@RequestBody Map<String, String> body) {
        String name = body.get("name");
        if (name == null || name.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("code", 40001, "message", "name 不能为空"));
        }
        boolean duplicated = users.values().stream().anyMatch(u -> u.name().equals(name));
        if (duplicated) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("code", 40901, "message", "用户名已存在: " + name));
        }
        User user = new User(idGen.incrementAndGet(), name, body.getOrDefault("city", ""));
        users.put(user.id(), user);
        return ResponseEntity.status(HttpStatus.CREATED).body(user);
    }

    @GetMapping("/users/{id}")
    public ResponseEntity<?> get(@PathVariable long id) {
        User user = users.get(id);
        if (user == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("code", 40400, "message", "用户不存在 id=" + id));
        }
        return ResponseEntity.ok(user);
    }

    @GetMapping("/users")
    public List<User> list() {
        return users.values().stream().sorted(Comparator.comparingLong(User::id)).toList();
    }
}

// =============================================================================
// src/main/java/com/example/usersvc/UserServiceApp.java
// =============================================================================

package com.example.usersvc;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/** 练习 1：独立用户服务（默认端口 18321） */
@SpringBootApplication
public class UserServiceApp {

    public static void main(String[] args) {
        new SpringApplicationBuilder(UserServiceApp.class)
                .properties("server.port=18321")
                .run(args);
    }
}

// =============================================================================
// src/main/resources/application.properties
// =============================================================================

management.endpoints.web.exposure.include=health
logging.level.com.example=INFO

// =============================================================================
// src/test/java/com/example/usersvc/UserServiceTest.java
// =============================================================================

package com.example.usersvc;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class UserServiceTest {

    private static ConfigurableApplicationContext app;
    private static RestClient client;

    @BeforeAll
    static void start() {
        app = new SpringApplicationBuilder(UserServiceApp.class).run("--server.port=0");
        int port = ((WebServerApplicationContext) app).getWebServer().getPort();
        client = RestClient.create("http://localhost:" + port);
    }

    @AfterAll
    static void stop() {
        app.close();
    }

    @Test
    void createAndGet() {
        User created = client.post().uri("/users")
                .body(Map.of("name", "王五", "city", "深圳"))
                .retrieve().body(User.class);
        assertThat(created.id()).isPositive();
        User fetched = client.get().uri("/users/" + created.id()).retrieve().body(User.class);
        assertThat(fetched.name()).isEqualTo("王五");
        assertThat(fetched.city()).isEqualTo("深圳");
    }

    @Test
    void duplicateNameGets409() {
        client.post().uri("/users").body(Map.of("name", "重复甲")).retrieve().body(User.class);
        var status = client.post().uri("/users").body(Map.of("name", "重复甲"))
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(409);
    }

    @Test
    void missingUserGets404() {
        var status = client.get().uri("/users/9999")
                .exchange((req, res) -> res.getStatusCode().value());
        assertThat(status).isEqualTo(404);
    }

    @Test
    void listAndHealth() {
        client.post().uri("/users").body(Map.of("name", "列表甲")).retrieve().body(User.class);
        List<User> users = client.get().uri("/users")
                .retrieve().body(new ParameterizedTypeReference<>() {
                });
        assertThat(users).isNotEmpty();
        assertThat(users.stream().map(User::name)).contains("列表甲");
        Map<?, ?> health = client.get().uri("/actuator/health").retrieve().body(Map.class);
        assertThat(health.get("status")).isEqualTo("UP");
    }
}
