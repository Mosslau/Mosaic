package com.example.users;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** 单元测试：Mockito 隔离 UserRepository，只测 UserService 的编排与校验逻辑。 */
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository repo;

    private UserService service;

    @BeforeEach
    void setUp() {
        service = new UserService(repo);
    }

    @Test
    void register_savesUserWithTrimmedFields() {
        when(repo.existsByEmail("m@x.com")).thenReturn(false);
        when(repo.save(any())).thenReturn(new User(1L, "mosslau", "m@x.com"));

        User created = service.register("  mosslau  ", "  m@x.com  ");

        assertThat(created.id()).isEqualTo(1L);
        // save 收到的参数已被规范化：姓名/邮箱都去掉了首尾空白
        verify(repo).save(argThat(u -> u.name().equals("mosslau") && u.email().equals("m@x.com")));
    }

    @Test
    void register_rejectsDuplicateEmail_withoutSaving() {
        when(repo.existsByEmail("dup@x.com")).thenReturn(true);

        assertThatThrownBy(() -> service.register("dup", "dup@x.com"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("已注册");

        verify(repo, never()).save(any());
    }

    @Test
    void register_rejectsBlankName_withoutTouchingRepo() {
        assertThatThrownBy(() -> service.register("   ", "m@x.com"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("姓名");

        // 校验失败连 existsByEmail 都不该调用 —— 业务规则先于存储
        verify(repo, never()).existsByEmail(anyString());
        verify(repo, never()).save(any());
    }

    @Test
    void findById_returnsUser_whenExists() {
        when(repo.findById(7L)).thenReturn(Optional.of(new User(7L, "bob", "bob@x.com")));

        assertThat(service.findById(7L).email()).isEqualTo("bob@x.com");
    }

    @Test
    void findById_throws_whenMissing() {
        when(repo.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.findById(99L))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("不存在");
    }

    @Test
    void updateEmail_changesEmail_whenAvailable() {
        when(repo.findById(1L)).thenReturn(Optional.of(new User(1L, "mosslau", "old@x.com")));
        when(repo.existsByEmail("new@x.com")).thenReturn(false);
        when(repo.save(any())).thenReturn(new User(1L, "mosslau", "new@x.com"));

        User updated = service.updateEmail(1L, "new@x.com");

        assertThat(updated.email()).isEqualTo("new@x.com");
        // 保存时保留原 id 与姓名，只换邮箱
        verify(repo).save(argThat(u -> u.id() == 1L && u.name().equals("mosslau") && u.email().equals("new@x.com")));
    }

    @Test
    void updateEmail_rejectsOccupiedEmail() {
        when(repo.findById(1L)).thenReturn(Optional.of(new User(1L, "mosslau", "old@x.com")));
        when(repo.existsByEmail("taken@x.com")).thenReturn(true);

        assertThatThrownBy(() -> service.updateEmail(1L, "taken@x.com"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("占用");

        verify(repo, never()).save(any());
    }

    @Test
    void deleteById_returnsRepoResult() {
        when(repo.deleteById(1L)).thenReturn(true);
        when(repo.deleteById(2L)).thenReturn(false);

        assertThat(service.deleteById(1L)).isTrue();
        assertThat(service.deleteById(2L)).isFalse();
        verify(repo).deleteById(eq(1L));
        verify(repo).deleteById(eq(2L));
    }
}
