package com.ninebot.dataagent.api;

import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 将控制面和 Gateway 异常转换成稳定的 JSON 错误结构。 */
@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String, Object> badRequest(IllegalArgumentException ex) {
        return error("INVALID_REQUEST", ex.getMessage(), false);
    }

    @ExceptionHandler(IllegalStateException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public Map<String, Object> unavailable(IllegalStateException ex) {
        return error("SERVICE_UNAVAILABLE", ex.getMessage(), true);
    }

    @ExceptionHandler(UnsupportedOperationException.class)
    @ResponseStatus(HttpStatus.NOT_IMPLEMENTED)
    public Map<String, Object> notImplemented(UnsupportedOperationException ex) {
        return error("NOT_IMPLEMENTED", ex.getMessage(), false);
    }

    private Map<String, Object> error(String code, String message, boolean retryable) {
        return Map.of("code", code, "message", message == null ? code : message,
                "retryable", retryable, "timestamp", Instant.now().toString());
    }
}
