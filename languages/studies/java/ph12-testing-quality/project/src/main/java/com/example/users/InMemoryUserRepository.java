package com.example.users;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * 内存实现：HashMap 当「数据库」，id 为 0 时自动分配。
 * 生产中可用作原型/开发环境实现；测试中它是天然的 fake。
 */
public class InMemoryUserRepository implements UserRepository {

    private final Map<Long, User> store = new HashMap<>();
    private final Map<String, Long> emailToId = new HashMap<>();
    private long nextId = 1;

    @Override
    public Optional<User> findById(long id) {
        return Optional.ofNullable(store.get(id));
    }

    @Override
    public boolean existsByEmail(String email) {
        return emailToId.containsKey(email);
    }

    @Override
    public User save(User user) {
        long id = user.id() == 0 ? nextId++ : user.id();
        User stored = new User(id, user.name(), user.email());
        store.put(id, stored);
        emailToId.put(stored.email(), id);
        return stored;
    }

    @Override
    public boolean deleteById(long id) {
        User removed = store.remove(id);
        if (removed != null) {
            emailToId.remove(removed.email());
        }
        return removed != null;
    }
}
