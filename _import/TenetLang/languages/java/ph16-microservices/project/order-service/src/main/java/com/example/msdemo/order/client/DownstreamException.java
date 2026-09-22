package com.example.msdemo.order.client;

/**
 * 下游调用失败语义（1）：用户服务返回了错误状态码（4xx 除 404、5xx）。
 * 与 examples/ex01 的 DownstreamException 同构：调用方显式建模失败，而不是让异常裸奔。
 */
public class DownstreamException extends RuntimeException {

    public DownstreamException(String service, int status) {
        super("下游服务 " + service + " 返回错误状态 " + status);
    }
}
