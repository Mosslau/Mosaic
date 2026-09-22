package com.example;

/**
 * 业务服务：依赖 UserRepository，通过构造器注入（Java 工程化惯例，便于测试替换依赖）。
 * 被测对象本身不含任何外部调用 —— 外部调用全部发生在注入的依赖上。
 */
public class UserService {

    private final UserRepository repo;

    public UserService(UserRepository repo) {
        this.repo = repo;
    }

    /** 正常路径：用户存在返回问候语；错误路径：不存在抛 IllegalArgumentException。 */
    public String greeting(long id) {
        return repo.findById(id)
                .map(u -> "Hello, " + u.name() + "!")
                .orElseThrow(() -> new IllegalArgumentException("用户不存在: " + id));
    }

    /** 注册：邮箱重复则拒绝（错误路径），否则落库。 */
    public void register(User user) {
        if (repo.existsByEmail(user.email())) {
            throw new IllegalArgumentException("邮箱已注册: " + user.email());
        }
        repo.save(user);
    }
}
