package com.example.msdemo.gateway.controller;

import com.example.msdemo.common.api.ApiResponse;
import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

/**
 * 手写 mini 网关的转发控制器（Spring Cloud Gateway 的同构教学版——真实 Gateway 不在离线缓存，
 * Route/Predicate/Filter 机制见主文档 3.2）。路由表即「谓词 → 目标」：
 *   /api/auth/**、/api/users/** → user-service（登录 + 用户管理）
 *   /api/orders/**              → order-service（订单聚合）
 * 按方法/路径/query 原样转发，并把 JwtAuthFilter 验签得到的身份注入 X-Auth-User/X-Auth-Role 头，
 * 下游服务信任该头（内网信任边界）不再各自验签。
 * 踩坑（已实测，见 exercises/sol-04 文件头）：转发客户端必须用 JdkClientHttpRequestFactory——
 * SimpleClientHttpRequestFactory（HttpURLConnection）在 POST + 下游 401 时抛 HttpRetryException，
 * 表现为登录密码错误时网关 500 而非透传下游的 40101。
 */
@RestController
public class GatewayProxyController {

    private final RestClient userServiceClient;
    private final RestClient orderServiceClient;

    public GatewayProxyController(RestClient userServiceClient, RestClient orderServiceClient) {
        this.userServiceClient = userServiceClient;
        this.orderServiceClient = orderServiceClient;
    }

    @RequestMapping("/api/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request,
                                        @RequestBody(required = false) byte[] body) {
        String path = request.getRequestURI();   // 含 /api 前缀；下游服务本身就以 /api/... 暴露，无需 StripPrefix
        RestClient target = route(path);
        String uri = request.getQueryString() == null
                ? path
                : path + "?" + request.getQueryString();
        HttpMethod method = HttpMethod.valueOf(request.getMethod());
        var spec = target.method(method).uri(uri).headers(headers -> {
            // 注入验签得到的身份（不转发客户端自带的 X-Auth-*，防止伪造身份头直达下游）
            String authUser = (String) request.getAttribute("authUser");
            String authRole = (String) request.getAttribute("authRole");
            if (authUser != null) {
                headers.set("X-Auth-User", authUser);
            }
            if (authRole != null) {
                headers.set("X-Auth-Role", authRole);
            }
            headers.setContentType(MediaType.APPLICATION_JSON);
        });
        if (body != null && (method == HttpMethod.POST || method == HttpMethod.PUT || method == HttpMethod.PATCH)) {
            spec.body(body);
        }
        return spec.exchange((req, res) -> ResponseEntity.status(res.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(res.bodyTo(byte[].class)));
    }

    /** 路由表：路径前缀谓词 → 下游服务（真实 Spring Cloud Gateway 用 Path=/api/orders/** 声明式表达同一条规则） */
    private RestClient route(String path) {
        if (path.startsWith("/api/orders")) {
            return orderServiceClient;
        }
        if (path.startsWith("/api/auth") || path.startsWith("/api/users")) {
            return userServiceClient;
        }
        throw new BizException(BizCodes.NOT_FOUND, "no route for " + path);
    }
}
