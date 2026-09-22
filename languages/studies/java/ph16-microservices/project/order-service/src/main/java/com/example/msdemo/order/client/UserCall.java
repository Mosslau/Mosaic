package com.example.msdemo.order.client;

/**
 * 一次下游调用的结果：远程用户名 + user-service 实际见到的 X-Trace-Id（链路透传证据，参照 examples/ex01）。
 */
public record UserCall(String username, String downstreamTraceId) {
}
