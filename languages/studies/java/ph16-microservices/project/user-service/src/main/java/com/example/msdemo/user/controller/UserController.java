package com.example.msdemo.user.controller;

import com.example.msdemo.common.api.ApiResponse;
import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import com.example.msdemo.user.dto.CreateUserRequest;
import com.example.msdemo.user.dto.UserDto;
import com.example.msdemo.user.service.UserService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 用户端点。鉴权模型：服务位于网关内侧，信任网关注入的 X-Auth-User / X-Auth-Role 头
 * （内网信任边界——生产环境应配网络隔离/mTLS，绝不可把服务直接暴露给外网）。
 */
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping("/{id}")
    public ApiResponse<UserDto> getById(@PathVariable long id,
                                        @RequestHeader(value = "X-Auth-User", required = false) String authUser) {
        requireAuthenticated(authUser);
        return ApiResponse.ok(userService.findById(id));
    }

    @GetMapping
    public ApiResponse<List<UserDto>> list(@RequestHeader(value = "X-Auth-User", required = false) String authUser,
                                           @RequestHeader(value = "X-Auth-Role", required = false) String role) {
        requireAdmin(authUser, role);
        return ApiResponse.ok(userService.list());
    }

    @PostMapping
    public ApiResponse<UserDto> create(@RequestHeader(value = "X-Auth-User", required = false) String authUser,
                                       @RequestHeader(value = "X-Auth-Role", required = false) String role,
                                       @RequestBody CreateUserRequest request) {
        requireAdmin(authUser, role);
        return ApiResponse.ok(userService.create(request.username(), request.password(), request.role()));
    }

    private void requireAuthenticated(String authUser) {
        if (authUser == null || authUser.isBlank()) {
            throw new BizException(BizCodes.UNAUTHENTICATED, "missing X-Auth-User header");
        }
    }

    private void requireAdmin(String authUser, String role) {
        requireAuthenticated(authUser);
        if (!"ADMIN".equals(role)) {
            throw new BizException(BizCodes.FORBIDDEN, "admin role required");
        }
    }
}
