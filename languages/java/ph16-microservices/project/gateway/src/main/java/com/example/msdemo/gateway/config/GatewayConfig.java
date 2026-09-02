package com.example.msdemo.gateway.config;

import com.example.msdemo.common.jwt.JwtService;
import com.example.msdemo.common.trace.TraceIdClientInterceptor;
import com.example.msdemo.common.trace.TraceIdFilter;
import com.example.msdemo.gateway.filter.JwtAuthFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;

/**
 * 网关装配：
 * 1. JwtService：与 user-service 同一 jwt.secret 才能验签互通（真实部署密钥走配置中心/环境变量共享）
 * 2. TraceIdFilter（order=1）+ JwtAuthFilter（order=2）：先透传 traceId 再鉴权，
 *    401 响应也带 X-Trace-Id 方便定位
 * 3. 两个下游 RestClient（user-service / order-service）：转发必须用 JdkClientHttpRequestFactory——
 *    SimpleClientHttpRequestFactory（HttpURLConnection）在 POST + 下游 401 时抛 HttpRetryException
 *    （已实测，见 exercises/sol-04）；拦截器把 MDC 里的 traceId 透传给下游服务
 */
@Configuration
public class GatewayConfig {

    @Bean
    JwtService jwtService(@Value("${jwt.secret}") String secret,
                          @Value("${jwt.ttl-hours:2}") long ttlHours) {
        return new JwtService(secret, ttlHours);
    }

    @Bean
    FilterRegistrationBean<TraceIdFilter> traceIdFilter() {
        FilterRegistrationBean<TraceIdFilter> registration = new FilterRegistrationBean<>(new TraceIdFilter());
        registration.setOrder(1);
        registration.addUrlPatterns("/*");
        return registration;
    }

    @Bean
    FilterRegistrationBean<JwtAuthFilter> jwtAuthFilter(JwtService jwtService) {
        FilterRegistrationBean<JwtAuthFilter> registration =
                new FilterRegistrationBean<>(new JwtAuthFilter(jwtService));
        registration.setOrder(2);
        registration.addUrlPatterns("/api/*");   // 只保护业务 API，actuator 留给探活
        return registration;
    }

    @Bean
    RestClient userServiceClient(@Value("${downstream.user-service.base-url}") String baseUrl) {
        return downstreamClient(baseUrl);
    }

    @Bean
    RestClient orderServiceClient(@Value("${downstream.order-service.base-url}") String baseUrl) {
        return downstreamClient(baseUrl);
    }

    private RestClient downstreamClient(String baseUrl) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(500))   // 连不上：快速失败
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofMillis(2000));  // 读不动：快速失败（比下游聚合链路留余量）
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .requestInterceptor(new TraceIdClientInterceptor())   // X-Trace-Id 透传
                .build();
    }
}
