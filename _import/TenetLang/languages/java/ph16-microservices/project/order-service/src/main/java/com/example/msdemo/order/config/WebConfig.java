package com.example.msdemo.order.config;

import com.example.msdemo.common.trace.TraceIdFilter;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 装配：TraceIdFilter（order=1，最先进入；入口生成/接力 X-Trace-Id 并写 MDC，
 * 供 UserClient 的 TraceIdClientInterceptor 透传到 user-service）。
 * order-service 不签发/验签 JWT（认证收敛在网关，见主文档 3.2），故无需 JwtService。
 */
@Configuration
public class WebConfig {

    @Bean
    FilterRegistrationBean<TraceIdFilter> traceIdFilter() {
        FilterRegistrationBean<TraceIdFilter> registration = new FilterRegistrationBean<>(new TraceIdFilter());
        registration.setOrder(1);
        registration.addUrlPatterns("/*");
        return registration;
    }
}
