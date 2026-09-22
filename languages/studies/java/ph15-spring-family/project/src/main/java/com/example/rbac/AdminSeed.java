package com.example.rbac;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/** 启动种子：空库时造一个 admin/ADMIN（密码 admin123 的 BCrypt 哈希）——演示用，生产走独立初始化 */
@Component
public class AdminSeed implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(AdminSeed.class);

    private final UserRepository repository;
    private final PasswordEncoder passwordEncoder;

    public AdminSeed(UserRepository repository, PasswordEncoder passwordEncoder) {
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        if (repository.count() == 0) {
            repository.save(new User("admin", passwordEncoder.encode("admin123"), "ADMIN", "系统管理员"));
            log.info("seed_admin username=admin（密码 admin123，BCrypt 哈希入库）");
        }
    }
}
