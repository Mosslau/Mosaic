package com.example;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;

/** Filter 注册：FilterRegistrationBean 显式声明 URL 与顺序（order 越小越靠外，先执行） */
@Configuration
public class FilterConfig {

    @Bean
    public FilterRegistrationBean<DemoFilter> demoFilter() {
        FilterRegistrationBean<DemoFilter> registration = new FilterRegistrationBean<>(new DemoFilter());
        registration.addUrlPatterns("/api/*");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE); // 最外层：先于 DispatcherServlet 与一切拦截器
        return registration;
    }
}
