// examples/ex05-spring-boot-validation-error/src/main/java/com/example/GlobalExceptionHandler.java
// —— 全局异常处理（@RestControllerAdvice）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：roadmap 必会概念「全局异常处理提升一致性」——@RestControllerAdvice 拦截所有
// Controller 抛出的异常，按异常类型分发到对应 @ExceptionHandler 方法，统一转成 ApiResponse。
// 没有它的话，校验失败会返回 Spring 默认的错误 JSON（结构不统一），500 也会裸堆栈。
// 分层：MethodArgumentNotValidException（校验失败，4xxxx）→ 客户端错；
//       Exception（兜底）→ 5xxxx，日志必须记录（不然线上查不到根因）。
package com.example;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/** 全局异常处理器：把异常统一翻译成 ApiResponse + 合适的 HTTP 状态码。 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 参数校验失败：400 + 业务码 40001，data 里带每个字段的错误信息。 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Map<String, String>> handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> fieldErrors = new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors()
                .forEach(fe -> fieldErrors.putIfAbsent(fe.getField(), fe.getDefaultMessage()));
        return ApiResponse.error(40001, "参数校验失败", fieldErrors);
    }

    /** 兜底：未预期的异常 → 500 + 业务码 50000；必须记 ERROR 日志。 */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleUnexpected(Exception ex) {
        log.error("unhandled_exception", ex);
        return ApiResponse.error(50000, "服务器内部错误");
    }
}
