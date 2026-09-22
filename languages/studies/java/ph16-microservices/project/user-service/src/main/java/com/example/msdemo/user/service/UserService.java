package com.example.msdemo.user.service;

import com.example.msdemo.common.api.BizCodes;
import com.example.msdemo.common.api.BizException;
import com.example.msdemo.user.domain.AppUser;
import com.example.msdemo.user.dto.UserDto;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 内存用户表（聚焦服务拆分语义，不引数据库——生产等价物见 ph15 project 的 JPA UserRepository）。
 * 种子用户：admin/admin123（ADMIN）、alice/alice123（USER）。
 */
@Service
public class UserService {

    private final ConcurrentHashMap<Long, AppUser> byId = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Long> idByUsername = new ConcurrentHashMap<>();
    private final AtomicLong idGen = new AtomicLong(1);
    /** 用户校验调用计数：供测试核对「幂等重放不会重复打下游」（白盒断言用） */
    private final AtomicInteger validationCount = new AtomicInteger();

    public UserService() {
        seed("admin", "admin123", "ADMIN");
        seed("alice", "alice123", "USER");
    }

    private void seed(String username, String password, String role) {
        String salt = Passwords.newSalt();
        AppUser user = new AppUser(idGen.getAndIncrement(), username, Passwords.hash(salt, password), salt, role);
        byId.put(user.id(), user);
        idByUsername.put(username, user.id());
    }

    /** 登录认证：用户不存在或口令不符都报 40101（不区分，防用户名枚举） */
    public AppUser authenticate(String username, String rawPassword) {
        Long id = username == null ? null : idByUsername.get(username);
        AppUser user = id == null ? null : byId.get(id);
        if (user == null || rawPassword == null
                || !Passwords.matches(user.salt(), rawPassword, user.passwordHash())) {
            throw new BizException(BizCodes.LOGIN_FAILED, "username or password incorrect");
        }
        return user;
    }

    /** 按 id 查用户（order-service 下单校验也走它，计数器随之 +1）；不存在 → 40400 */
    public UserDto findById(long id) {
        validationCount.incrementAndGet();
        AppUser user = byId.get(id);
        if (user == null) {
            throw new BizException(BizCodes.NOT_FOUND, "user not found: " + id);
        }
        return toDto(user);
    }

    public List<UserDto> list() {
        return byId.values().stream()
                .sorted(Comparator.comparingLong(AppUser::id))
                .map(this::toDto)
                .toList();
    }

    public UserDto create(String username, String password, String role) {
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            throw new BizException(BizCodes.BAD_REQUEST, "username/password required");
        }
        if (!"ADMIN".equals(role) && !"USER".equals(role)) {
            throw new BizException(BizCodes.BAD_REQUEST, "role must be ADMIN or USER");
        }
        String salt = Passwords.newSalt();
        AppUser user = new AppUser(idGen.getAndIncrement(), username, Passwords.hash(salt, password), salt, role);
        if (idByUsername.putIfAbsent(username, user.id()) != null) {
            throw new BizException(BizCodes.CONFLICT_USERNAME, "username exists: " + username);
        }
        byId.put(user.id(), user);
        return toDto(user);
    }

    public int validationCount() {
        return validationCount.get();
    }

    private UserDto toDto(AppUser user) {
        return new UserDto(user.id(), user.username(), user.role());
    }
}
