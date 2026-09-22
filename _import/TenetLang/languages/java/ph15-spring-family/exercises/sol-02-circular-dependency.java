// exercises/sol-02-circular-dependency.java —— 练习 2 参考实现：构造器循环依赖实测与 @Lazy 解法
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Framework 6.1.8（纯核心容器，无 Web）
// 验证状态：已验证（本机离线 mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 2, Failures: 0, Errors: 0
//   （constructorCycleFailsFastAtRefresh：Ping↔Pong 纯构造器循环 → 启动抛
//     UnsatisfiedDependencyException，根因 BeanCurrentlyInCreationException「currently in creation」；
//     lazyBreaksTheCycle：@Lazy 注入延迟代理 → 容器能启动，调用输出 ping(lazy) -> pong）
// ---------------------------------------------------------------------------
// 本练习工程 = 标准 Maven 工程 + 下列文件（按注释里的文件路径逐个写入）：
//   pom.xml 直接复制 ../examples/ex01-spring-core-ioc-lifecycle/pom.xml，artifactId 改成 sol02-circular-dependency
//   其余文件如下。验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 教学点：循环依赖的两种形态——字段/setter 注入 Spring 能靠「提前暴露早期引用」解开；
//   构造器注入做不到（对象没建完无法暴露），启动即 fail-fast。修法：(a) 重构去掉环；
//   (b) 一方改 setter/字段注入；(c) @Lazy 在参数上（本练习的解法）注入延迟代理。
//   依赖环本身是设计味道——优先考虑拆环，@Lazy 是兜底。
// ===========================================================================
// src/main/java/com/example/cycle/PingService.java
// ===========================================================================
package com.example.cycle;

import org.springframework.stereotype.Service;

/** 循环依赖的一半：Ping 需要 Pong */
@Service
public class PingService {

    private final PongService pong;

    public PingService(PongService pong) {
        this.pong = pong;
    }

    public String ping() {
        return "ping -> " + pong.pong();
    }
}

// ===========================================================================
// src/main/java/com/example/cycle/PongService.java
// ===========================================================================
package com.example.cycle;

import org.springframework.stereotype.Service;

/** 循环依赖的另一半：Pong 需要 Ping——构造器互相引用，容器无法决定先建谁 */
@Service
public class PongService {

    private final PingService ping;

    public PongService(PingService ping) {
        this.ping = ping;
    }

    public String pong() {
        return "pong";
    }
}

// ===========================================================================
// src/main/java/com/example/cycle/CycleConfig.java
// ===========================================================================
package com.example.cycle;

import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;

/** 只扫 cycle 包：构造器循环的 Ping ↔ Pong */
@Configuration
@ComponentScan("com.example.cycle")
public class CycleConfig {
}

// ===========================================================================
// src/main/java/com/example/fix/PongService.java
// ===========================================================================
package com.example.fix;

import org.springframework.stereotype.Service;

@Service
public class PongService {

    public String pong() {
        return "pong";
    }
}

// ===========================================================================
// src/main/java/com/example/fix/PingLazyService.java
// ===========================================================================
package com.example.fix;

import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;

/** 解法 A（本练习用）：@Lazy 打断构造期循环——参数先注入「延迟代理」，首次调用时才真正解析 */
@Service
public class PingLazyService {

    private final PongService pong;

    public PingLazyService(@Lazy PongService pong) {
        this.pong = pong;
    }

    public String ping() {
        return "ping(lazy) -> " + pong.pong();
    }
}

// ===========================================================================
// src/main/java/com/example/fix/FixConfig.java
// ===========================================================================
package com.example.fix;

import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;

/** 只扫 fix 包：@Lazy 解法（PingLazy ↔ Pong，Pong 无回依赖） */
@Configuration
@ComponentScan("com.example.fix")
public class FixConfig {
}

// ===========================================================================
// src/test/java/com/example/CircularDependencyTest.java
// ===========================================================================
package com.example;

import com.example.cycle.CycleConfig;
import com.example.cycle.PingService;
import com.example.fix.FixConfig;
import com.example.fix.PingLazyService;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * sol-02 测试：构造器循环依赖在 refresh 时 fail-fast；@Lazy 解法让容器能启动。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
class CircularDependencyTest {

    /** 纯构造器循环：Ping ↔ Pong 谁都没法先建——启动即抛 BeanCurrentlyInCreationException */
    @Test
    void constructorCycleFailsFastAtRefresh() {
        assertThatThrownBy(() -> {
            try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(CycleConfig.class)) {
                ctx.getBean(PingService.class);
            }
        }).isInstanceOf(Exception.class).hasMessageContaining("currently in creation");
    }

    /** @Lazy 解法：延迟代理注入，容器能启动，调用时真正拿到对方 */
    @Test
    void lazyBreaksTheCycle() {
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(FixConfig.class)) {
            PingLazyService ping = ctx.getBean(PingLazyService.class);
            assertThat(ping.ping()).isEqualTo("ping(lazy) -> pong");
        }
    }
}

