package com.example.ordersaga;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/** account-service 客户端装配：显式超时（调用链路上每一跳都不能裸奔） */
@Configuration
public class AccountClientConfig {

    @Bean
    RestClient accountRestClient(@Value("${account-service.base-url}") String baseUrl) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(500));
        factory.setReadTimeout(Duration.ofMillis(800));
        return RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }

    @Bean
    AccountClient accountClient(RestClient accountRestClient) {
        return new AccountClient(accountRestClient);
    }
}
