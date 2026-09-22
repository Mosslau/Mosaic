package com.example.rbac;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 用户管理端点（URL 级已要求 ADMIN，见 SecurityConfig）：
 * Controller 只做 HTTP 语义与参数校验，业务（查重/加密/删除）全在 UserService。
 */
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ApiResponse<List<UserView>> list() {
        return ApiResponse.ok(userService.listAll().stream().map(UserView::from).toList());
    }

    /** 创建用户：@Valid 拦空参数；重名 → 409；角色非法 → 400 */
    @PostMapping
    public ApiResponse<UserView> create(@Valid @RequestBody CreateUserRequest request) {
        User user = userService.create(request.username(), request.password(), request.role(), request.displayName());
        return ApiResponse.ok(UserView.from(user));
    }

    /** 删除用户（仅 ADMIN；URL 级 + 这里是业务入口） */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        userService.delete(id);
        return ApiResponse.ok(null);
    }

    /** 列表视图：绝不外泄 password 字段 */
    public record UserView(Long id, String username, String role, String displayName) {
        static UserView from(User user) {
            return new UserView(user.getId(), user.getUsername(), user.getRole(), user.getDisplayName());
        }
    }

    public record CreateUserRequest(
            @NotBlank(message = "username 不能为空")
            @Size(min = 3, max = 50, message = "username 长度 3~50")
            String username,
            @NotBlank(message = "password 不能为空")
            @Size(min = 6, max = 50, message = "password 长度 6~50")
            String password,
            @NotBlank(message = "role 不能为空") String role,
            @NotBlank(message = "displayName 不能为空") String displayName) {
    }
}
