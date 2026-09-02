package com.example.security;

import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 分层演示端点：/public（匿名）、/api/hello 与 /api/me（认证）、/api/admin/**（URL 级 ADMIN） */
@RestController
public class DemoController {

    private final SecurityBookService bookService;

    public DemoController(SecurityBookService bookService) {
        this.bookService = bookService;
    }

    @GetMapping("/public/ping")
    public Map<String, String> ping() {
        return Map.of("message", "pong");
    }

    @GetMapping("/api/hello")
    public Map<String, String> hello() {
        return Map.of("message", "hello, authenticated user");
    }

    /** 当前登录人：Authentication 由 Spring Security 注入（Filter 链认证后放入 SecurityContext） */
    @GetMapping("/api/me")
    public Map<String, Object> me(Authentication authentication) {
        List<String> authorities = authentication.getAuthorities().stream()
                .map(Object::toString)
                .toList();
        return Map.of("username", authentication.getName(), "authorities", authorities);
    }

    @GetMapping("/api/admin/users")
    public List<String> adminUsers() {
        return List.of("admin", "operator"); // 只有 ADMIN 能看（URL 级 hasRole）
    }

    @GetMapping("/api/books")
    public List<Map.Entry<Long, String>> listBooks(Authentication authentication) {
        return bookService.listAll(authentication); // 任何已认证用户可读
    }

    @DeleteMapping("/api/books/{id}")
    public Map<String, Object> deleteBook(@PathVariable long id, Authentication authentication) {
        bookService.deleteBook(id, authentication); // 方法级 @PreAuthorize("hasRole('ADMIN')") 拦在这
        return Map.of("deleted", id, "by", authentication.getName());
    }
}
