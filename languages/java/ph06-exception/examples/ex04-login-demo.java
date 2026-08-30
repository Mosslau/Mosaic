// examples/ex04-login-demo.java —— 登录与参数校验：IllegalArgumentException vs 业务异常
// 对应主文档「6. 代码示例 / 示例 4」：区分「调用方写错」与「业务规则失败」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex04-login-demo.java
// 运行：java LoginDemo
// 验证状态：已验证：OpenJDK 17.0.16
class LoginDemo {
    // 参数校验：调用方错误 -> IllegalArgumentException（unchecked）
    static void requireNonEmpty(String value, String field) {
        if (value == null || value.trim().isEmpty()) {
            throw new IllegalArgumentException(field + " 不能为空");
        }
    }

    // 业务异常：业务规则失败（unchecked，避免污染接口签名）
    static class LoginException extends RuntimeException {
        LoginException(String message) { super(message); }
    }

    static String login(String username, String password) {
        requireNonEmpty(username, "用户名");
        requireNonEmpty(password, "密码");
        if (!"admin".equals(username) || !"123456".equals(password)) {
            throw new LoginException("用户名或密码错误");
        }
        return "登录成功，欢迎 " + username;
    }

    public static void main(String[] args) {
        try {
            System.out.println(login("admin", "123456"));
        } catch (LoginException e) {
            System.out.println("业务失败: " + e.getMessage());
        }

        try {
            System.out.println(login("admin", "wrong"));
        } catch (LoginException e) {
            System.out.println("业务失败: " + e.getMessage());
        }

        // 参数为空 -> IllegalArgumentException，由调用方修正
        try {
            System.out.println(login("", "123456"));
        } catch (IllegalArgumentException e) {
            System.out.println("参数错误: " + e.getMessage());
        }
    }
}
