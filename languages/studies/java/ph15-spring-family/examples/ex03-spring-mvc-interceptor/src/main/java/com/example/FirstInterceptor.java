package com.example;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 第一个拦截器：请求计时（afterCompletion 打印耗时）+ 记录执行阶段。
 * 注册顺序 = 第一个 → preHandle 最先、postHandle/afterCompletion 最后（栈式收尾）。
 */
public class FirstInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(FirstInterceptor.class);
    private final ThreadLocal<Long> start = new ThreadLocal<>();

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        OrderRecorder.record("first.pre");
        start.set(System.nanoTime());
        // handler 是 HandlerMethod 时能拿到「即将调用的 Controller 方法」——拦截器在 MVC 层，看得见方法级信息
        if (handler instanceof HandlerMethod hm) {
            log.info("first.pre -> 目标方法 {}#{}", hm.getBeanType().getSimpleName(), hm.getMethod().getName());
        }
        return true;
    }

    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response, Object handler,
                           org.springframework.web.servlet.ModelAndView modelAndView) {
        OrderRecorder.record("first.post");
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        OrderRecorder.record("first.after");
        long elapsedMs = (System.nanoTime() - start.get()) / 1_000_000;
        log.info("first.after -> 耗时 {} ms（ex={}）", elapsedMs, ex);
        start.remove(); // ThreadLocal 必须清理，防线程池复用串数据
    }
}
