package com.example;

/**
 * 被测类：加减乘除。
 * divide 显式校验除数为 0 并抛 IllegalArgumentException —— 给错误路径测试提供确定的行为。
 */
public class Calculator {

    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }

    public int multiply(int a, int b) {
        return a * b;
    }

    public int divide(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("除数不能为 0");
        }
        return a / b;
    }
}
