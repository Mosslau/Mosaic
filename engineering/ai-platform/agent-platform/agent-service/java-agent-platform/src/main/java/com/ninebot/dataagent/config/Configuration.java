package com.ninebot.dataagent.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.web.client.RestClient;

/** Spring 基础 Bean 配置。 */
@org.springframework.context.annotation.Configuration
@EnableConfigurationProperties(AgentProperties.class)
public class Configuration {
    @org.springframework.context.annotation.Bean
    RestClient pythonRuntimeRestClient(RestClient.Builder builder, AgentProperties properties) {
        return builder.baseUrl(properties.getRuntime().getBaseUrl()).build();
    }
}
