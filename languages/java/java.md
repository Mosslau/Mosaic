# Java 语言学习 Roadmap

> 面向企业级后端、微服务、高并发系统和车联网数据平台，重点建立 OOP 建模、JVM、Spring 生态和工程交付能力。

## 1. Java 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标

能写简单 Java 程序，理解 JDK、JRE、JVM 和 Java 程序结构。

### 学习内容

- JDK/JRE/JVM、javac/java 编译与运行
- class 与 main 方法
- 变量、常量、基本类型
- 基本类型 vs 引用类型
- String（不可变、字符串池）
- 运算符、条件判断、循环、数组
- 输入输出
- var 局部变量类型推导（Java 10+）

### 必会概念

- Java 代码先编译成字节码再在 JVM 上运行
- 基本类型和引用类型不同
- main 是程序入口
- 数组长度固定且会做边界检查
- var 保持静态类型，类型由编译期推导

### 示例

```java
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, Java");
    }
}
```

### 练习

- 计算器
- 判断素数
- 九九乘法表
- 数组最大值、最小值、平均值

### 阶段验收

- 能编译并运行单文件 Java 程序
- 能解释 JDK/JRE/JVM 区别
- 能用循环和数组完成基础练习

### 推荐项目

- 成绩统计工具
- 猜数字游戏

## 2. 面向对象 OOP 阶段

> 📖 详细展开版见 [ph02-oop/02-oop.md](./ph02-oop/02-oop.md)

### 目标

理解类、对象、封装、继承、多态和接口。

### 学习内容

- class、object、field、method
- 构造方法、this、static、final
- 封装、继承、多态
- abstract class、interface
- override 与 overload
- record（Java 16+ 不可变数据类）
- sealed class（Java 17 受控继承）

### 必会概念

- 对象是状态和行为的组合
- 封装用于保护不变量
- 继承表达 is-a，组合常常更灵活
- 接口表达能力边界
- record 自动生成构造、访问器、equals、hashCode、toString
- sealed class 明确限定子类范围，让继承更可控

### 示例

```java
interface Sensor {
    double read();
}

class TemperatureSensor implements Sensor {
    public double read() { return 36.5; }
}
```

### 练习

- 学生类 / 车辆类 / 电机类建模
- 用 record 定义设备状态
- 用 sealed class 限制状态继承层次
- 设备管理系统

### 阶段验收

- 能设计清晰类模型
- 能用 record 表达不可变数据
- 能解释重载和重写
- 能用接口解耦依赖

### 推荐项目

- 学生管理系统
- 设备管理系统

## 3. Java 常用类阶段

> 📖 详细展开版见 [ph03-common-classes/03-common-classes.md](./ph03-common-classes/03-common-classes.md)

### 目标

熟悉标准库中最常用的基础类。

### 学习内容

- String、StringBuilder、StringBuffer
- Text Blocks（`"""..."""`，Java 15+）
- Math、Random、BigDecimal
- LocalDate、LocalDateTime、DateTimeFormatter
- 包装类型与自动装箱拆箱

### 必会概念

- String 不可变
- 大量拼接优先用 StringBuilder
- 金额计算用 BigDecimal
- 优先使用 java.time 处理时间

### 示例

```java
StringBuilder sb = new StringBuilder();
sb.append("Hello");
sb.append(" Java");
System.out.println(sb.toString());
```

### 练习

- 字符串反转
- 字符频次统计
- 金额计算
- 日期格式化

### 阶段验收

- 能正确选择 String/StringBuilder
- 能避免浮点金额误差
- 能处理常见日期时间格式

### 推荐项目

- 验证码生成器
- 日期工具类

## 4. 集合框架阶段

> 📖 详细展开版见 [ph04-collections/04-collections.md](./ph04-collections/04-collections.md)

### 目标

熟练使用 Java 常用集合。

### 学习内容

- List、Set、Map、Queue、Deque
- ArrayList、LinkedList
- HashMap、LinkedHashMap、TreeMap
- HashSet、TreeSet、ConcurrentHashMap
- PriorityQueue

### 必会概念

- 集合接口和实现要分开理解
- HashMap 不保证顺序
- ConcurrentHashMap 适合并发读写场景
- 集合遍历修改要注意 ConcurrentModificationException

