// project/exception-demo-app.java —— 统一异常处理 demo 自测入口：三层模拟 + 6 条自测路径
// Controller/Service/DAO 三层各自抛不同类型的异常，顶层统一交给 GlobalExceptionHandler 分类处理
// - DAO 层：抛受检异常（模拟 SQLException）
// - Service 层：参数异常抛 IllegalArgumentException，业务失败抛具体业务异常，基础设施故障抛 IllegalStateException
// - Controller 层：统一 try/catch + handler.handle(Throwable) 收口
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java ExceptionDemoApp
// 验证状态：已验证：OpenJDK 17.0.16
class ExceptionDemoApp {
    // ==================== DAO 层 ====================
    static class UserDao {
        // 模拟数据库：只有 user1 存在；查不到时抛受检异常（真实场景是 SQLException）
        String findById(String userId) throws Exception {
            if ("user1".equals(userId)) {
                return "Alice";
            }
            throw new Exception("SQL: no row found for id=" + userId);
        }
    }

    // ==================== Service 层 ====================
    static class UserService {
        private final UserDao dao = new UserDao();

        // 边界转换：受检异常在 DAO 边界包装为 unchecked 业务异常，保留 cause（主文档 4.3 节）
        String findUser(String userId) {
            try {
                return dao.findById(userId);
            } catch (Exception e) {
                throw new UserNotFoundException(userId, e);
            }
        }

        String login(String username, String password) {
            // 参数校验：调用方错误 -> IllegalArgumentException
            if (username == null || username.trim().isEmpty()
                    || password == null || password.isEmpty()) {
                throw new IllegalArgumentException("用户名或密码不能为空");
            }
            // 业务校验：凭据错误 -> 业务异常
            if (!"admin".equals(username) || !"123456".equals(password)) {
                throw new LoginFailedException();
            }
            return "admin";
        }

        String transfer(String account, double amount) {
            if (amount <= 0) {
                throw new IllegalArgumentException("转账金额必须为正数");
            }
            // 余额不足 -> 业务异常（携带余额上下文）
            throw new InsufficientBalanceException(100.0, amount);
        }

        // 模拟基础设施故障（连接池耗尽）：既非参数问题也非业务规则
        String pingDatabase() {
            throw new IllegalStateException("connection pool exhausted");
        }
    }

    // ==================== Controller 层 ====================
    static class UserController {
        private final UserService service = new UserService();
        private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

        // 每个接口同一骨架：业务逻辑放 try，异常统一交 handler 分类处理
        ApiResponse<String> findUser(String userId) {
            try {
                return ApiResponse.success(service.findUser(userId));
            } catch (Throwable t) {
                return handler.handle(t);
            }
        }

        ApiResponse<String> login(String username, String password) {
            try {
                return ApiResponse.success(service.login(username, password));
            } catch (Throwable t) {
                return handler.handle(t);
            }
        }

        ApiResponse<String> transfer(String account, double amount) {
            try {
                return ApiResponse.success(service.transfer(account, amount));
            } catch (Throwable t) {
                return handler.handle(t);
            }
        }

        ApiResponse<String> ping() {
            try {
                return ApiResponse.success(service.pingDatabase());
            } catch (Throwable t) {
                return handler.handle(t);
            }
        }
    }

    // ==================== 自测 main ====================
    public static void main(String[] args) {
        UserController controller = new UserController();

        // 路径 1：正常路径
        ApiResponse<String> r1 = controller.findUser("user1");
        check(r1.success() && "Alice".equals(r1.data()), "正常查询: findUser(user1) = Alice");
        System.out.println("    " + r1);

        // 路径 2：业务异常 -> 用户不存在（DAO 受检异常 -> 边界转换 -> 404）
        ApiResponse<String> r2 = controller.findUser("nobody");
        check(!r2.success() && r2.code() == ErrorCode.USER_NOT_FOUND.code,
                "用户不存在 -> code 404");
        System.out.println("    " + r2);

        // 路径 3：业务异常 -> 登录失败（错误码 1001）
        ApiResponse<String> r3 = controller.login("admin", "wrong");
        check(!r3.success() && r3.code() == ErrorCode.LOGIN_FAILED.code,
                "登录失败 -> code 1001");
        System.out.println("    " + r3);

        // 路径 4：业务异常 -> 余额不足（错误码 2001，context 携带余额与金额）
        ApiResponse<String> r4 = controller.transfer("acc1", 500.0);
        check(!r4.success() && r4.code() == ErrorCode.INSUFFICIENT_BALANCE.code,
                "余额不足 -> code 2001");
        System.out.println("    " + r4);

        // 路径 5：参数异常 -> 400（调用方写错）
        ApiResponse<String> r5 = controller.login("", "123456");
        check(!r5.success() && r5.code() == ErrorCode.INVALID_PARAM.code,
                "空参数 -> code 400");
        System.out.println("    " + r5);

        // 路径 6：未知异常 -> 兜底 500（记录日志 + 不泄露内部细节）
        ApiResponse<String> r6 = controller.ping();
        check(!r6.success() && r6.code() == ErrorCode.SYSTEM_ERROR.code,
                "未知异常 -> code 500 兜底");
        System.out.println("    " + r6);

        System.out.println("全部自测通过");
    }

    // 断言失败立即抛 AssertionError 并给出路径名（不静默）
    private static void check(boolean condition, String msg) {
        if (!condition) {
            throw new AssertionError("自测失败: " + msg);
        }
        System.out.println("通过: " + msg);
    }
}
