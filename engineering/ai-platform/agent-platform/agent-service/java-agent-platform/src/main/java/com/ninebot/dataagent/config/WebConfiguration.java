package com.ninebot.dataagent.config;

import java.util.Arrays;
import java.util.List;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 本地前端联调 CORS 配置。
 *
 * <p>生产环境应通过 WEB_ALLOWED_ORIGINS 设置实际前端域名，不能继续使用默认的本地端口。</p>
 */
@Configuration
public class WebConfiguration implements WebMvcConfigurer {
    private final List<String> allowedOrigins;

    public WebConfiguration() {
        String value = System.getenv().getOrDefault("WEB_ALLOWED_ORIGINS",
                "http://127.0.0.1:5500,http://localhost:5500");
        allowedOrigins = Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(item -> !item.isBlank())
                .toList();
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(allowedOrigins.toArray(String[]::new))
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("Content-Type", "Accept", "Last-Event-ID")
                .allowCredentials(false)
                .maxAge(3600);
    }
}
