package com.example.rbac;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 认证端点：登录（校验 + AuthenticationManager + 发 JWT）、当前用户 */
@RestController
@RequestMapping("/api")
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtService jwtService;

    public AuthController(AuthenticationManager authenticationManager, JwtService jwtService) {
        this.authenticationManager = authenticationManager;
        this.jwtService = jwtService;
    }

    /** 登录：@Valid 先拦空参数（400），AuthenticationManager 再验密码（失败 40101） */
    @PostMapping("/auth/login")
    public ApiResponse<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.username(), request.password()));
        String role = authentication.getAuthorities().iterator().next().getAuthority().replace("ROLE_", "");
        String token = jwtService.issue(authentication.getName(), role);
        return ApiResponse.ok(Map.of(
                "token", token,
                "username", authentication.getName(),
                "role", role));
    }

    /** 当前登录用户信息（带 token 访问；Filter 已认证） */
    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me(Authentication authentication) {
        List<String> authorities = authentication.getAuthorities().stream().map(Object::toString).toList();
        return ApiResponse.ok(Map.of("username", authentication.getName(), "authorities", authorities));
    }

    /** 登录请求体：@NotBlank 由 starter-validation 提供实现（ph14 参数校验升级为框架 Bean Validation） */
    public record LoginRequest(
            @NotBlank(message = "username 不能为空") String username,
            @NotBlank(message = "password 不能为空") String password) {
    }
}
