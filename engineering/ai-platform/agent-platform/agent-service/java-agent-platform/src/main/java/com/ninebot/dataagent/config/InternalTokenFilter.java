package com.ninebot.dataagent.config;

import com.ninebot.dataagent.service.HmacRequestSigner;
import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** HMAC authentication for Java Gateway inbound calls, with local token migration fallback. */
@Component
public class InternalTokenFilter extends OncePerRequestFilter {
    private static final Set<String> PROTECTED_PREFIXES = Set.of(
            "/internal/runtime", "/internal/mcp", "/mcp", "/internal/sandboxes");
    private final AgentProperties properties;
    private final StringRedisTemplate redis;

    public InternalTokenFilter(AgentProperties properties, StringRedisTemplate redis) {
        this.properties = properties;
        this.redis = redis;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (PROTECTED_PREFIXES.stream().noneMatch(path::startsWith)) {
            chain.doFilter(request, response);
            return;
        }

        Credentials credentials = credentialsFor(path);
        if (credentials.complete()) {
            byte[] body = request.getInputStream().readAllBytes();
            boolean valid = HmacRequestSigner.verify(
                    request.getHeader("X-Signature"), request.getMethod(), path,
                    request.getQueryString(), body, request.getHeader("X-Access-Key"),
                    request.getHeader("X-Timestamp"), request.getHeader("X-Nonce"),
                    request.getHeader("X-Content-SHA256"), credentials.secretKey());
            if (!valid || !HmacRequestSigner.VERSION.equals(request.getHeader("X-Signature-Version"))) {
                reject(response, "INVALID_INTERNAL_SIGNATURE", "invalid internal HMAC signature");
                return;
            }
            String nonceKey = "agent:auth:nonce:" + credentials.accessKey() + ":"
                    + request.getHeader("X-Nonce");
            try {
                Boolean claimed = redis.opsForValue().setIfAbsent(
                        nonceKey, "1", java.time.Duration.ofSeconds(300));
                if (!Boolean.TRUE.equals(claimed)) {
                    reject(response, "REPLAYED_INTERNAL_NONCE", "request nonce has already been used");
                    return;
                }
            } catch (RuntimeException exception) {
                reject(response, "INTERNAL_REPLAY_PROTECTION_UNAVAILABLE", "replay protection unavailable");
                return;
            }
            chain.doFilter(new CachedBodyRequest(request, body), response);
            return;
        }

        String expected = properties.getGateway().getInternalToken();
        String supplied = request.getHeader("X-Internal-Service-Token");
        if (supplied == null || expected == null || !constantTimeEquals(expected, supplied)) {
            reject(response, "INVALID_INTERNAL_SERVICE_TOKEN", "invalid internal service credential");
            return;
        }
        chain.doFilter(request, response);
    }

    private Credentials credentialsFor(String path) {
        if (path.startsWith("/internal/sandboxes")) {
            var sandbox = properties.getGateway().getSandbox();
            return new Credentials(sandbox.getAccessKey(), sandbox.getSecretKey());
        }
        return new Credentials(properties.getGateway().getAccessKey(), properties.getGateway().getSecretKey());
    }

    private static boolean constantTimeEquals(String left, String right) {
        return java.security.MessageDigest.isEqual(
                left.getBytes(StandardCharsets.UTF_8), right.getBytes(StandardCharsets.UTF_8));
    }

    private static void reject(HttpServletResponse response, String code, String message)
            throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":\"" + code + "\",\"message\":\"" + message + "\"}");
    }

    private record Credentials(String accessKey, String secretKey) {
        boolean complete() { return accessKey != null && !accessKey.isBlank() && secretKey != null && !secretKey.isBlank(); }
    }

    private static final class CachedBodyRequest extends HttpServletRequestWrapper {
        private final byte[] body;
        CachedBodyRequest(HttpServletRequest request, byte[] body) { super(request); this.body = body; }
        @Override public ServletInputStream getInputStream() {
            return new ServletInputStream() {
                private final java.io.ByteArrayInputStream input = new java.io.ByteArrayInputStream(body);
                @Override public int read() { return input.read(); }
                @Override public boolean isFinished() { return input.available() == 0; }
                @Override public boolean isReady() { return true; }
                @Override public void setReadListener(ReadListener listener) { }
            };
        }
        @Override public BufferedReader getReader() {
            return new BufferedReader(new java.io.InputStreamReader(getInputStream(), StandardCharsets.UTF_8));
        }
        @Override public int getContentLength() { return body.length; }
        @Override public long getContentLengthLong() { return body.length; }
    }
}
