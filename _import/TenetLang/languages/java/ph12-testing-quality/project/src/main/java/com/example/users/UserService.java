package com.example.users;

import java.util.regex.Pattern;

/**
 * 用户业务服务：校验 + 编排存储，不含任何外部调用本身（外部调用全在注入的 UserRepository 上）。
 * 校验规则是本项目的业务核心，值得用参数化测试全覆盖（见 UserValidationTest）。
 */
public class UserService {

    /** 简单邮箱格式：本地部分@域名（点分标签，不允许连续点；教学用，生产级校验建议用专门库）。 */
    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("^[\\w.+-]+@[\\w-]+(\\.[\\w-]+)+$");

    private final UserRepository repo;

    public UserService(UserRepository repo) {
        this.repo = repo;
    }

    /** 注册：校验姓名/邮箱 → 查重 → 落库，返回带分配 id 的用户。 */
    public User register(String name, String email) {
        validateName(name);
        String normalizedEmail = validateEmail(email);
        if (repo.existsByEmail(normalizedEmail)) {
            throw new IllegalArgumentException("邮箱已注册: " + normalizedEmail);
        }
        return repo.save(new User(0L, name.trim(), normalizedEmail));
    }

    /** 按 id 查用户，不存在抛 IllegalArgumentException。 */
    public User findById(long id) {
        return repo.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在: " + id));
    }

    /** 修改邮箱：新邮箱必须合法且未被占用。 */
    public User updateEmail(long id, String newEmail) {
        User user = findById(id);
        String normalized = validateEmail(newEmail);
        if (!normalized.equals(user.email()) && repo.existsByEmail(normalized)) {
            throw new IllegalArgumentException("邮箱已被占用: " + normalized);
        }
        User updated = repo.save(new User(user.id(), user.name(), normalized));
        return updated;
    }

    /** 删除用户，返回是否删除成功。 */
    public boolean deleteById(long id) {
        return repo.deleteById(id);
    }

    private static void validateName(String name) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("姓名不能为空");
        }
    }

    /** 校验并返回规范化（去首尾空白）后的邮箱。 */
    private static String validateEmail(String email) {
        if (email == null || !EMAIL_PATTERN.matcher(email.trim()).matches()) {
            throw new IllegalArgumentException("邮箱格式非法: " + email);
        }
        return email.trim();
    }
}
