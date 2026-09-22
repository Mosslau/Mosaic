// project/error-code.java —— 业务错误码枚举：集中管理全部错误语义
// 统一异常处理 demo 的组件一：错误码集中定义，避免魔法数字散落各处
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java ExceptionDemoApp
// 验证状态：已验证：OpenJDK 17.0.16
// 错误码枚举：code 用于对外传输（协议层），message 是默认可读消息
enum ErrorCode {
    INVALID_PARAM(400, "参数不合法"),
    USER_NOT_FOUND(404, "用户不存在"),
    LOGIN_FAILED(1001, "用户名或密码错误"),
    INSUFFICIENT_BALANCE(2001, "余额不足"),
    SYSTEM_ERROR(500, "系统繁忙，请稍后再试");

    final int code;
    final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }
}
