// project/api-response.java —— 统一响应结构：所有接口返回同一形状
// 统一异常处理 demo 的组件三：success/code/message/data 四要素，异常也翻译成这个形状
// 用 record（Java 16+）表达不可变响应；静态工厂方法负责构造
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java ExceptionDemoApp
// 验证状态：已验证：OpenJDK 17.0.16
record ApiResponse<T>(boolean success, int code, String message, T data) {
    // 正常路径：成功响应
    static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, 0, "成功", data);
    }

    // 失败路径：错误码 -> 统一响应（泛型方法，调用处按上下文推断 T）
    static <T> ApiResponse<T> error(ErrorCode errorCode) {
        return new ApiResponse<>(false, errorCode.code, errorCode.message, null);
    }

    // 可读输出：模拟 JSON 响应体
    @Override
    public String toString() {
        return String.format("{success=%s, code=%d, message=%s, data=%s}",
                success, code, message, data);
    }
}
