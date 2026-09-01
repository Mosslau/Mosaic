package com.example;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * JUnit 5 基础：断言（正常路径 + 错误路径）与生命周期。
 * 对应主文档 3.1；完整工程见 examples/ex01-junit5-basic/。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1（离线 mvn -o）。
 */
@DisplayName("Calculator 断言与生命周期")
class CalculatorLifecycleTest {

    private Calculator calculator;

    @BeforeAll
    static void beforeAll() {
        // 每个测试类只执行一次（static）
        System.out.println("beforeAll: 类级初始化（如连接池）");
    }

    @AfterAll
    static void afterAll() {
        System.out.println("afterAll: 类级清理（如关连接）");
    }

    @BeforeEach
    void setUp() {
        // 每个测试方法执行前都跑 —— 保证每个测试从干净状态开始
        calculator = new Calculator();
        System.out.println("beforeEach: 新建被测对象");
    }

    @AfterEach
    void tearDown() {
        System.out.println("afterEach: 测试后清理");
    }

    @Test
    @DisplayName("正常路径：1 + 2 = 3")
    void add() {
        assertEquals(3, calculator.add(1, 2));
    }

    @Test
    @DisplayName("错误路径：除数为 0 抛 IllegalArgumentException")
    void divideByZeroThrows() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> calculator.divide(10, 0));   // 注意：传的是「执行动作」lambda，不是结果
        assertEquals("除数不能为 0", ex.getMessage());
    }

    @Test
    @DisplayName("assertAll 聚合多个断言：失败时全部报告，而不是停在第一个")
    void multipleAssertions() {
        assertAll("四则运算",
                () -> assertEquals(4, calculator.add(2, 2)),
                () -> assertEquals(0, calculator.subtract(2, 2)),
                () -> assertEquals(6, calculator.multiply(2, 3)),
                () -> assertEquals(2, calculator.divide(6, 3)));
    }
}
