package com.example.msdemo.gateway.filter;

import com.example.msdemo.common.jwt.JwtService;
import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 网关鉴权过滤器（手写 OncePerRequestFilter，参照 exercises/sol-04 的 JwtAuthFilter）：
 * 除 /api/auth/login（登录端点本身）外，一律要求 Authorization: Bearer &lt;JWT&gt;；
 * 验签通过后把用户名/角色写进 request attribute，供转发控制器注入 X-Auth-User/X-Auth-Role 头给下游。
 * 失败统一 401 + {"code":40100} —— 认证收敛到网关，下游服务不再各自验签（主文档 3.2）。
 * 复用 common 的 JwtService（与 user-service 共享同一 jwt.secret 才能签发/验签互通）。
 */
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final String AUTH_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtService jwtService;

    public JwtAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (request.getRequestURI().startsWith("/api/auth/login")) {
            chain.doFilter(request, response);
            return;
        }
        String header = request.getHeader(AUTH_HEADER);
        if (header == null || !header.startsWith(BEARER_PREFIX)) {
            reject(response, "missing or malformed Authorization header");
            return;
        }
        try {
            Claims claims = jwtService.parse(header.substring(BEARER_PREFIX.length()));
            // 验签成功：身份交给转发控制器注入下游请求头（下游信任网关注入的头）
            request.setAttribute("authUser", claims.getSubject());
            request.setAttribute("authRole", claims.get("role", String.class));
            chain.doFilter(request, response);
        } catch (Exception e) {
            // 篡改/过期/签名不符都抛 JwtException（含子类），统一 40100
            reject(response, "invalid or expired token");
        }
    }

    private void reject(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":40100,\"message\":\"" + message + "\"}");
    }
}
