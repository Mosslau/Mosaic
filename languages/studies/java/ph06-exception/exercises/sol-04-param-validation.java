// exercises/sol-04-param-validation.java —— 练习 4 参数校验异常参考实现
// requireXxx 风格校验工具 + 订单创建场景：校验放在方法入口最前（fail fast）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-04-param-validation.java
// 运行：java ParamValidationSol
// 验证状态：已验证：OpenJDK 17.0.16
class ParamValidationSol {
    // 校验工具：全部抛 IllegalArgumentException，消息带字段名，方便调用方定位问题
    static final class Validator {
        static void requireNonEmpty(String value, String field) {
            if (value == null || value.trim().isEmpty()) {
                throw new IllegalArgumentException(field + " 不能为空");
            }
        }

        static void requireNotNull(Object value, String field) {
            if (value == null) {
                throw new IllegalArgumentException(field + " 不能为 null");
            }
        }

        static void requirePositive(int value, String field) {
            if (value <= 0) {
                throw new IllegalArgumentException(field + " 必须为正数，当前: " + value);
            }
        }

        static void requirePositive(double value, String field) {
            if (value <= 0) {
                throw new IllegalArgumentException(field + " 必须为正数，当前: " + value);
            }
        }

        static void requireInRange(int value, int min, int max, String field) {
            if (value < min || value > max) {
                throw new IllegalArgumentException(
                        field + " 必须在 [" + min + ", " + max + "] 范围内，当前: " + value);
            }
        }
    }

    // 订单服务：所有校验在方法入口第一行开始，任何业务逻辑之前
    static final class OrderService {
        static String createOrder(String buyerName, int itemCount, double pricePerItem) {
            Validator.requireNonEmpty(buyerName, "买家姓名");
            Validator.requireInRange(itemCount, 1, 100, "商品数量");
            Validator.requirePositive(pricePerItem, "单价");
            double total = itemCount * pricePerItem;
            // 浮点直接输出会有精度尾巴（如 29.700000000000003），展示时格式化两位小数
            return String.format("订单创建成功: %s x%d, 总价 %.2f",
                    buyerName, itemCount, total);
            // 为什么参数校验用 unchecked 的 IllegalArgumentException？
            // 参数错误是「调用方写错了」，不是可恢复的外部失败；强制 checked 会让每一层
            // 调用者被迫 catch/throws，污染接口签名。fail fast 才是目的：尽早暴露调用方 bug。
        }
    }

    public static void main(String[] args) {
        // 合法入参
        System.out.println(OrderService.createOrder("张三", 3, 9.9));

        // 空买家 -> IllegalArgumentException（消息含字段名）
        try {
            OrderService.createOrder("", 3, 9.9);
        } catch (IllegalArgumentException e) {
            System.out.println("空买家: " + e.getMessage());
        }

        // 数量越界 -> 字段名 + 允许范围
        try {
            OrderService.createOrder("张三", 101, 9.9);
        } catch (IllegalArgumentException e) {
            System.out.println("数量越界: " + e.getMessage());
        }

        // 单价为 0 -> 非法（float/double 与 0 精确比较在本场景够用）
        try {
            OrderService.createOrder("张三", 3, 0);
        } catch (IllegalArgumentException e) {
            System.out.println("单价为 0: " + e.getMessage());
        }
    }
}
