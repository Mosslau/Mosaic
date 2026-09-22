// examples/ex03-business-exception-demo.java —— 自定义业务异常体系：错误码枚举 + 异常基类 + 异常链
// 对应主文档「6. 代码示例 / 示例 3」与推荐项目「业务错误码体系」的核心骨架
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex03-business-exception-demo.java
// 运行：java BusinessExceptionDemo
// 验证状态：已验证：OpenJDK 17.0.16
class BusinessExceptionDemo {
    // 错误码枚举：集中管理业务错误语义
    enum ErrorCode {
        INVALID_PARAM(1001, "参数不合法"),
        USER_NOT_FOUND(1002, "用户不存在"),
        LOGIN_FAILED(1003, "登录失败"),
        INSUFFICIENT_BALANCE(2001, "余额不足");

        final int code;
        final String message;

        ErrorCode(int code, String message) {
            this.code = code;
            this.message = message;
        }
    }

    // 业务异常基类：unchecked + 错误码 + 异常链
    static class BusinessException extends RuntimeException {
        private final ErrorCode errorCode;

        BusinessException(ErrorCode errorCode) {
            super(errorCode.message);
            this.errorCode = errorCode;
        }

        BusinessException(ErrorCode errorCode, Throwable cause) {
            super(errorCode.message, cause);   // 保留根因
            this.errorCode = errorCode;
        }

        public ErrorCode getErrorCode() { return errorCode; }
    }

    // 账户服务：余额不足时抛业务异常，并附上根因
    static class AccountService {
        private final double balance;

        AccountService(double balance) { this.balance = balance; }

        void transfer(double amount) {
            if (amount <= 0) {
                throw new BusinessException(ErrorCode.INVALID_PARAM);
            }
            if (balance < amount) {
                throw new BusinessException(ErrorCode.INSUFFICIENT_BALANCE,
                        new IllegalArgumentException(
                                "余额 " + balance + " 小于转账金额 " + amount));
            }
            System.out.println("转账成功: " + amount);
        }
    }

    public static void main(String[] args) {
        AccountService service = new AccountService(100.0);
        try {
            service.transfer(500.0);
        } catch (BusinessException e) {
            System.out.println("错误码: " + e.getErrorCode().code
                    + ", 信息: " + e.getMessage());
            e.printStackTrace();   // 生产环境应交给日志框架
        }
    }
}