### 示例

```java
Map<String, Integer> scores = new HashMap<>();
scores.put("Alice", 90);
scores.put("Bob", 85);
```

### 练习

- List 管理学生
- Map 统计词频
- Set 去重
- PriorityQueue 任务调度

### 阶段验收

- 能按场景选择集合
- 能解释 HashMap 基本原理
- 能避免遍历修改错误

### 推荐项目

- LRU Cache
- 设备状态表

## 5. 泛型阶段

> 📖 详细展开版见 [ph05-generics/05-generics.md](./ph05-generics/05-generics.md)

### 目标

理解类型安全和通用代码设计。

### 学习内容

- 泛型类、泛型方法、泛型接口
- 类型擦除
- 通配符 ?
- 上界 extends、下界 super

### 必会概念

- 泛型主要提供编译期类型安全
- 运行期存在类型擦除
- PECS 原则：Producer Extends, Consumer Super
- 不要滥用原始类型

### 示例

```java
class Box<T> {
    private T value;
    public void set(T value) { this.value = value; }
    public T get() { return value; }
}
```

### 练习

- 泛型 Box
- 泛型 Pair
- 泛型 Stack
- 泛型 Repository

### 阶段验收

- 能解释类型擦除
- 能使用 extends/super 通配符
- 能设计简单泛型类

### 推荐项目

- 泛型缓存容器
- 泛型分页结果

## 6. 异常处理阶段

> 📖 详细展开版见 [ph06-exception/06-exception.md](./ph06-exception/06-exception.md)

### 目标

写出稳定、可维护的错误处理代码。

### 学习内容

- try/catch/finally
- throw、throws
- checked exception、unchecked exception
- 自定义异常、异常链
- try-with-resources

### 必会概念

- 异常用于异常路径，不应吞掉异常
- 业务异常要有清晰语义
- 资源释放优先用 try-with-resources
- 异常信息要保留上下文

### 示例

```java
try {
    int result = 10 / 0;
} catch (ArithmeticException e) {
    System.out.println("不能除以 0");
}
```

### 练习

- 安全除法
- 文件读取异常
- 登录异常
- 参数校验异常

### 阶段验收

- 能设计业务异常体系
- 能正确释放资源
- 能区分 checked/unchecked exception

### 推荐项目

- 统一异常处理 demo
- 业务错误码体系

## 7. IO 与文件操作阶段

> 📖 详细展开版见 [ph07-io-file/07-io-file.md](./ph07-io-file/07-io-file.md)

### 目标

能读写文件并处理数据流。

### 学习内容

- File、InputStream、OutputStream
- Reader、Writer、BufferedReader
- NIO、Path、Files
- 序列化、CSV/JSON 文件处理

### 必会概念

- 字节流处理二进制，字符流处理文本
- 缓冲能提升 IO 性能
- 文件路径要考虑平台差异
- IO 必须处理异常

### 示例

```java
List<String> lines = Files.readAllLines(Path.of("data.txt"));
for (String line : lines) {
    System.out.println(line);
}
```

### 练习

- 读取配置文件
- 日志分析
- CSV 解析
- 批量重命名

### 阶段验收

- 能读写文本文件
- 能处理文件异常
- 能用 NIO 简化文件操作

### 推荐项目

- 文件复制工具
- 目录统计工具

## 8. Lambda 与 Stream 阶段

> 📖 详细展开版见 [ph08-lambda-stream/08-lambda-stream.md](./ph08-lambda-stream/08-lambda-stream.md)

### 目标

掌握现代 Java 的函数式数据处理方式。

### 学习内容

- Lambda 表达式
- 函数式接口
- Predicate、Consumer、Function、Supplier
- Stream API
- map、filter、reduce、collect、groupingBy、Optional
- Switch Expressions（`->` / `yield`，Java 14+）
- Pattern Matching for instanceof / switch（Java 16+/21+）

### 必会概念

- Stream 描述数据处理流水线
- 中间操作惰性执行
- Optional 用于表达可能为空
- Switch Expressions 消除 break 穿透，用箭头语法和 yield 返回值
- Pattern Matching 消除 instanceof + 强转的样板代码
- 过度链式调用会降低可读性

