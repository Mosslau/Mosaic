// project/exception-handler.java —— 统一处理入口：分类处理业务异常 / 参数异常 / 未知异常
// 统一异常处理 demo 的组件四：顶层唯一 catch 点，把异常翻译为错误码 + 统一响应
// 分类规则（主文档第 4.3 节「边界转换」的收口）：
// - 业务异常 BusinessException -> 对应业务错误码（404/1001/2001）
// - 参数异常 IllegalArgumentException -> 400（调用方写错）
// - 其他未知异常 -> 记录日志（这里用打印模拟日志框架）后返回兜底 500，不向调用方泄露内部细节
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java ExceptionDemoApp
// 验证状态：已验证：OpenJDK 17.0.16
class GlobalExceptionHandler {
    // 统一处理入口：任何异常 -> ApiResponse
    // 泛型 <T> 让 controller 层可以按接口返回值类型推断，无需为每个接口写一套
    <T> ApiResponse<T> handle(Throwable t) {
        if (t instanceof BusinessException) {           // 业务异常：错误码即业务语义
            BusinessException be = (BusinessException) t;
            System.out.println("[业务异常] code=" + be.getErrorCode().code
                    + ", " + be.getMessage() + " (context: " + be.getContext() + ")");
            return ApiResponse.error(be.getErrorCode());
        }
        if (t instanceof IllegalArgumentException) {    // 参数异常：调用方写错
            System.out.println("[参数异常] " + t.getMessage());
            return ApiResponse.error(ErrorCode.INVALID_PARAM);
        }
        // 未知异常：打印堆栈（生产环境交给日志框架）后返回兜底错误
        System.out.println("[未知异常] " + t.getClass().getSimpleName()
                + ": " + t.getMessage());
        t.printStackTrace();
        return ApiResponse.error(ErrorCode.SYSTEM_ERROR);
    }
}
