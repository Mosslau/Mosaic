package com.example.msdemo.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 网关入口（默认端口 18313）。
 * 职责（主文档 3.2，Spring Cloud Gateway 的同构手写版——真实 Gateway 不在离线缓存，机制见主文档）：
 * 1. JWT 验签过滤器：除 /api/auth/login 外一律验 Bearer token，验过把身份写进 request attribute
 * 2. 转发控制器：按路径路由到 user-service / order-service，并把验签得到的 X-Auth-User/X-Auth-Role
 *    注入下游请求头（认证收敛到网关，下游不再各自验签）
 * 3. X-Trace-Id 全链路透传（TraceIdFilter + RestClient 拦截器）
 */
@SpringBootApplication
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
