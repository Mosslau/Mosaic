// project/src/main/java/com/example/vehicle/GlobalExceptionHandler.java —— 全局异常处理
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0（本机离线 mvn -o 实测）
// 验证状态：已验证（MockMvc 测试实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：所有业务异常（BusinessException.code）与校验失败（MethodArgumentNotValidException）
// 在这里统一翻译成 ApiResponse + 合适的 HTTP 状态码；未知异常兜底 500 并记 ERROR 日志。
// 业务码 → HTTP 状态映射：401xx → 401，404xx → 404，其余 4xxxx → 400，5xxxx → 500。
package com.example.vehicle;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 业务异常：按 code 前缀映射 HTTP 状态（401xx → 401，404xx → 404，其余 4xxxx → 400，5xxxx → 500）。 */
    @ExceptionHandler(VehicleService.BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusiness(VehicleService.BusinessException ex) {
        HttpStatus status = ex.getCode().startsWith("5") ? HttpStatus.INTERNAL_SERVER_ERROR
                : ex.getCode().startsWith("404") ? HttpStatus.NOT_FOUND
                : ex.getCode().startsWith("401") ? HttpStatus.UNAUTHORIZED
                : HttpStatus.BAD_REQUEST;
        return ResponseEntity.status(status)
                .body(ApiResponse.error(Integer.parseInt(ex.getCode()), ex.getMessage()));
    }

    /** 参数校验失败（@Valid 触发）：400 + 40000，data 里带每个字段的错误信息。 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Map<String, String>>> handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> fieldErrors = new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors()
                .forEach(fe -> fieldErrors.putIfAbsent(fe.getField(), fe.getDefaultMessage()));
        return ResponseEntity.badRequest().body(ApiResponse.error(40000, "参数校验失败", fieldErrors));
    }

    /** 兜底：未预期异常 → 500 + 50000；必须记 ERROR 日志。 */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpected(Exception ex) {
        log.error("unhandled_exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error(50000, "服务器内部错误"));
    }
}
