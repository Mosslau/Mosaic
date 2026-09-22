# ph20 阶段项目：简易 IOC 容器（mini-ioc）

## 需求

roadmap「20. 高级 Java 阶段」推荐项目之一——**简易 IOC 容器**：用纯 Java（零第三方依赖）实现一个注解驱动的迷你容器，覆盖 Spring IOC 的核心语义：**注册 → 装配（构造器/字段注入）→ 单例缓存 → 依赖按类型解析 → 循环依赖检测**。做完它，「反射 + 注解 = 框架能力」这条主线（roadmap 必会概念「反射和代理支撑框架能力」）就落地了；同时它是 [`exercises/sol-01-mini-ioc`](../exercises/sol-01-mini-ioc/) 手写容器的「工程版升级」——sol-01 用显式注册 + 最省事构造器展示容器本质，本项目用注解驱动 + 两种注入方式 + 循环检测展示框架形态。

## 目录结构

```
project/
├── README.md
└── mini-ioc/
    └── src/com/tenet/minioc/
        ├── Component.java      # 注解：标记组件，value 可指定 bean 名
        ├── Inject.java         # 注解：注入点（构造器 = 构造注入，字段 = 字段注入）
        ├── MiniContext.java    # 容器核心：注册/装配/单例缓存/循环检测（约 150 行）
        ├── SampleBeans.java    # 演示组件：Logger / EmailNotifier / OrderService / Metrics
        ├── CycleBeans.java     # 故意制造的循环依赖对（A→B→A）
        └── MiniIocDemo.java    # 演示入口（main，7 项断言）
```

## 功能清单

- [x] `@Component` 注册组件，bean 名取注解 value 或类名默认（首字母小写）
- [x] 构造器注入：容器选带 `@Inject` 的构造器，按参数类型递归解析依赖
- [x] 字段注入：对象创建后，容器反射注入所有带 `@Inject` 的字段
- [x] 单例作用域：同一 bean 名只创建一次，后续 getBean 返回缓存实例
- [x] 按类型解析：依赖参数/字段是接口时，注册表中找到唯一可赋值实现即注入
- [x] 歧义检测：多个实现可赋给同一接口时给出清晰报错（提示用 `@Component(value)` 命名）
- [x] 循环依赖检测：创建链 A→B→A 时抛 `CycleDependencyException` 并打印完整创建链
- [x] 组件可见性不设限：反射 + `setAccessible` 装配，包内类也能被管理（教学点）

## 验证状态（如实标注）

**已验证**（OpenJDK 17.0.18，Homebrew 本机实测）：编译通过，`MiniIocDemo` 输出 7/7 PASS，含「构造注入链路可用」「字段注入与构造注入共享同一 Logger 单例」「两次 getBean 同一实例」「接口唯一实现解析成功」「未注册报错清晰」「循环依赖被检测且消息含 `cycleA -> cycleB -> cycleA`」。

```bash
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
cd mini-ioc
$JAVAC -encoding UTF-8 -d /tmp/tl20-cls src/com/tenet/minioc/*.java
$JAVA -cp /tmp/tl20-cls com.tenet.minioc.MiniIocDemo
```

## 验收标准

- 运行 `MiniIocDemo` 输出 7 行 PASS 且以 `ALL PASS: 7/7` 结束
- 你能回答这三个「为什么」（对照主文档 3.8 反射部分）：
  1. 为什么 `Metrics` 的 `private Logger logger` 字段能被容器赋值？（`getDeclaredField` + `setAccessible`）
  2. 为什么 `OrderService` 的构造参数声明为 `Notifier` 接口时容器能注入 `EmailNotifier`？（`isAssignableFrom` 找唯一实现）
  3. 为什么容器能捕获 A→B→A 循环？（创建栈：发现当前 bean 正在创建中即异常）
- 扩展一题：给容器加一个 `@Component("custom")` 的第二个 Notifier 实现，观察 `OrderService` 装配报「歧义」错误，再用 `@Component(value)` + 构造器显式取名解决（体验 Spring 里 `@Qualifier` 解决的问题）

## 与真实 Spring 的差距（诚实清单）

| 本容器 | Spring | 说明 |
|--------|--------|------|
| 手动 `register(类...)` | classpath/注解扫描 | 无第三方字节码扫描库，注册方式简化；语义（注册表+装配）一致 |
| 单例固定 | singleton / prototype / request / session 多作用域 | 只实现默认作用域 |
| 构造器+字段注入 | 构造器/字段/setter + `@Qualifier`/`@Primary`/泛型注入 | 注入面收窄 |
| 循环依赖直接抛错 | 三级缓存支持字段/setter 循环；构造器循环同样抛 | 教学版选择「先检测」，不解决 |
| 无 AOP/事务/事件 | BeanPostProcessor 全生态 | 容器之外的能力属 ph15 已学的 Spring 家族，不在本容器范围内 |

## 扩展方向

- **加 BeanPostProcessor 钩子**：在 bean 创建前后留扩展点（`beforeInit/afterInit`），仿照 Spring 的 `BeanPostProcessor`——这是 AOP 代理（ph15）能织入的机制位置
- **加 scope**：`@Scope("prototype")` 每次 getBean 新建——体会「单例与原型」的选择对状态的影响
- **接 exercises/sol-03 RPC**：把 `services` 注册表换成 MiniContext，RPC 服务端就能从容器取 bean——反射装配 + 反射 dispatch 串成一条线（RPC demo 进阶）
- **对比参考**：本容器「创建链 + 单例缓存」的思维模型，读 Spring 源码时对应 `DefaultSingletonBeanRegistry` 的 `singletons/singletonFactories` 三级缓存结构
