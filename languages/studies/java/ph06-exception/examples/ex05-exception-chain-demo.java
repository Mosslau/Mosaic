// examples/ex05-exception-chain-demo.java —— 异常链保留根因：DAO 边界转换，Caused by 完整链路
// 对应主文档「6. 代码示例 / 示例 5」：底层受检异常在 DAO 边界转 unchecked，逐层包装
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex05-exception-chain-demo.java
// 运行：java ExceptionChainDemo
// 验证状态：已验证：OpenJDK 17.0.16
class ExceptionChainDemo {
    static class DaoException extends RuntimeException {
        DaoException(String message, Throwable cause) { super(message, cause); }
    }

    static class ServiceException extends RuntimeException {
        ServiceException(String message, Throwable cause) { super(message, cause); }
    }

    // 最底层：数据库驱动抛出的受检异常
    static void dbQuery() throws Exception {
        throw new Exception("数据库连接超时");
    }

    // DAO 层：边界转换——受检异常包装为 unchecked DaoException，保留 cause
    static void findUser() {
        try {
            dbQuery();
        } catch (Exception e) {
            throw new DaoException("查询用户失败", e);
        }
    }

    // Service 层：继续包装，根因逐层传递
    static void getUserInfo() {
        try {
            findUser();
        } catch (DaoException e) {
            throw new ServiceException("获取用户信息失败", e);
        }
    }

    public static void main(String[] args) {
        try {
            getUserInfo();
        } catch (ServiceException e) {
            System.out.println("顶层捕获: " + e.getMessage());
            System.out.println("---- 完整堆栈（含根因）----");
            e.printStackTrace();   // 打印 ServiceException -> DaoException -> Exception
            System.out.println("根因信息: "
                    + e.getCause().getCause().getMessage());
        }
    }
}
