package com.example.msdemo.user.controller;

import com.example.msdemo.common.api.ApiResponse;
import com.example.msdemo.common.jwt.JwtService;
import com.example.msdemo.user.domain.AppUser;
import com.example.msdemo.user.dto.LoginRequest;
import com.example.msdemo.user.dto.LoginResponse;
import com.example.msdemo.user.service.UserService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 认证端点：登录签发 JWT（2 小时过期，secret 走配置）。此端点本身不需要鉴权。 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final UserService userService;
    private final JwtService jwtService;

    public AuthController(UserService userService, JwtService jwtService) {
        this.userService = userService;
        this.jwtService = jwtService;
    }

    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@RequestBody LoginRequest request) {
        AppUser user = userService.authenticate(request.username(), request.password());
        String token = jwtService.issue(user.username(), user.role());
        return ApiResponse.ok(new LoginResponse(token, user.username(), user.role()));
    }
}
