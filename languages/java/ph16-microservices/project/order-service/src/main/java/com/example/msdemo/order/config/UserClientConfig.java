package com.example.msdemo.order.config;

import com.example.msdemo.common.trace.TraceIdClientInterceptor;
import com.example.msdemo.order.client.UserClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * 远程调用客户端装配（OpenFeign 的同构手写版，机制见主文档 3.2；Feign 不在离线缓存）：
 * 显式连接/读超时是微服务调用的底线——不设超时会被慢下游拖死线程池（主文档 3.3），
 * 复用 common 的 TraceIdClientInterceptor 把当前线程 MDC 里的 traceId 透传给 user-service。
 * order-service 只对 user-service 发 GET（读），无需担心 POST+401 的 HttpRetryException 踩坑
 * （那是 gateway 转发登录 POST 的问题，gateway 用 JdkClientHttpRequestFactory 规避，见 sol-04）。
 */
@Configuration
public class UserClientConfig {

    @Bean
    RestClient userRestClient(@Value("${user-service.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(500));   // 连不上：快速失败（测试用随机端口，5xx/拒连都覆盖）
        factory.setReadTimeout(Duration.ofMillis(1000));     // 读不动：快速失败
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .requestInterceptor(new TraceIdClientInterceptor())   // X-Trace-Id 透传
                .build();
    }

    @Bean
    UserClient userClient(RestClient userRestClient) {
        return new UserClient(userRestClient);
    }
}
