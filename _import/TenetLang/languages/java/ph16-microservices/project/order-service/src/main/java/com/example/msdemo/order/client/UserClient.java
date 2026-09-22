package com.example.msdemo.order.client;

import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import com.example.msdemo.common.trace.TraceIdFilter;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * user-service 的远程客户端（OpenFeign 的同构手写版，机制见主文档 3.2）。
 * 失败语义显式建模（对照 examples/ex01 的 UserClient）：
 *  - 404（确定答案：用户不存在）→ 抛 {@link BizException} 40400，不降级不重试（4xx 重试无意义，主文档 4.1）
 *  - 其它非 2xx → {@link DownstreamException}（下游病了，交 Controller 降级）
 *  - 连接/读超时 → {@link DownstreamTimeoutException}（同样交 Controller 降级）
 * 身份透传：把入口收到的 X-Auth-User 头原样转发给 user-service——网关注入的信任头
 * （与 user-service「网关内侧信任注入头」模型一致），保证 user-service 侧能过鉴权。
 */
public class UserClient {

    private final RestClient restClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public UserClient(RestClient restClient) {
        this.restClient = restClient;
    }

    /**
     * 远程取用户名。成功返回 {@link UserCall}（用户名 + 下游实际见到的 traceId，链路透传证据）；
     * 用户不存在抛 40400；下游故障/超时抛异常由 Controller 降级为占位用户名。
     */
    public UserCall findUser(long userId, String authUser) {
        try {
            return restClient.get().uri("/api/users/{id}", userId)
                    .header("X-Auth-User", authUser)   // 身份头透传：网关 → order-service → user-service
                    .exchange((request, response) -> {
                        String downstreamTraceId = response.getHeaders().getFirst(TraceIdFilter.HEADER);
                        int status = response.getStatusCode().value();
                        if (status == 404) {
                            // 确定答案：这个用户不存在（不是服务故障）→ 40400 透传，不降级
                            throw new BizException(BizCodes.NOT_FOUND, "user not found: " + userId);
                        }
                        if (status >= 400) {
                            // 其它错误（5xx/4xx 异常码）→ 下游不可用语义，交 Controller 降级
                            throw new DownstreamException("user-service", status);
                        }
                        String body = response.bodyTo(String.class);
                        JsonNode root = objectMapper.readTree(body);
                        String username = root.path("data").path("username").asText();
                        return new UserCall(username, downstreamTraceId);
                    });
        } catch (ResourceAccessException e) {
            // 连接超时/读超时/连接被拒都落到 ResourceAccessException（cause 是 SocketTimeoutException/ConnectException）
            throw new DownstreamTimeoutException("user-service", e);
        }
    }
}
