package com.example;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 第二个拦截器：登录校验的「简化替身」——带 block=true 参数时短路（返回 false）。
 * 教学点：preHandle 返回 false = 请求在此被拦下，后续拦截器与 Controller 都不执行；
 * Spring Security 的 Filter 链拦截（ex06）与此同思想，只是把「拦」做成了框架标准件。
 */
public class SecondInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        OrderRecorder.record("second.pre");
        if ("true".equals(request.getParameter("block"))) {
            response.setStatus(403); // 拦下：无业务响应体（可自行写 JSON，见 ex06 的 403 处理）
            OrderRecorder.record("second.pre.BLOCKED");
            return false;
        }
        return true;
    }

    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response, Object handler,
                           org.springframework.web.servlet.ModelAndView modelAndView) {
        OrderRecorder.record("second.post");
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        OrderRecorder.record("second.after");
    }
}
