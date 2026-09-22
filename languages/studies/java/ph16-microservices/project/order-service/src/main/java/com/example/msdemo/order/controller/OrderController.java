package com.example.msdemo.order.controller;

import com.example.msdemo.common.api.ApiResponse;
import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import com.example.msdemo.order.client.DownstreamException;
import com.example.msdemo.order.client.DownstreamTimeoutException;
import com.example.msdemo.order.client.UserCall;
import com.example.msdemo.order.client.UserClient;
import com.example.msdemo.order.domain.Order;
import com.example.msdemo.order.dto.OrderDetail;
import com.example.msdemo.order.service.OrderService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 订单聚合端点（参照 examples/ex01 的 OrderController）：本地订单数据 + 远程用户名。
 * 信任模型与 user-service 一致：order-service 位于网关内侧，信任网关注入的 X-Auth-User 头，
 * 并把该身份头原样透传给 user-service（内网信任边界，生产应配网络隔离/mTLS）。
 * 失败语义（主文档 3.3「有损服务」）：订单不存在 → 40400；用户不存在（下游 404，确定答案）
 * → 40400 透传不降级；用户服务故障/超时（不确定故障）→ 降级：HTTP 仍 200、degraded=true、
 * 用户名换成占位文案，订单本体不丢。
 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private static final Logger log = LoggerFactory.getLogger(OrderController.class);

    /** 降级占位文案（与 exercises/sol-02 的 degraded 语义一致） */
    private static final String DEGRADED_USER_TEXT = "（用户服务暂不可用，降级展示）";

    private final OrderService orderService;
    private final UserClient userClient;

    public OrderController(OrderService orderService, UserClient userClient) {
        this.orderService = orderService;
        this.userClient = userClient;
    }

    @GetMapping("/{id}")
    public ApiResponse<OrderDetail> detail(@PathVariable long id,
                                           @RequestHeader(value = "X-Auth-User", required = false) String authUser) {
        requireAuthenticated(authUser);
        Order order = orderService.findById(id);
        if (order == null) {
            // 订单数据是 order-service 自己的（数据跟着服务走），本地查无 → 40400
            throw new BizException(BizCodes.NOT_FOUND, "order not found: " + id);
        }
        try {
            UserCall call = userClient.findUser(order.userId(), authUser);   // 远程取用户名（同构 OpenFeign）
            return ApiResponse.ok(new OrderDetail(order.orderId(), order.item(),
                    call.username(), false, call.downstreamTraceId()));
        } catch (DownstreamException | DownstreamTimeoutException e) {
            // 用户服务故障/超时 → 降级展示（订单不丢）；真实工程还会配熔断，见 ex03
            log.warn("degrade order {} (user lookup failed): {}", id, e.getMessage());
            return ApiResponse.ok(new OrderDetail(order.orderId(), order.item(),
                    DEGRADED_USER_TEXT, true, null));
        }
    }

    private void requireAuthenticated(String authUser) {
        if (authUser == null || authUser.isBlank()) {
            throw new BizException(BizCodes.UNAUTHENTICATED, "missing X-Auth-User header");
        }
    }
}
