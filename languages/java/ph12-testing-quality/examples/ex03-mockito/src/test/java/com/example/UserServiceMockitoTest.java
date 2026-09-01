package com.example;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mockito 单元测试：stub（when/thenReturn、thenThrow）+ 交互验证（verify/never/argThat）。
 * 对应主文档 3.3；完整工程见 examples/ex03-mockito/。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Mockito 5.11.0（离线 mvn -o）。
 */
@ExtendWith(MockitoExtension.class)
class UserServiceMockitoTest {

    @Mock
    private UserRepository repo;   // Mockito 生成 UserRepository 的替身

    private UserService service;

    @BeforeEach
    void setUp() {
        // 构造器注入 mock —— 被测服务与真实数据库完全隔离
        service = new UserService(repo);
    }

    @Test
    void greeting_returnsHello_whenUserExists() {
        // stub：规定「调用 findById(1L) 时返回该用户」
        when(repo.findById(1L)).thenReturn(Optional.of(new User(1L, "mosslau", "m@x.com")));

        assertEquals("Hello, mosslau!", service.greeting(1L));

        verify(repo).findById(1L);   // 验证交互确实发生了（且只发生一次）
    }

    @Test
    void greeting_throws_whenUserMissing() {
        when(repo.findById(99L)).thenReturn(Optional.empty());

        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                () -> service.greeting(99L));
        assertEquals("用户不存在: 99", ex.getMessage());
    }

    @Test
    void register_rejectsDuplicateEmail() {
        when(repo.existsByEmail("dup@x.com")).thenReturn(true);

        assertThrows(IllegalArgumentException.class,
                () -> service.register(new User(2L, "dup", "dup@x.com")));

        verify(repo, never()).save(any());   // 重复邮箱不许落库 —— 验证「没有发生」
    }

    @Test
    void register_savesNewUser() {
        when(repo.existsByEmail("new@x.com")).thenReturn(false);

        service.register(new User(3L, "new", "new@x.com"));

        verify(repo).save(argThat(u -> u.name().equals("new")));   // 参数匹配器
    }

    @Test
    void repositoryFailure_isPropagated() {
        // stub 抛异常：模拟数据库挂掉，被测服务不应吞掉异常
        when(repo.findById(1L)).thenThrow(new RuntimeException("数据库连接失败"));

        assertThrows(RuntimeException.class, () -> service.greeting(1L));
    }
}
