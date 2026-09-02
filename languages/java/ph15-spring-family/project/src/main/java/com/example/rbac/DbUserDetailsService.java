package com.example.rbac;

import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 数据库版 UserDetailsService：Security 登录时按用户名查 JPA 用户表。
 * 对比 examples/ex06 的内存用户——「用户从哪来」从配置变成了数据，其余认证逻辑零改动，
 * 这正是 UserDetailsService 抽象的价值。
 */
@Service
public class DbUserDetailsService implements UserDetailsService {

    private final UserRepository repository;

    public DbUserDetailsService(UserRepository repository) {
        this.repository = repository;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        User user = repository.findByUsername(username)
                .orElseThrow(() -> new UsernameNotFoundException("用户不存在: " + username));
        return org.springframework.security.core.userdetails.User.builder()
                .username(user.getUsername())
                .password(user.getPassword())           // BCrypt 哈希
                .authorities(List.of(new SimpleGrantedAuthority("ROLE_" + user.getRole())))
                .build();
    }
}
