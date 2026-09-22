package com.example.orderservice;

import com.example.common.TraceIdFilter;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/** user-service 的远程客户端：状态码 → 业务异常，IO/超时 → 超时异常（失败语义在调用方显式建模） */
public class UserClient {

    private final RestClient restClient;

    public UserClient(RestClient restClient) {
        this.restClient = restClient;
    }

    public UserCall findUser(long userId) {
        try {
            return restClient.get().uri("/users/{id}", userId).exchange((request, response) -> {
                String downstreamTrace = response.getHeaders().getFirst(TraceIdFilter.HEADER);
                if (response.getStatusCode().value() == 404) {
                    throw new UserNotFoundException(userId);
                }
                if (response.getStatusCode().isError()) {
                    throw new DownstreamException("user-service", response.getStatusCode().value());
                }
                return new UserCall(response.bodyTo(com.example.userservice.UserDto.class), downstreamTrace);
            });
        } catch (ResourceAccessException e) {
            // 连接超时/读超时都落到 ResourceAccessException（cause 是 SocketTimeoutException/ConnectException）
            throw new DownstreamTimeoutException("user-service", e);
        }
    }
}
