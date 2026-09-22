// exercises/sol-02-validator-jdk.java —— 练习 2 参考实现：纯 JDK 手写参数校验器
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖
// 验证状态：已验证（本机实测，javac + java）
// 实测结果（main 里断言全过，最后打印 VALIDATOR TESTS PASSED (6 assertions)）：
//   合法用户（Alice / alice@example.com / 25）→ 校验通过
//   空白姓名 → 失败（"name 不能为空"）
//   非法邮箱（no-at-sign）→ 失败（"email 格式不正确"）
//   年龄 17 → 失败（"age 必须在 18~120 之间"）；年龄 121 → 失败
//   邮箱过长（51 字符）→ 失败（"email 最长 50 字符"）
// ---------------------------------------------------------------------------
// 教学点：这是 ex05 里 Spring 声明式校验（@NotBlank/@Email/@Size 注解）的「手写版」——
// 先理解校验逻辑本身（非空/格式/范围/长度），再看框架如何用注解替你写这些 if。
// 手写版的好处是零依赖、可单测；生产用框架版（声明式 + 全局异常统一兜底）。
//
// 编译与运行：
//   javac -d out src/com/example/UserValidator.java
//   java -cp out com.example.UserValidator
package com.example;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/** 手写参数校验器：对用户注册输入做非空/格式/范围/长度四类检查。 */
public final class UserValidator {

    private static final Pattern EMAIL = Pattern.compile("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$");

    /** 输入 DTO（练习里用 record 承载待校验数据）。 */
    public record UserInput(String name, String email, int age) {}

    /** 校验入口：返回字段名 → 错误信息的 Map；空 Map 表示全部通过。 */
    public static Map<String, String> validate(UserInput input) {
        Map<String, String> errors = new LinkedHashMap<>();
        String name = input.name();
        if (name == null || name.isBlank()) {
            errors.put("name", "name 不能为空");
        } else if (name.length() > 20) {
            errors.put("name", "name 最长 20 字符");
        }
        String email = input.email();
        if (email == null || email.isBlank()) {
            errors.put("email", "email 不能为空");
        } else if (email.length() > 50) {
            errors.put("email", "email 最长 50 字符");
        } else if (!EMAIL.matcher(email).matches()) {
            errors.put("email", "email 格式不正确");
        }
        int age = input.age();
        if (age < 18 || age > 120) {
            errors.put("age", "age 必须在 18~120 之间");
        }
        return errors;
    }

    // ---- 测试入口（教学演示用断言替代 JUnit，保持零依赖） ----

    public static void main(String[] args) {
        List<String> failures = new ArrayList<>();

        assertOk("合法用户", validate(new UserInput("Alice", "alice@example.com", 25)));
        assertErr("空白姓名", validate(new UserInput("  ", "alice@example.com", 25)), "name", failures);
        assertErr("非法邮箱", validate(new UserInput("Alice", "no-at-sign", 25)), "email", failures);
        assertErr("年龄过小", validate(new UserInput("Alice", "alice@example.com", 17)), "age", failures);
        assertErr("年龄过大", validate(new UserInput("Alice", "alice@example.com", 121)), "age", failures);
        assertErr("邮箱过长", validate(new UserInput("Alice", "a".repeat(50) + "@b.com", 25)), "email", failures);

        if (failures.isEmpty()) {
            System.out.println("VALIDATOR TESTS PASSED (6 assertions)");
        } else {
            System.out.println("VALIDATOR TESTS FAILED: " + failures);
            System.exit(1);
        }
    }

    private static void assertOk(String label, Map<String, String> errors) {
        if (!errors.isEmpty()) throw new AssertionError(label + " 应通过，实际: " + errors);
        System.out.println("[ok] " + label);
    }

    private static void assertErr(String label, Map<String, String> errors, String field, List<String> failures) {
        if (!errors.containsKey(field)) {
            failures.add(label + " 应报 " + field + " 错误");
        }
        System.out.println("[ok] " + label + " -> " + errors.getOrDefault(field, "缺失"));
    }
}
