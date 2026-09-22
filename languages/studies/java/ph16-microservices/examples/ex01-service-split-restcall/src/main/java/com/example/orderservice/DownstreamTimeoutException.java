package com.example.orderservice;

/** 下游连接/读超时（RestClient 把 SocketTimeoutException 包成 ResourceAccessException） */
public class DownstreamTimeoutException extends RuntimeException {

    public DownstreamTimeoutException(String service, Throwable cause) {
        super("下游服务 " + service + " 调用超时", cause);
    }
}
