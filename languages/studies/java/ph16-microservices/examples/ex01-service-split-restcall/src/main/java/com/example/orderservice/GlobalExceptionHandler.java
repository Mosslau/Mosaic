package com.example.orderservice;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 下游失败的对外语义：超时 504 / 下游 5xx 502 / 查无 404。
 * 业务码沿用 ph14 的 {code,message,data} 壳（ph16 新增 50200/50400 两个下游错误码，认证授权码沿用 ph15 语义）。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    public record ErrorBody(int code, String message) {
    }

    @ExceptionHandler({OrderNotFoundException.class, UserNotFoundException.class})
    public ResponseEntity<ErrorBody> notFound(RuntimeException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(new ErrorBody(40400, ex.getMessage()));
    }

    @ExceptionHandler(DownstreamTimeoutException.class)
    public ResponseEntity<ErrorBody> timeout(DownstreamTimeoutException ex) {
        return ResponseEntity.status(HttpStatus.GATEWAY_TIMEOUT).body(new ErrorBody(50400, ex.getMessage()));
    }

    @ExceptionHandler(DownstreamException.class)
    public ResponseEntity<ErrorBody> downstream(DownstreamException ex) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(new ErrorBody(50200, ex.getMessage()));
    }
}
