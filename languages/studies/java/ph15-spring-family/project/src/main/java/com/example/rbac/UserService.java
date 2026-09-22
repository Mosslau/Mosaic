package com.example.rbac;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 用户业务：创建（查重 + BCrypt 加密 + 角色白名单校验）、列表、删除。
 * 教学点：事务边界在 Service（@Transactional），Controller 只做 HTTP 语义；
 * 密码在 Service 层加密后入库——BCrypt 单向哈希，数据库被拖走也拿不到明文（ex06 已验证哈希形态）。
 */
@Service
public class UserService {

    private final UserRepository repository;
    private final PasswordEncoder passwordEncoder;

    public UserService(UserRepository repository, PasswordEncoder passwordEncoder) {
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional(readOnly = true)
    public List<User> listAll() {
        return repository.findAll();
    }

    /** 创建用户：用户名唯一（存在即 409）、角色白名单 ADMIN/USER、密码 BCrypt 化 */
    @Transactional
    public User create(String username, String rawPassword, String role, String displayName) {
        if (repository.existsByUsername(username)) {
            throw new DuplicateUsernameException(username);
        }
        if (!role.equals("ADMIN") && !role.equals("USER")) {
            throw new IllegalArgumentException("角色只允许 ADMIN 或 USER: " + role);
        }
        return repository.save(new User(username, passwordEncoder.encode(rawPassword), role, displayName));
    }

    @Transactional
    public void delete(Long id) {
        repository.deleteById(id);
    }
}
