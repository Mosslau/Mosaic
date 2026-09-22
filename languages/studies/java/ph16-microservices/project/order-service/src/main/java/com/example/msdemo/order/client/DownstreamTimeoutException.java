package com.example.msdemo.order.client;

/**
 * 下游调用失败语义（2）：连接/读超时。RestClient 把 SocketTimeoutException/ConnectException
 * 包成 ResourceAccessException，这里转成语义明确的业务异常（参照 examples/ex01）。
 */
public class DownstreamTimeoutException extends RuntimeException {

    public DownstreamTimeoutException(String service, Throwable cause) {
        super("下游服务 " + service + " 调用超时", cause);
    }
}
