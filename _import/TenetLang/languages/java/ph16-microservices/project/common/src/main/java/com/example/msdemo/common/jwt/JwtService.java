package com.example.msdemo.common.jwt;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;

/**
 * JWT 签发/验签（jjwt 0.12.5；按密钥长度自动选 HS 算法——本模块 50 字节密钥实际签发 HS384）。思路参照 ph15 exercises/sol-05，但因本阶段不引入
 * Spring Security（不在离线缓存），这里只是普通工具类：user-service 用它签发，
 * gateway 的 JwtAuthFilter（手写 OncePerRequestFilter）用它验签。
 * 密钥走配置注入（jwt.secret），两个服务必须配同一密钥才能签发/验签互通。
 */
public class JwtService {

    private final SecretKey key;
    private final long ttlHours;

    public JwtService(String secret, long ttlHours) {
        // jjwt 按密钥长度自动选 HS 算法：32–47 字节 → HS256、48–63 → HS384、≥64 → HS512；
        // 本模块 jwt.secret 为 50 字节 → HS384（2026-09-02 实测签发头 {"alg":"HS384"}）。
        // 生产密钥走环境变量注入，绝不写进代码
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttlHours = ttlHours;
    }

    public String issue(String username, String role) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(username)
                .claim("role", role)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttlHours, ChronoUnit.HOURS)))
                .signWith(key)
                .compact();
    }

    /** 验签 + 取 claims；token 非法/过期抛 JwtException，由调用方（网关过滤器）转 40100 */
    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}
