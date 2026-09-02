package com.example.orderservice;

import com.example.userservice.UserDto;

/** 一次下游调用的结果：业务体 + 下游服务实际见到的 traceId（链路透传的证据） */
public record UserCall(UserDto user, String downstreamTraceId) {
}