### 示例

```java
List<Integer> result = nums.stream()
        .filter(n -> n > 2)
        .map(n -> n * 2)
        .toList();
```

### 练习

- 过滤学生成绩并统计平均分
- 按班级分组
- 设备状态筛选
- 用 Switch Expressions 重写 if-else 分支
- 用 Pattern Matching 改写 instanceof 判断

### 阶段验收

- 能写常见 Stream 操作
- 能用 Switch Expressions 替代传统 switch
- 能用 Pattern Matching 简化类型判断
- 能合理使用 Optional
- 能判断何时不用 Stream

### 推荐项目

- 日志过滤统计
- 报表分组统计

## 9. 多线程与并发阶段

> 📖 详细展开版见 [ph09-concurrency/09-concurrency.md](./ph09-concurrency/09-concurrency.md)

### 目标

能写安全的并发 Java 程序。

### 学习内容

- Thread、Runnable、Callable、Future
- ExecutorService、线程池
- synchronized、volatile
- Lock、ReentrantLock、Condition
- Atomic、ConcurrentHashMap、CompletableFuture
- Virtual Threads（Java 21 虚拟线程）
- Structured Concurrency、Scoped Values（Java 21+）

### 必会概念

- 线程池比手动创建线程更可控
- volatile 保证可见性但不保证复合操作原子性
- 锁要避免死锁和过大粒度
- CompletableFuture 适合异步编排
- 虚拟线程由 JVM 调度，可创建百万级，适合"每个请求一个线程"模型
- 虚拟线程遇到阻塞 IO 时会自动让出平台线程，无需 async/await 语法

### 示例

```java
ExecutorService executor = Executors.newFixedThreadPool(4);
executor.submit(() -> System.out.println("task"));
executor.shutdown();

// Java 21 虚拟线程
try (var vtExecutor = Executors.newVirtualThreadPerTaskExecutor()) {
    vtExecutor.submit(() -> System.out.println("virtual thread task"));
}
```

### 练习

- 多线程计数器
- 生产者消费者
- 线程安全队列
- 异步日志系统
- 用虚拟线程实现高并发任务处理

### 阶段验收

- 能解释线程池参数
- 能说明虚拟线程和平台线程的区别及适用场景
- 能避免常见竞态
- 能用并发集合解决问题

### 推荐项目

- 线程池任务调度器
- 并发文件处理工具

## 10. JVM 阶段

> 📖 详细展开版见 [ph10-jvm/10-jvm.md](./ph10-jvm/10-jvm.md)

### 目标

理解 Java 程序运行机制并具备性能分析能力。

### 学习内容

- 类加载、字节码、JIT
- 栈、堆、方法区、程序计数器
- GC Roots、Minor GC、Full GC
- JVM 参数
- jps、jstack、jmap、jstat、Arthas

### 必会概念

- Java 代码编译为 class 字节码
- GC 自动回收但不等于没有内存问题
- 线程 dump 可定位死锁和阻塞
- 堆 dump 可分析内存泄漏

### 示例

```bash
java -Xms512m -Xmx512m -XX:+UseG1GC -jar app.jar
```

### 练习

- 查看 Java 进程
- 分析线程死锁
- 导出 heap dump
- 查看 GC 日志

### 阶段验收

- 能解释 JVM 运行流程
- 能使用基础诊断工具
- 能定位常见线上问题

### 推荐项目

- JVM 问题排查笔记
- 内存泄漏 demo

## 11. Maven / Gradle 与工程化阶段

> 📖 详细展开版见 [ph11-build-tooling/11-build-tooling.md](./ph11-build-tooling/11-build-tooling.md)

### 目标

能管理真实 Java 项目。

### 学习内容

- Maven、Gradle
- pom.xml、依赖管理、生命周期
- 多模块项目
- 打包 jar
- Checkstyle、SpotBugs、JaCoCo

### 必会概念

- 构建工具负责依赖、编译、测试和打包
- 依赖版本冲突需要显式管理
- 多模块要控制依赖方向
- 构建产物应可复现

### 示例

```bash
mvn clean test package
```

### 练习

- 创建 Maven 项目
- 引入第三方依赖
- 打可执行 jar
- 配置覆盖率

