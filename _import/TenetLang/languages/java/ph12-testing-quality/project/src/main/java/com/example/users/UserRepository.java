package com.example.users;

import java.util.Optional;

/**
 * 用户存储接口：业务层只依赖这个抽象（依赖倒置），
 * 单元测试用 Mockito 替身、集成测试连真实 JDBC 实现 —— 接口是本阶段「替身能插进来」的前提。
 */
public interface UserRepository {

    Optional<User> findById(long id);

    boolean existsByEmail(String email);

    /** 保存用户并返回带分配 id 的持久化结果。 */
    User save(User user);

    /** 删除指定 id 的用户，返回是否删除了。 */
    boolean deleteById(long id);
}
