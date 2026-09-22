package com.example.msdemo.gateway.config;

import com.example.msdemo.common.api.ApiResponse;
import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 网关统一异常契约：未知路由等 BizException → 业务码 + HTTP 状态；未知异常 → 50000 兜底。
 * 网关只做透传与鉴权，不该自己抛业务错——这里主要兜底路由表 miss。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public ResponseEntity<ApiResponse<Void>> biz(BizException e) {
        return ResponseEntity.status(e.httpStatus())
                .body(ApiResponse.error(e.code(), e.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> fallback(Exception e) {
        log.error("unhandled exception", e);
        return ResponseEntity.status(500)
                .body(ApiResponse.error(BizCodes.INTERNAL_ERROR, "internal error"));
    }
}
