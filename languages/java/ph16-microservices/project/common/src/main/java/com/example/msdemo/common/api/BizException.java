package com.example.msdemo.common.api;

/**
 * 业务异常：携带业务码，HTTP 状态由码值推导（code / 100）。
 * 各服务的 @RestControllerAdvice 统一把它翻译成 {@link ApiResponse} 错误壳。
 */
public class BizException extends RuntimeException {

    private final int code;

    public BizException(int code, String message) {
        super(message);
        this.code = code;
    }

    public int code() {
        return code;
    }

    /** 约定：业务码前三位即 HTTP 状态（40100→401、50400→504、50000→500） */
    public int httpStatus() {
        return code / 100;
    }
}
