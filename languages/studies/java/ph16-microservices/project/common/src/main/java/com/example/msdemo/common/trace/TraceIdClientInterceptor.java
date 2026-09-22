package com.example.msdemo.common.trace;

import org.slf4j.MDC;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

import java.io.IOException;

/**
 * RestClient 侧的 TraceId 透传拦截器：把当前线程 MDC 里的 traceId 写进下游请求头。
 * 等价于 Micrometer Tracing 的 PropagatingSenderTracingObservationHandler 做的 header 注入。
 */
public class TraceIdClientInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution)
            throws IOException {
        String traceId = MDC.get("traceId");
        if (traceId != null && !traceId.isBlank()) {
            request.getHeaders().set(TraceIdFilter.HEADER, traceId);
        }
        return execution.execute(request, body);
    }
}
