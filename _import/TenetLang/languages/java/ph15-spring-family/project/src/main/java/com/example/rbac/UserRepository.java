package com.example.rbac;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/** Spring Data 仓库：方法名派生查询 findByUsername（接口即实现，见 examples/ex05） */
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    boolean existsByUsername(String username);
}
