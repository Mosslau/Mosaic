package com.example;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 参数化测试：一组输入一组预期，代替 N 个几乎相同的测试方法。
 * 对应主文档 3.2；完整工程见 examples/ex02-parameterized/。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1（离线 mvn -o）。
 */
class StringUtilsParamTest {

    // @NullAndEmptySource 提供 null 与 "" 两个值，@ValueSource 再补空白字符
    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   ", "\t\n"})
    void isBlank_shouldReturnTrue(String input) {
        assertTrue(StringUtils.isBlank(input), () -> "isBlank(" + input + ") 应为 true");
    }

    @ParameterizedTest
    @ValueSource(strings = {"abc", " a ", "x"})
    void isBlank_shouldReturnFalse(String input) {
        assertFalse(StringUtils.isBlank(input));
    }

    // CsvSource：每行一个用例，逗号分隔参数。
    // 实测（JUnit 5.10.1）：裸空单元格 → null；引号包裹 '' → 空串 ""（本行两个都是 ''）
    @ParameterizedTest
    @CsvSource({
            "abc,cba",
            "hello,olleh",
            "a,a",
            "'',''"
    })
    void reverse_basic(String input, String expected) {
        assertEquals(expected, StringUtils.reverse(input));
    }

    // MethodSource：工厂方法返回 Arguments 流，适合表达复杂的「输入 + 预期」对
    @ParameterizedTest
    @MethodSource("reverseCases")
    void reverse_fromMethodSource(String input, String expected) {
        assertEquals(expected, StringUtils.reverse(input));
    }

    static Stream<Arguments> reverseCases() {
        return Stream.of(
                Arguments.of("Java", "avaJ"),
                Arguments.of("", ""),
                Arguments.of(null, ""));   // null 视为空串
    }
}
