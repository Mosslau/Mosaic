package com.example;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 只测 add，不测 divide —— 跑完后打开 target/site/jacoco/index.html 看覆盖率缺口。
 * 实测数字见 examples/ex06-jacoco-coverage/README 与本工程 target/site/jacoco/jacoco.csv。
 */
class CalculatorTest {

    @Test
    void add() {
        assertEquals(3, new Calculator().add(1, 2));
    }
}
