/*
 * project/mini-ioc/src/com/tenet/minioc/CycleBeans.java
 * 故意制造的循环依赖对（A → B → A），用于验证容器的循环检测：
 * 真实 Spring 用「三级缓存 + 提前暴露引用」支持构造器外的循环；
 * 本教学容器选择更简单的策略——检测到即抛 CycleDependencyException 并打印完整创建链。
 */
package com.tenet.minioc;

@Component("cycleA")
final class CycleA {
    @Inject
    CycleA(CycleB b) {
    }
}

@Component("cycleB")
final class CycleB {
    @Inject
    CycleB(CycleA a) {
    }
}
