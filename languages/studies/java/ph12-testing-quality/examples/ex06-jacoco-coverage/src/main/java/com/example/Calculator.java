package com.example;

/**
 * 被测类：只测 add 不测 divide（测试类见 src/test），
 * 故意留一个未覆盖方法 —— 演示「覆盖率 = 测到的 ÷ 全部」这个心智模型。
 */
public class Calculator {

    public int add(int a, int b) {
        return a + b;
    }

    public int divide(int a, int b) {
        // 原生 int 除法：b=0 抛 ArithmeticException（错误路径没测，覆盖率缺口所在）
        return a / b;
    }
}
