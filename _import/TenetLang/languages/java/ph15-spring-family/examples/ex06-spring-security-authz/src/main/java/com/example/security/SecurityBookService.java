package com.example.security;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 方法级授权落点：@PreAuthorize 写在【业务方法】上，而不是 URL 上——
 * URL 规则表达不了「同控制器里 GET 人人可读、DELETE 只要 ADMIN」这类细粒度，
 * 授权跟着业务走（service 层），Controller 不掺和权限判断（roadmap：Controller 不写复杂业务）。
 * 为聚焦「授权分层」，藏书用内存 Map 模拟数据源、未接持久化——持久化访问形态见 examples/ex05 与 project。
 */
@Service
public class SecurityBookService {

    private final Map<Long, String> books = new ConcurrentHashMap<>(Map.of(1L, "Spring 实战", 2L, "Effective Java"));

    public List<Map.Entry<Long, String>> listAll(Authentication authentication) {
        return List.copyOf(books.entrySet());
    }

    @PreAuthorize("hasRole('ADMIN')")
    public void deleteBook(long id, Authentication authentication) {
        books.remove(id);
    }
}
