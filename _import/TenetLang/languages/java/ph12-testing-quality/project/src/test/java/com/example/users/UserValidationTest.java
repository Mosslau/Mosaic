package com.example.users;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 参数化测试：把校验规则写成一章「事实表」，每行一个输入 + 预期。 */
class UserValidationTest {

    private UserService service;

    @BeforeEach
    void setUp() {
        service = new UserService(new InMemoryUserRepository());
    }

    // 合法邮箱：一行一组输入，全部应注册成功
    @ParameterizedTest
    @CsvSource({
            "mosslau@example.com",
            "a.b+c@sub.example.org",
            "user_1@x.io",
            "a@b.co.jp"
    })
    void register_acceptsValidEmails(String email) {
        User created = service.register("ok", email);

        assertThat(created.email()).isEqualTo(email.trim());
    }

    // 非法邮箱：全部应抛 IllegalArgumentException
    @ParameterizedTest
    @ValueSource(strings = {"", "plain", "a@b", "a@b.", "@x.com", "a b@c.com", "a@b..com", "a@@b.com"})
    void register_rejectsInvalidEmails(String email) {
        assertThatThrownBy(() -> service.register("ok", email))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("邮箱");
    }

    // 姓名为 null 或空白：全部拒绝
    @ParameterizedTest
    @NullSource
    @ValueSource(strings = {"", "   ", "\t\n"})
    void register_rejectsBlankNames(String name) {
        assertThatThrownBy(() -> service.register(name, "m@x.com"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("姓名");
    }

    // 邮箱规范化：首尾空白应被去掉后再落库
    @ParameterizedTest
    @MethodSource("emailsWithPadding")
    void register_trimsEmailPadding(String raw, String expected) {
        User created = service.register("ok", raw);

        assertThat(created.email()).isEqualTo(expected);
    }

    static Stream<org.junit.jupiter.params.provider.Arguments> emailsWithPadding() {
        return Stream.of(
                org.junit.jupiter.params.provider.Arguments.of("  m@x.com  ", "m@x.com"),
                org.junit.jupiter.params.provider.Arguments.of("\tm@x.com\n", "m@x.com"));
    }

    @Test
    void register_trimsNamePadding() {
        User created = service.register("  mosslau  ", "m@x.com");

        assertThat(created.name()).isEqualTo("mosslau");
    }
}
