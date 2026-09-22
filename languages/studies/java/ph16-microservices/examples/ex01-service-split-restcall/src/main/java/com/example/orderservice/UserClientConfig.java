package com.example.orderservice;

import com.example.common.TraceIdClientInterceptor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * 远程调用客户端装配（OpenFeign 的同构手写版，Feign 不在离线缓存、机制见主文档 3.2）：
 * 显式连接/读超时是微服务调用的底线——roadmap 必会概念「远程调用必须有超时和降级」。
 */
@Configuration
public class UserClientConfig {

    @Bean
    RestClient userRestClient(@Value("${user-service.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(500));   // 连不上：快速失败
        factory.setReadTimeout(Duration.ofMillis(800));      // 读不动：快速失败（慢用户 sleep 1500ms 会触发）
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .requestInterceptor(new TraceIdClientInterceptor())   // TraceId 透传
                .build();
    }

    @Bean
    UserClient userClient(RestClient userRestClient) {
        return new UserClient(userRestClient);
    }
}
