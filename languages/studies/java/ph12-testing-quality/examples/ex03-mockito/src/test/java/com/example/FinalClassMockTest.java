package com.example;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mockito 5.x 默认 inline mock maker：final 类 / final 方法也可 mock（主文档 4.2 的实测依据）。
 * 历史：final 无法被子类化，subclass mock maker 时代 mock 不了；5.x 用 JVM instrumentation 改写字节码。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Mockito 5.11.0（离线 mvn -o）。
 */
@ExtendWith(MockitoExtension.class)
class FinalClassMockTest {

    @Mock
    private FinalGreeter greeter;   // final 类照常生成替身，无需 mockito-inline 额外依赖

    @Test
    void finalClassAndMethod_canBeMockedByDefault() {
        when(greeter.greet("mosslau")).thenReturn("mocked!");

        assertEquals("mocked!", greeter.greet("mosslau"));

        verify(greeter).greet("mosslau");
    }
}