### 阶段验收

- 能独立创建工程
- 能解决依赖冲突
- 能打包运行服务

### 推荐项目

- Maven 多模块模板
- 可执行 CLI jar

## 12. 单元测试与工程质量阶段

> 📖 详细展开版见 [ph12-testing-quality/12-testing-quality.md](./ph12-testing-quality/12-testing-quality.md)

### 目标

写出可靠、可维护的 Java 工程代码。

### 学习内容

- JUnit 5、Mockito、AssertJ
- 集成测试、参数化测试
- Mock 外部依赖
- Testcontainers
- 覆盖率和静态检查

### 必会概念

- 测试应覆盖正常路径和错误路径
- Mock 用于隔离外部依赖
- 集成测试验证真实组件协作
- 覆盖率不是唯一质量指标

### 示例

```java
@Test
void shouldAddTwoNumbers() {
    assertEquals(3, calculator.add(1, 2));
}
```

### 练习

- 工具类测试
- Service 测试
- Mock 数据库依赖
- Testcontainers 测数据库

### 阶段验收

- 能写单元测试和集成测试
- 能使用 Mock
- 能生成覆盖率报告

### 推荐项目

- 带测试的用户服务
- Testcontainers 示例

## 13. 数据库阶段

> 📖 详细展开版见 [ph13-database/13-database.md](./ph13-database/13-database.md)

### 目标

掌握 Java 操作数据库和缓存。

### 学习内容

- SQL、JDBC、连接池
- MySQL、PostgreSQL、Redis
- 事务、索引、慢查询
- MyBatis、JPA/Hibernate
- Flyway、Liquibase

### 必会概念

- SQL 基础比 ORM 更重要
- 事务边界必须由业务定义
- 索引影响查询和写入成本
- Redis 适合缓存和高频状态

### 示例

```java
PreparedStatement stmt = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
stmt.setLong(1, 1L);
```

### 练习

- 用户表 CRUD
- 事务转账
- 连接池
- Redis 缓存
- 慢查询优化

### 阶段验收

- 能写参数化查询
- 能处理事务
- 能设计基础缓存策略

### 推荐项目

- 学生管理数据库版
- 设备状态存储服务

## 14. Web 后端开发阶段

### 目标

能用 Java 写后端 API 服务。

### 学习内容

- HTTP、Servlet、Tomcat
- REST API、JSON
- 参数校验、JWT、CORS
- 全局异常处理、日志、API 文档
- Spring MVC、Spring Boot

### 必会概念

- Controller 不应写复杂业务
- 接口响应结构要统一
- 认证和授权要分清
- 全局异常处理提升一致性

### 示例

```java
@RestController
@RequestMapping("/api")
class HelloController {
    @GetMapping("/ping")
    Map<String, String> ping() { return Map.of("message", "pong"); }
}
```

### 练习

- Todo API
- 登录注册
- 文件上传
- 设备管理 API

### 阶段验收

- 能设计 REST API
- 能处理认证和异常
- 能写基础后端服务

### 推荐项目

- 后台管理系统
- 车辆数据上报 API

## 15. Spring 全家桶阶段

### 目标

掌握企业级 Java 开发核心技术栈。

### 学习内容

- Spring IOC、DI、Bean 生命周期
- AOP、事务管理
- Spring MVC、拦截器
- Spring Boot 自动配置、starter、profile、actuator
- Spring Data、Spring Security

### 必会概念

- IOC 管对象创建和依赖
- AOP 适合横切逻辑
- 事务要注意传播和回滚规则
- Spring Boot 自动配置要能追踪来源

### 示例

```java
@Service
class UserService {
    private final UserRepository repo;
    UserService(UserRepository repo) { this.repo = repo; }
}
```

### 练习

- REST API 服务
- JWT 登录认证
- Redis 缓存
- 统一响应结构

### 阶段验收

- 能搭建 Spring Boot 项目
- 能解释 Bean 生命周期
- 能处理事务和安全

### 推荐项目

- 权限管理系统
- 设备管理平台

## 16. 微服务与分布式阶段

### 目标

能开发中大型后端系统。

### 学习内容

