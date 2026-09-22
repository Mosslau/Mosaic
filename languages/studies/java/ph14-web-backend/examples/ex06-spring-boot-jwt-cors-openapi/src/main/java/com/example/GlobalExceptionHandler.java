// examples/ex06-spring-boot-jwt-cors-openapi/src/main/java/com/example/GlobalExceptionHandler.java
// —— 全局异常处理（@RestControllerAdvice）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// ---------------------------------------------------------------------------
// 教学点：鉴权失败（AuthController.AuthException）也走统一异常处理 → 401 + 业务码。
// 这样 Controller 里不用写 try/catch，异常处理全部收口在这一处（一致性）。
package com.example;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 鉴权失败：401 + 业务码 40100。 */
    @ExceptionHandler(AuthController.AuthException.class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    public ApiResponse<Void> handleAuth(AuthController.AuthException ex) {
        return ApiResponse.error(40100, ex.getMessage());
    }

    /** 兜底：未预期的异常 → 500 + 业务码 50000；必须记 ERROR 日志。 */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleUnexpected(Exception ex) {
        log.error("unhandled_exception", ex);
        return ApiResponse.error(50000, "服务器内部错误");
    }
}
