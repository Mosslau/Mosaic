package com.example;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;

import java.io.IOException;

/**
 * Servlet Filter：包在 DispatcherServlet 外层（先于一切拦截器）。
 * Filter 看不到「要调哪个 Controller 方法」（它只见到 URL/Servlet），
 * Interceptor 看得到（HandlerMethod）——这是两者定位差异的核心。
 */
public class DemoFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        OrderRecorder.record("filter.before");
        chain.doFilter(request, response); // 放行：进 DispatcherServlet → 拦截器链 → Controller
        OrderRecorder.record("filter.after");
    }
}