- 微服务架构
- Spring Cloud、Nacos、Gateway、OpenFeign
- Sentinel、Resilience4j
- 分布式事务、分布式锁
- 链路追踪、服务监控、幂等

### 必会概念

- 微服务增加治理复杂度
- 远程调用必须有超时和降级
- 重试需要幂等
- 链路追踪帮助定位跨服务问题

### 示例

```text
client → gateway → service-a → service-b → database
```

### 练习

- 用户服务
- 订单服务
- 设备管理服务
- 网关鉴权

### 阶段验收

- 能拆分服务边界
- 能处理服务调用失败
- 能接入注册发现和网关

### 推荐项目

- 微服务订单系统
- 车联网服务拆分 demo

## 17. 消息队列与搜索阶段

### 目标

掌握高并发系统常用中间件。

### 学习内容

- Kafka、RocketMQ、RabbitMQ
- 消息可靠性、重复消费、顺序性
- 死信队列、延迟消息
- Elasticsearch、倒排索引、日志检索

### 必会概念

- 消费者要设计幂等
- 分区影响顺序和吞吐
- 消息积压需要监控
- 搜索索引要考虑同步一致性

### 示例

```text
业务服务 → Kafka → 消费服务 → Elasticsearch
```

### 练习

- 异步订单处理
- 车辆数据消费
- 告警消息推送
- 日志搜索

### 阶段验收

- 能解释消息可靠性方案
- 能处理重复消费
- 能设计基础搜索索引

### 推荐项目

- Kafka 日志采集
- 设备事件搜索系统

## 18. 缓存与高并发阶段

### 目标

掌握高性能后端系统设计。

### 学习内容

- Redis、Caffeine
- 缓存穿透、击穿、雪崩
- 分布式锁、限流、幂等
- 秒杀系统、连接池优化
- 异步化、批处理、读写分离

### 必会概念

- 缓存要设置失效策略
- 热点 key 需要保护
- 分布式锁要有超时和唯一标识
- 高并发要从入口限流到存储保护

### 示例

```text
请求 → 本地缓存 → Redis → 数据库
```

### 练习

- 热点数据缓存
- 接口限流
- 库存扣减
- 批量写入优化

### 阶段验收

- 能设计缓存策略
- 能处理常见缓存问题
- 能解释限流和幂等

### 推荐项目

- 秒杀系统 demo
- 车辆状态实时缓存

## 19. DevOps 与部署阶段

### 目标

把 Java 服务部署到生产环境。

### 学习内容

- Linux、Shell、Docker、Docker Compose
- Kubernetes、Helm、Nginx
- CI/CD、Jenkins、GitHub Actions
- 日志采集、监控告警、灰度发布

### 必会概念

- 镜像构建应可复现
- 配置与代码分离
- 服务需要健康检查
- 发布必须可回滚

### 示例

```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/app.jar app.jar
CMD ["java", "-jar", "app.jar"]
```

### 练习

- Spring Boot 打包
- Docker 部署
- Compose 启动 Java + MySQL + Redis
- Kubernetes 部署

### 阶段验收

- 能构建并运行镜像
- 能配置健康检查
- 能查看日志和指标

### 推荐项目

- Spring Boot 部署模板
- Kubernetes Java 服务示例

## 20. 高级 Java 阶段

### 目标

理解 Java 底层和大型工程设计能力。

### 学习内容

- JVM 深入、JMM、AQS
- 线程池原理、HashMap、ConcurrentHashMap
- ClassLoader、Reflection、Proxy、SPI
- Netty、高性能网络编程
- 设计模式、DDD

### 必会概念

- JMM 解释可见性和有序性
- AQS 是很多并发工具基础
- 反射和代理支撑框架能力
- DDD 服务复杂业务建模

### 示例

```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(core, max, 60, TimeUnit.SECONDS, queue);
```

### 练习

- 手写简易 IOC
- 手写线程池
- RPC demo
- Netty TCP server

### 阶段验收

- 能解释并发底层机制
- 能阅读框架关键源码
- 能设计复杂业务模块

### 推荐项目

- 简易 IOC 容器
- Netty 网关 demo

## 21. 车联网 / 智能电动车方向 Java 阶段

### 目标

用 Java 构建车联网后端、设备管理、OTA 和数据服务。

