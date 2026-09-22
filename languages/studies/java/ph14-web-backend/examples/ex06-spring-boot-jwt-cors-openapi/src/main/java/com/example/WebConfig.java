// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/WebConfig.java
// —— 注册拦截器 + CORS 配置
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（curl 实测 CORS 预检，见 README）
// 实测结果（curl 直测，端口 18086）：
//   OPTIONS /api/me（Origin: http://localhost:5173）→ 200，响应头
//     Access-Control-Allow-Origin: http://localhost:5173
//     Access-Control-Allow-Methods: GET, POST, OPTIONS
//   GET /api/me 带 Origin 头 → 响应含 Access-Control-Allow-Origin（CORS 头实测）
// ---------------------------------------------------------------------------
// 教学点：CORS（跨域资源共享）解决「浏览器里前端(http://localhost:5173) 调后端 API
// (http://localhost:18086) 被同源策略拦」的问题。两种配置方式：
//   ① 注解 @CrossOrigin 加在单个 Controller/方法上（粒度细）
//   ② 本文件的全局 CORS 配置（统一管，推荐）——允许的源/方法/头显式声明。
// 注意：Allow-Origin 配 * 表示任意源，带凭证（cookie）时不允许用 *（见 3.7）。
// 拦截器注册：addInterceptors 里 addPathPatterns 声明哪些路径需要鉴权。
package com.example;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final AuthInterceptor authInterceptor;

    public WebConfig(AuthInterceptor authInterceptor) {
        this.authInterceptor = authInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // /api/me 需要 JWT；登录接口 /api/auth/login 放行（不然没人能登录）
        registry.addInterceptor(authInterceptor)
                .addPathPatterns("/api/me");
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("http://localhost:5173") // 前端开发服务器地址
                .allowedMethods("GET", "POST", "OPTIONS")
                .allowedHeaders("*");
    }
}
