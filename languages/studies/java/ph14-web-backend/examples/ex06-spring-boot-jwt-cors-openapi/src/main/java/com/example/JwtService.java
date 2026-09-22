// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/JwtService.java
// —— 用 jjwt 库签发/验签 JWT（对比 ex03 手写版）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0 + jjwt 0.12.5（本机离线 mvn -o 实测）
// 验证状态：已验证（单元测试 + 集成实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：手写（ex03）让你明白 JWT 的签名机制，这里用成熟库 jjwt 看「生产怎么写」——
// 算法、密钥、过期时间都由库管理，API 语义清晰：builder 签发、parser 验签。
// 密钥 32 字节（HS256 要求），生产应放配置/环境变量，不硬编码在代码里。
package com.example;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/** JWT 签发与验签（HS256）。@Component 让它成为 Spring Bean，可注入到控制器/拦截器。 */
@Component
public class JwtService {

    private final SecretKey key;

    public JwtService() {
        // HS256 要求密钥至少 32 字节（256 位）；教学演示硬编码，
        // 生产应从配置/环境变量注入（ph11 讲过配置管理，ph15 讲 Spring 配置）
        this("0123456789abcdef0123456789abcdef");
    }

    public JwtService(String secret) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    /** 签发：sub 放用户名，ttlSeconds 控制有效期。 */
    public String issue(String username, long ttlSeconds) {
        long now = System.currentTimeMillis();
        return Jwts.builder()
                .subject(username)
                .issuedAt(new Date(now))
                .expiration(new Date(now + ttlSeconds * 1000))
                .signWith(key)
                .compact();
    }

    /** 验签并解析：token 非法/过期抛 JwtException（由调用方转 401）。 */
    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