### 学习内容

- 设备管理平台
- 车辆数据接入服务
- OTA 管理平台
- 告警规则引擎
- Kafka 数据消费
- Redis 实时状态缓存
- 轨迹查询、运维后台

### 必会概念

- Java 适合企业级后台和高并发数据服务
- 车辆数据链路要关注吞吐、延迟和可靠性
- 告警和 OTA 必须有审计和回滚设计

### 示例

```text
车辆 → 接入服务 → Kafka → 清洗/告警/存储 → 后台平台
```

### 练习

- 车辆数据上报 API
- 设备管理系统
- OTA 升级平台
- Kafka 遥测消费服务

### 阶段验收

- 能接入车辆数据并落库
- 能处理实时状态缓存
- 能设计告警规则和查询接口

### 推荐项目

- 车联网后台平台
- OTA 管理系统

## 附录：阶段性项目验收标准

### 目标

用项目验收 Java 学习成果。

### 学习内容

- 功能验收、测试验收、部署验收
- README、接口文档、数据库脚本
- 单元测试、集成测试、覆盖率
- 日志、监控、错误码

### 必会概念

- 能运行不等于可交付
- 接口、数据表和配置都要可说明
- 测试覆盖核心业务和错误路径
- 服务必须可观测

### 示例

```text
验收项：
- mvn test 通过
- 接口文档完整
- Docker 镜像可启动
- 日志和健康检查可用
```

### 练习

- 给项目补 README
- 给 Service 补测试
- 补 Dockerfile
- 补接口文档

### 阶段验收

- 能完成控制台项目（初级）
- 能完成 Spring Boot CRUD 服务（中级）
- 能完成可部署微服务或车联网模块（高级）

### 推荐项目

- Java 学习项目集
- Spring Boot 服务模板

## 推荐学习顺序

```text
Java 基础语法（含 var、Text Blocks）
→ 面向对象（含 record、sealed class）
→ 常用类 / 集合 / 泛型
→ 异常 / IO / Stream（含 Switch Expressions、Pattern Matching）
→ 多线程（含 Virtual Threads）/ JVM
→ Maven / Gradle / 测试
→ 数据库 / Redis
→ Spring Boot
→ Spring Cloud / 消息队列 / 缓存
→ Docker / Kubernetes
→ JVM 调优 / 高并发 / 车联网项目
```

## Java 和 C / C++ / Rust / Go / Python 的区别

| 方向 | Java |
| --- | --- |
| 内存管理 | GC 自动回收 |
| 类型系统 | 静态类型 |
| 运行方式 | 编译成字节码，在 JVM 上运行 |
| 主要方向 | 后端、企业系统、Android、大数据 |
| 工程能力 | 很强 |

## 项目路线

### 初级项目

- 计算器
- 学生管理系统
- 通讯录
- 文件统计工具

### 中级项目

- 图书管理系统
- 用户登录注册系统
- REST API 服务
- MySQL CRUD 系统
- Redis 缓存系统

### 高级项目

- Spring Boot 电商系统
- 权限管理系统
- 微服务订单系统
- API Gateway
- Kafka 日志采集系统

### 车联网 / 智能电动车项目

- 设备管理后台
- 车辆实时状态平台
- OTA 升级平台
- 车辆告警规则引擎
- 车辆轨迹查询服务

## 对你最推荐的 Java 路线

```text
Java 基础（含 var、Text Blocks）
→ 面向对象（含 record、sealed class）
→ 集合框架
→ 泛型
→ 异常处理
→ IO
→ Stream（含 Switch Expressions、Pattern Matching）
→ 多线程（含 Virtual Threads）
→ JVM
→ Maven
→ Spring Boot
→ MyBatis
→ MySQL / PostgreSQL
→ Redis
→ Kafka / RocketMQ
→ Spring Cloud
→ Docker / Kubernetes
→ 车辆数据平台
```

重点掌握：OOP、record、sealed class、Collection、HashMap、ArrayList、Generic、Exception、Stream、Switch Expressions、Pattern Matching、Optional、ThreadPool、Virtual Threads、ConcurrentHashMap、JVM、Maven、JUnit、Spring Boot、MyBatis、Redis、Kafka、Docker、Kubernetes。
