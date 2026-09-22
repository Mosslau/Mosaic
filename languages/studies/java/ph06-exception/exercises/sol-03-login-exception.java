// exercises/sol-03-login-exception.java —— 练习 3 登录异常参考实现
// 在示例 ex04 基础上：LoginException 携带错误码 + 连续 3 次错误锁定账户
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-03-login-exception.java
// 运行：java LoginExceptionSol
// 验证状态：已验证：OpenJDK 17.0.16
class LoginExceptionSol {
    // 错误码枚举：区分失败原因，比裸字符串消息更可编程
    enum LoginError {
        WRONG_PASSWORD(1001, "用户名或密码错误"),
        ACCOUNT_LOCKED(1002, "账户已锁定，请稍后再试");

        final int code;
        final String message;

        LoginError(int code, String message) {
            this.code = code;
            this.message = message;
        }
    }

    // 业务异常：携带错误码（unchecked，避免污染接口签名）
    static class LoginException extends RuntimeException {
        private final LoginError error;

        LoginException(LoginError error) {
            super(error.message);
            this.error = error;
        }

        LoginError getError() { return error; }
    }

    // 登录服务：参数校验用 IllegalArgumentException，业务失败用 LoginException
    static class LoginService {
        private static final String USER = "admin";
        private static final String PASSWORD = "123456";
        private static final int MAX_ATTEMPTS = 3;

        private int failedAttempts = 0;   // 实例内维护的锁定状态
        private boolean locked = false;

        String login(String username, String password) {
            requireNonEmpty(username, "用户名");
            requireNonEmpty(password, "密码");
            if (locked) {
                throw new LoginException(LoginError.ACCOUNT_LOCKED);
            }
            if (!USER.equals(username) || !PASSWORD.equals(password)) {
                failedAttempts++;
                if (failedAttempts >= MAX_ATTEMPTS) {
                    locked = true;
                }
                throw new LoginException(LoginError.WRONG_PASSWORD);
            }
            failedAttempts = 0;   // 登录成功重置失败计数
            return "登录成功，欢迎 " + username;
        }

        // 参数校验：调用方写错 -> IllegalArgumentException（unchecked）
        static void requireNonEmpty(String value, String field) {
            if (value == null || value.trim().isEmpty()) {
                throw new IllegalArgumentException(field + " 不能为空");
            }
        }
    }

    public static void main(String[] args) {
        LoginService service = new LoginService();

        // 连续 3 次密码错误 -> 第 3 次后账户锁定
        for (int i = 1; i <= 3; i++) {
            try {
                service.login("admin", "wrong");
            } catch (LoginException e) {
                System.out.println("第 " + i + " 次失败: 错误码 " + e.getError().code
                        + ", " + e.getMessage());
            }
        }

        // 锁定后即使密码正确也失败
        try {
            service.login("admin", "123456");
        } catch (LoginException e) {
            System.out.println("锁定后正确密码: 错误码 " + e.getError().code
                    + ", " + e.getMessage());
        }

        // 新实例：正确凭据登录成功
        LoginService fresh = new LoginService();
        System.out.println(fresh.login("admin", "123456"));

        // 参数为空 -> IllegalArgumentException，与业务异常分开 catch
        try {
            fresh.login("", "123456");
        } catch (IllegalArgumentException e) {
            System.out.println("参数错误: " + e.getMessage());
        }
    }
}
