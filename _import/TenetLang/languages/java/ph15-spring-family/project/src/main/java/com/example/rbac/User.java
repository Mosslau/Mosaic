package com.example.rbac;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 用户实体：用户名唯一、密码存 BCrypt 哈希、单角色（ADMIN/USER）——RBAC 的最小形态。
 * @Table(name = "app_user")：user 是 SQL 保留字，避免与 HSQLDB 关键字冲突。
 * 教学点：实体只描述形状，SQL 由 Hibernate ddl-auto 生成、访问走 UserRepository（见 examples/ex05）。
 */
@Entity
@Table(name = "app_user")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, length = 100)
    private String password; // BCrypt 哈希（绝不明文）

    @Column(nullable = false, length = 20)
    private String role; // ADMIN | USER

    @Column(nullable = false, length = 50)
    private String displayName;

    protected User() {
        // JPA 无参构造（Hibernate 反射用）；业务创建走带参构造
    }

    public User(String username, String password, String role, String displayName) {
        this.username = username;
        this.password = password;
        this.role = role;
        this.displayName = displayName;
    }

    public Long getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getPassword() {
        return password;
    }

    public String getRole() {
        return role;
    }

    public String getDisplayName() {
        return displayName;
    }
}
