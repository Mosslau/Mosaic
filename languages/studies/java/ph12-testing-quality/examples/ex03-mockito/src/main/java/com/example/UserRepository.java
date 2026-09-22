package com.example;

import java.util.Optional;

/**
 * 外部依赖接口：真实实现可能是数据库访问、远程 HTTP 调用等（本阶段不实现）。
 * 测试时用 Mockito 生成替身，把被测服务与外部世界隔离 —— 「Mock 外部依赖」。
 */
public interface UserRepository {

    Optional<User> findById(long id);

    boolean existsByEmail(String email);

    void save(User user);
}
