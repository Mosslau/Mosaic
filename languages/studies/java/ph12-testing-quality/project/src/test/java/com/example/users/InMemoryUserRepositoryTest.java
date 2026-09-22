package com.example.users;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/** 内存仓库自身的行为测试（它同时是别的测试的 fake，自己也要测）。 */
class InMemoryUserRepositoryTest {

    private InMemoryUserRepository repo;

    @BeforeEach
    void setUp() {
        repo = new InMemoryUserRepository();
    }

    @Test
    void save_assignsIncrementingIds_whenIdIsZero() {
        User a = repo.save(new User(0L, "a", "a@x.com"));
        User b = repo.save(new User(0L, "b", "b@x.com"));

        assertThat(a.id()).isEqualTo(1L);
        assertThat(b.id()).isEqualTo(2L);
    }

    @Test
    void save_keepsProvidedId() {
        User saved = repo.save(new User(42L, "fixed", "fixed@x.com"));

        assertThat(saved.id()).isEqualTo(42L);
        assertThat(repo.findById(42L)).contains(saved);
    }

    @Test
    void findById_missing_returnsEmpty() {
        assertThat(repo.findById(1L)).isEmpty();
    }

    @Test
    void existsByEmail_followsSaveAndDelete() {
        User saved = repo.save(new User(0L, "a", "a@x.com"));

        assertThat(repo.existsByEmail("a@x.com")).isTrue();
        repo.deleteById(saved.id());
        assertThat(repo.existsByEmail("a@x.com")).isFalse();
    }

    @Test
    void deleteById_returnsWhetherRemoved() {
        User saved = repo.save(new User(0L, "a", "a@x.com"));

        assertThat(repo.deleteById(saved.id())).isTrue();
        assertThat(repo.deleteById(saved.id())).isFalse();   // 再删同一 id 返回 false
        assertThat(repo.findById(saved.id())).isEmpty();
    }

    @Test
    void save_twiceWithSameEmail_replacesMapping() {
        repo.save(new User(0L, "a", "same@x.com"));
        User second = repo.save(new User(0L, "b", "same@x.com"));

        assertThat(repo.existsByEmail("same@x.com")).isTrue();
        assertThat(second.id()).isEqualTo(2L);
    }
}
