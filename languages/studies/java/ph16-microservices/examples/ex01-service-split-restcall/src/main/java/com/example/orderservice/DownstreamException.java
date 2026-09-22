package com.example.orderservice;

/** 下游返回 5xx 等非预期错误 */
public class DownstreamException extends RuntimeException {

    public DownstreamException(String service, int status) {
        super("下游服务 " + service + " 返回错误状态 " + status);
    }
}
