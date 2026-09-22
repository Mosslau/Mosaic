// project/business-exception.java —— 业务异常体系：unchecked 基类 + 错误码 + 上下文 + 具体子类
// 统一异常处理 demo 的组件二：基类携带错误码与业务上下文，子类表达具体业务失败
// 设计要点：
// - 继承 RuntimeException（unchecked）——不污染每一层接口签名（主文档 3.3/4.3 节）
// - 错误码来自 ErrorCode 枚举；context 携带业务上下文（订单号、用户 ID、余额等）
// - cause 构造器保留底层根因（异常链，主文档 3.4 节）
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java ExceptionDemoApp
// 验证状态：已验证：OpenJDK 17.0.16
class BusinessException extends RuntimeException {
    private final ErrorCode errorCode;
    private final String context;   // 业务上下文，null 表示无

    BusinessException(ErrorCode errorCode) {
        this(errorCode, null, null);
    }

    BusinessException(ErrorCode errorCode, String context) {
        this(errorCode, context, null);
    }

    BusinessException(ErrorCode errorCode, String context, Throwable cause) {
        super(errorCode.message, cause);   // 构造器链：异常链保留根因
        this.errorCode = errorCode;
        this.context = context;
    }

    ErrorCode getErrorCode() { return errorCode; }
    String getContext() { return context; }
}

// 用户不存在：DAO 边界转换的落点（携带 userId 上下文，可保留底层 cause）
class UserNotFoundException extends BusinessException {
    UserNotFoundException(String userId) {
        super(ErrorCode.USER_NOT_FOUND, "userId=" + userId);
    }

    UserNotFoundException(String userId, Throwable cause) {
        super(ErrorCode.USER_NOT_FOUND, "userId=" + userId, cause);
    }
}

// 登录失败：凭据错误（无需上下文）
class LoginFailedException extends BusinessException {
    LoginFailedException() {
        super(ErrorCode.LOGIN_FAILED);
    }
}

// 余额不足：携带余额与请求金额，便于日志排查
class InsufficientBalanceException extends BusinessException {
    InsufficientBalanceException(double balance, double amount) {
        super(ErrorCode.INSUFFICIENT_BALANCE,
                "balance=" + balance + ", amount=" + amount);
    }
}
