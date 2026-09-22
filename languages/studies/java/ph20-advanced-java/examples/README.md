# ph20 高级 Java 示例

> 八个示例对应主文档「3. 语法与参数」主线：JMM 可见性实证（ex01）→ AQS 自研锁（ex02）→ 手写线程池（ex03）→ CHM 并发行为（ex04）→ 反射/代理/SPI（ex05）→ 类加载器（ex06）→ GC 日志解读（ex07）→ Netty echo（ex08）。验证环境：**OpenJDK 17.0.18（Homebrew）**，纯 Java 示例零第三方依赖；ex08 需从 Maven Central 拉取 netty 4.1.137.Final 模块 jar。

## 验证状态（如实标注）

| 目录 | 主题 | 依赖 | 验证状态 |
|------|------|------|---------|
| ex01-jmm-visibility/ | volatile 可见性实证（故意错误对照 + 正确写法） | 无（纯 Java 17） | **已验证**（编译通过可运行；Phase 1 故意错误段本机未复现——如实说明见文件头） |
| ex02-aqs-mini-reentrant-lock/ | 继承 AbstractQueuedSynchronizer 手写可重入锁 | 无 | **已验证**：8 线程 × 2 万次重入互斥自增无丢失，16 线程竞争无死锁 |
| ex03-handwritten-threadpool/ | 手写线程池（core→queue→max→reject 四段路径） | 无 | **已验证**：8/8 PASS |
| ex04-chm-concurrency/ | ConcurrentHashMap.compute 原子性 + 裸 HashMap 对照 + 弱一致遍历 | 无 | **已验证**：7/7 PASS（对照实验实测丢失约 40 万次更新） |
| ex05-reflection-proxy-spi/ | 反射私有字段/注解 + JDK 动态代理 + ServiceLoader SPI | 无 | **已验证**：SPI 发现 2 个实现 |
| ex06-classloader-hierarchy/ | 委派链打印 + 打破双亲委派加载同名类 | 无 | **已验证**：5/5 PASS |
| ex07-gc-log-demo/ | GC 日志演示程序 + 采集样例与解读（README） | 无（需 -Xlog） | **已验证**：140 次 Pause Young / 0 次 Full |
| ex08-netty-echo/ | Netty TCP echo server/client（ServerBootstrap + pipeline） | netty 4.1.137.Final（手动拉 jar） | **已验证**：server/client 实测 ECHO OK |

> 两个「故意错误示例」注意：ex01 Phase 1 与 ex04 的裸 HashMap 段是**教学对照**，行为有不确定性（ex04 本机运行稳定丢更新、ex01 本机未复现），两文件头都注明了运行前提，切勿当作正确并发代码使用。

## 一条验证主链（全部纯 Java，从零开始）

```bash
# 编译全部到 /tmp（先进入各示例目录再 javac；或按每个文件头的命令）
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
OUT=/tmp/tl20-cls && mkdir -p $OUT

# ex01：JMM 可见性（volatile 修复段确定性输出）
cd ex01-jmm-visibility
$JAVAC -encoding UTF-8 -d $OUT JMMVisibilityDemo.java && $JAVA -Xint -cp $OUT JMMVisibilityDemo

# ex02：AQS 自研锁
cd ../ex02-aqs-mini-reentrant-lock
$JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT MiniReentrantLockDemo

# ex03：手写线程池
cd ../ex03-handwritten-threadpool
$JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ThreadPoolDemo

# ex04：CHM 并发（对照段会打印丢失量）
cd ../ex04-chm-concurrency
$JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ChmConcurrencyDemo

# ex05：反射/代理/SPI（classpath 需带 spi-resources）
cd ../ex05-reflection-proxy-spi
$JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp ${OUT}:spi-resources Ex05ReflectionProxySpiDemo

# ex06：类加载器（先编译两个版本的 Greeting 到不同目录）
cd ../ex06-classloader-hierarchy
mkdir -p /tmp/tl20-vA /tmp/tl20-vB
$JAVAC -encoding UTF-8 -d /tmp/tl20-vA versionA/Greeting.java
$JAVAC -encoding UTF-8 -d /tmp/tl20-vB versionB/Greeting.java
$JAVAC -encoding UTF-8 -d $OUT Ex06ClassLoaderDemo.java
$JAVA -cp $OUT Ex06ClassLoaderDemo /tmp/tl20-vA /tmp/tl20-vB

# ex07：GC 日志（日志写文件，程序输出分配节奏）
cd ../ex07-gc-log-demo
$JAVAC -encoding UTF-8 -d $OUT GcLogDemo.java
$JAVA -Xms48m -Xmx48m "-Xlog:gc:file=/tmp/gc-demo.log" -cp $OUT GcLogDemo
grep -c 'Pause Young' /tmp/gc-demo.log     # 期望 >100（本机 140）
```

## 需要外部依赖的验证（ex08，本机已手动完成一次）

```bash
# netty jar 拉取与编译运行见 ex08-netty-echo/README.md（本机已实测 ECHO OK）
# 有 mvn 的环境：cd ex08-netty-echo && mvn -q compile（依赖 netty-all:4.1.137.Final）
```

## 与 exercises/project 的关系

- 练习 1（手写 IOC）比 ex05 更进一步：ex05 演示反射能读写，练习要求用反射真正建一个容器（参考实现 `sol-01`）
- 练习 2（手写线程池）是 ex03 的加配版：要求 `submit` 返回 Future（参考实现 `sol-02`）
- 练习 3（RPC demo）组合 ex05 的动态代理 + socket：把代理调用发到远端执行（参考实现 `sol-03`）
- 练习 4（Netty TCP server）是 ex08 的服务化扩展（参考实现 `sol-04`）

## 清理

所有编译产物输出到 `/tmp`（`/tmp/tl20-cls`、`/tmp/tl20-vA`、`/tmp/tl20-vB`、`/tmp/gc-demo.log` 等），仓库目录不落 `.class`。清理：`rm -rf /tmp/tl20-cls /tmp/tl20-vA /tmp/tl20-vB /tmp/gc-*.log`。
