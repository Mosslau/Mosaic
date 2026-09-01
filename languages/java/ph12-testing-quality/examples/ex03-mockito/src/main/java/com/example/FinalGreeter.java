package com.example;

/**
 * final 类 + final 方法：演示 Mockito 5.x 默认（inline mock maker）已可 mock final 类型。
 * 历史背景：final 无法被子类化，老版本（subclass mock maker）mock 不了；
 * 5.x 默认 inline mock maker（JVM instrumentation 改写字节码），实测可 mock（见 FinalClassMockTest）。
 */
public final class FinalGreeter {

    public final String greet(String name) {
        return "Hello, " + name;
    }
}
