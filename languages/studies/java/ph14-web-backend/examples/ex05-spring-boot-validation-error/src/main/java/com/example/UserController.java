// examples/ex05-spring-boot-validation-error/src/main/java/com/example/UserController.java —— @Valid 参数校验
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + spring-boot-starter-validation（Hibernate Validator 8.0.1.Final）
// 验证状态：已验证（MockMvc 测试 + spring-boot:run + curl 实测，见 README）
// 实测结果（curl 直测，端口 18085）：
//   POST /api/users（合法 body）→ 200 {"code":0,"message":"ok","data":{"id":1,"name":"Alice","email":"alice@example.com"}}
//   POST /api/users（name 空白 + email 非法）→ 400 {"code":40001,"message":"参数校验失败","data":{"email":"email 格式不正确","name":"name 不能为空"}}
//   POST /api/users（name 长度超限）→ 400 {"code":40001,...}
// ---------------------------------------------------------------------------
// 教学点：声明式校验——在 record 字段上贴 @NotBlank/@Email/@Size 注解，@Valid 触发校验，
// 失败抛 MethodArgumentNotValidException，由全局异常处理器（GlobalExceptionHandler）统一转成响应。
// 这是「参数校验」话题的框架实现：对比 ex01 里手写 if (name == null || name.isBlank())，
// 声明式把校验规则和数据模型放一起，Controller 里不再出现校验 if 代码。
package com.example;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private static final Logger log = LoggerFactory.getLogger(UserController.class);

    /** 请求体 DTO：校验注解直接声明在字段上（@NotBlank 空串也拒绝，@Email 格式校验）。 */
    public record CreateUserRequest(
            @NotBlank(message = "name 不能为空")
            @Size(max = 20, message = "name 最长 20 字符")
            String name,
            @NotBlank(message = "email 不能为空")
            @Email(message = "email 格式不正确")
            String email) {}

    public record User(long id, String name, String email) {}

    /** 内存用户表（教学演示；真实数据层在 ph13 数据库阶段）。 */
    private final ConcurrentHashMap<Long, User> store = new ConcurrentHashMap<>();
    private final AtomicLong seq = new AtomicLong(1);

    @PostMapping
    public ApiResponse<User> create(@Valid @RequestBody CreateUserRequest req) {
        User user = new User(seq.getAndIncrement(), req.name(), req.email());
        store.put(user.id(), user);
        log.info("create_user id={} name={}", user.id(), user.name());
        return ApiResponse.ok(user);
    }
}
