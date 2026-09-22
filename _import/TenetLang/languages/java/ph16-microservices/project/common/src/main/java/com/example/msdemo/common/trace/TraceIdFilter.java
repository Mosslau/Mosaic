package com.example.msdemo.common.trace;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * 链路追踪的最小同构实现（与 examples/ex01 相同语义）：每个入口请求携带/生成 X-Trace-Id，
 * 写入 MDC（日志可打印）与响应头（调用方可核对），供下游 RestClient 拦截器继续透传。
 * 生产等价物是 Micrometer Tracing / OpenTelemetry（离线缓存缺其 jar，本类演示同一语义）。
 * 普通类而非 @Component：由各服务用 FilterRegistrationBean 显式注册并控制顺序。
 */
public class TraceIdFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Trace-Id";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String traceId = request.getHeader(HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString();   // 入口服务生成
        }
        MDC.put("traceId", traceId);
        response.setHeader(HEADER, traceId);
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove("traceId");
        }
    }
}
