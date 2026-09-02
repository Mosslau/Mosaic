# Java Maven / Gradle 与工程化阶段

> 面向企业级后端、微服务方向，本阶段掌握 Maven / Gradle 构建工具并具备真实项目工程化能力——从 javac/jar 手工构建讲起，管得了依赖与生命周期，拿得起 pom.xml、多模块工程与可执行 jar。

## 1. 概述

构建工具阶段的目标是：**能管理真实 Java 项目**——先用 javac/jar/jlink 手工构建理解「构建」这件事的本质（编译、classpath、打包、运行时裁剪），再用 Maven（或 Gradle）把依赖、编译、测试、打包串成一条自动化的流水线，而不是像 ph10 那样用 javac 手工编译零散文件。`javac Hello.java` 只适合单文件与临时 classpath，真实项目动辄几十个第三方库（JSON、日志、数据库驱动、测试框架），它们的 jar 从哪来、版本谁管、冲突怎么办、如何打包交付，就是本阶段要解决的问题：**构建工具（Build Tool）负责依赖、编译、测试和打包**，多模块工程要**控制依赖方向**，依赖版本冲突要**显式管理**，构建产物要**可复现**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 手动构建 | javac 多文件编译与 classpath、jar 打包与清单（Main-Class / Class-Path）、jlink 精简运行时 |
| 构建工具 | Maven 与 Gradle 选型、pom.xml / build.gradle、普通 jar 与可执行 fat jar（shade） |
| 坐标与仓库 | groupId:artifactId:version、本地仓库 / Maven Central / 私服 |
| 依赖管理 | 传递依赖、scope、冲突仲裁、dependencyManagement |
| 生命周期 | validate → compile → test → package → verify → install → deploy |
| 多模块工程 | 聚合与继承、依赖方向控制 |
| 质量工具 | Checkstyle、SpotBugs、JaCoCo 覆盖率 |

这个阶段只涉及构建工程化：javac/jar/jlink 手工构建、Maven / Gradle 构建工具、依赖管理与多模块工程、打包与发布，**不涉及单元测试的编写与测试设计**（见 [ph12 单元测试与工程质量阶段](../ph12-testing-quality/12-testing-quality.md)）、**不涉及 Web 框架与 Spring 生态的工程化**（ph15 Spring 全家桶阶段，roadmap 第 15 节）、**不涉及 CI/CD 流水线与制品治理**（ph19 DevOps 与部署阶段，roadmap 第 19 节，目录待建）。本阶段承接 ph10 JVM 阶段——javac 只能编译零散源码、classpath 全靠手工拼接，真实项目需要构建工具统一管理依赖、编译、测试与打包。

## 2. 来源与演变

Java 诞生后的头十年，构建靠 `javac` 手工编译加 **Ant**（Apache Ant，2000 年发布）：用 XML 编写构建脚本（compile/jar 等 target），灵活但每个项目一套脚本、没有统一的依赖管理与生命周期，属于「脚本式构建」。真正的转折是 **Maven**：Maven 1.0（2004 年）引入**项目对象模型（Project Object Model, POM）**与**坐标（Coordinates）**，用 `groupId:artifactId:version` 三要素唯一定位一个构件（artifact），并依托 2002 年成立的 **Maven Central**（中央仓库）实现「声明依赖即自动下载」；Maven 2.0（2005 年）把**生命周期（Lifecycle）**与**传递依赖（Transitive Dependency）**定型——只声明直接依赖，它依赖的库会层层带下来，从此「约定优于配置（Convention over Configuration）」成为 Java 工程的事实标准。

**Gradle** 走的是另一条路：2007 年诞生、2012 年发布 1.0，用基于 **Groovy** 的领域特定语言（DSL）描述构建，构建模型是**任务依赖图（Task Graph）**而非固定阶段，天然支持**增量构建（Incremental Build）**；2018 年 Gradle 5.0 引入 **Kotlin DSL**，配置可静态类型检查。Gradle 构建更快、更灵活，是 Android 官方构建工具，但 Maven 生态更成熟、上手更平缓，企业存量工程仍以 Maven 为主——本阶段以 Maven 为主线（示例全部用 Maven 实测），Gradle 作为对比理解。

质量工具与构建工具并行演进：**Checkstyle**（2001 年）做代码风格静态检查；**FindBugs**（2006 年）做缺陷静态分析，2016 年社区 fork 为 **SpotBugs** 继续维护；**JaCoCo**（2009 年首发 0.1.0，官方版权 © 2009, 2026）做测试覆盖率统计，`mvn test` 后生成 HTML 报告，成为覆盖率的事实标准——它从 EclEmma 引擎独立而来，EclEmma 2.0 反过来基于 JaCoCo 引擎。三者与 Maven 的关系，见 3.8。

| 版本/年份 | 演进 |
|-----------|------|
| Ant（2000） | XML 脚本式构建，灵活但无依赖管理、无生命周期 |
| Maven 1.0（2004） | 引入 POM 与坐标；依托 Maven Central 中央仓库 |
| Maven 2.0（2005） | 生命周期与传递依赖定型，约定优于配置成为标准 |
| Gradle（2007 诞生 / 2012 1.0） | Groovy DSL 描述任务依赖图，增量构建、构建快 |
| Gradle 5.0（2018） | 引入 Kotlin DSL，配置可类型检查 |
| 质量工具 | Checkstyle（2001）、FindBugs（2006）→ SpotBugs（2016）、EclEmma（2005）→ JaCoCo（2009） |

本文示例以 **OpenJDK 17（LTS）+ Maven 3.9.12** 为基线（验证工具链：`javac -version` → 17.0.18、`mvn -version` → 3.9.12；本环境**未安装 Gradle**，Gradle 相关内容只做概念讲解、命令未实跑），pom 中统一用 `<maven.compiler.release>17</maven.compiler.release>`。构建语义（坐标、生命周期、scope、冲突仲裁）自 Maven 2 定型以来高度稳定，17 上观察到的行为可直接迁移到 21/25；本阶段全部 Maven 示例、练习与项目已在本工具链上实测通过（`mvn -o` 离线模式，依赖/插件取自本地仓库缓存，见第 6 章与各代码层 README），依赖与插件版本在 pom 中全部写死——这是本阶段最稳定的知识，值得深挖。

## 3. 语法与参数

### 3.1 javac 手工构建：多文件、classpath 与 -d

真实项目的构建从 javac 开始，Maven 只是把这条链自动化。多文件工程的三个核心参数：

| 参数 | 作用 | 示例 |
|------|------|------|
| `-d <目录>` | 指定 class 输出目录，自动按包建子目录 | `javac -d build src/greeting/Greeter.java` |
| `-cp <classpath>`（等价 `-classpath`） | 编译期依赖类路径，多个路径用 `:`（Windows `;`）分隔 | `javac -cp build-lib -d build-app app/Main.java` |
| `-sourcepath <目录>` | 指定源码根目录，javac 需要时自动找源文件编译 | `javac -sourcepath src -d build app/Main.java` |

```java
// examples/ex01-manual-javac.java —— javac 手动构建：多文件、-d、-cp（完整版见 examples/）
package manual;

class ManualJavacDemo {
    public static void main(String[] args) {
        String name = args.length > 0 ? args[0] : "Java";
        System.out.println(Helper.greet(name));   // Helper 在同包另一个源文件里
    }
}
```

```bash
# 1. 一次编译两个源文件到 build/（-d 自动按包建目录）
javac -d build ex01-manual-javac.java ex01-helper.java
# 2. 运行（-cp 指向输出目录, 类名带包名）
java -cp build manual.ManualJavacDemo "mosslau"
# 3. classpath 分离：helper 单独编译到 build-lib, 主程序用 -cp 引用编译好的类
javac -d build-lib ex01-helper.java
javac -d build-app -cp build-lib ex01-manual-javac.java
java -cp build-lib:build-app manual.ManualJavacDemo
```

- **`-d` 让 javac 自动按包建目录**：不指定时 class 直接落在当前目录，包一多就全糊在一起；指定后 `build/manual/` 与包名结构一致，`java -cp build manual.Xxx` 才能按包名找到类
- **编译期 classpath 与运行期 classpath 是两条链**：步骤 3 里 javac 从 `-cp build-lib` 解析 `Helper`（编译期链），java 从 `-cp build-lib:build-app` 加载类（运行期链）——手动拼这两条链，正是 Maven 的 `compile` 阶段在自动化的事
- **多文件手编的痛苦**：文件一多，`javac` 命令越来越长、漏一个文件就编不过、换机器就忘命令——这是 Maven 出现的直接动因

> class 文件内部结构（字节码、常量池、魔数 0xCAFEBABE）属于 ph10 JVM 阶段的内容，这里只把 javac 当作「把源码变成 class 的编译器」用。

### 3.2 jar 打包与清单：Main-Class 与 java -jar

`jar` 把编译产物打包成一个文件分发给别人运行。jar 本质是 zip + `META-INF/MANIFEST.MF` 清单，清单里的 **`Main-Class`** 属性决定 `java -jar` 从哪个类启动：

| 命令 | 作用 |
|------|------|
| `jar cf app.jar -C build .` | 把 build 目录内容打成 jar（c=create, f=file, -C 先进入目录再打包） |
| `jar cfe app.jar MainClass -C build .` | 打 jar 并写入入口类（e=entrypoint，等价清单写 `Main-Class`） |
| `jar ufe app.jar MainClass -C build .` | 事后更新：给已有 jar 补/改 Main-Class（u=update） |
| `unzip -p app.jar META-INF/MANIFEST.MF` | 查看清单内容 |

```bash
# 完整流程（实测命令与输出, 见 examples/ex02-jar-manifest.java）
javac -d build ex02-jar-manifest.java
jar cf app-plain.jar -C build .                  # 无 Main-Class 的 jar
java -jar app-plain.jar                          # 实测报错: app-plain.jar中没有主清单属性
jar cfe app-main.jar JarManifestDemo -C build .  # 带 Main-Class
java -jar app-main.jar                           # 实测输出: hello from jar
jar ufe app-plain.jar JarManifestDemo -C build . # 事后补主类
java -jar app-plain.jar                          # 同样可运行
```

- **`java -jar` 只认清单里的 Main-Class**：没有它，报「中没有主清单属性」（英文环境为 `no main manifest attribute`）——这是初学者最常撞的报错，理解 `e` 选项在写什么就不会怕
- **清单还有 `Class-Path` 属性**：写 `Class-Path: lib/gson-2.10.1.jar`（相对 jar 的路径），`java -jar` 会按它加载外部依赖——这是「薄 jar + 外部 classpath」打包方案的机制，与 3.5 的 fat jar 互为两条路
- **`jar cf` 与 `jar cfe` 的差别**：`e` 选项写入口点，等价于打包后手工编辑清单加一行 `Main-Class`（所以 `ufe` 能事后补）

### 3.3 jlink：模块化裁剪运行时

`jlink` 把 JDK 按**模块**裁出一个只含所需部分的最小运行时，随应用一起分发——这是 JDK 自带的分发方案（对应 3.6 的「打包」环节在运行时层面的延伸）：

```bash
# 完整流程（实测, 见 examples/ex03-jlink-runtime.java）
javac -d build ex03-jlink-runtime.java
jdeps --print-module-deps build/JlinkRuntimeDemo.class   # 实测输出: java.base,java.logging
jlink --add-modules java.base,java.logging --output runtime-min
runtime-min/bin/java -cp build JlinkRuntimeDemo          # 实测输出: hello from jlink runtime
du -sh runtime-min        # 实测 41M
du -sh <JDK 根目录>        # 实测 305M（完整 JDK）——裁掉约 87%
```

- **`jdeps` 回答「程序用到哪些模块」**：`--print-module-deps` 输出模块闭包，交给 `jlink --add-modules` 用
- **jlink 按模块裁剪、不是按类裁剪**：漏一个模块，运行期直接 `NoClassDefFoundError`（实测：只加 `java.base` 时 `java.util.logging.Logger` 找不到）——所以流程固定是「jdeps 分析 → jlink 裁剪 → 精简运行时自测」
- **典型用途**：容器镜像（只带 41M 运行时而不是 305M JDK）、离线环境分发

> 模块系统（JPMS）的完整语义（module-info 的 exports/opens、ServiceLoader 模块化）属于 ph20 高级 Java 阶段（与 ClassLoader、SPI 同族），这里只把 jlink 当作「把 JDK 裁小」的打包工具用。

### 3.4 Maven 坐标与 pom.xml

Maven 工程的核心是根目录下的 `pom.xml`（Project Object Model），它声明了工程的**身份**、**依赖**与**构建方式**。最关键的几个元素：

| 元素 | 作用 | 示例 |
|------|------|------|
| `groupId` | 组织/公司唯一标识（反域名） | `com.example` |
| `artifactId` | 工程（模块）名称 | `hello-maven` |
| `version` | 版本号，SNAPSHOT 表示开发中快照 | `1.0-SNAPSHOT` |
| `packaging` | 打包类型，默认 jar | `jar` / `war` / `pom`（聚合父工程） |
| `properties` | 定义可复用属性（如 Java 版本） | `maven.compiler.release=17` |
| `dependencies` | 直接依赖列表 | gson、junit 等 |
| `dependencyManagement` | 集中声明版本，供子模块继承 | 见 4.4 |
| `build` | 构建配置（插件、finalName 等） | maven-jar-plugin、maven-shade-plugin |
| `modules` / `parent` | 多模块聚合 / 继承 | `<module>common</module>` |

```xml
<!-- 最小 pom：三要素 + Java 版本属性（完整版见 examples/ex04-maven-minimal/pom.xml） -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>hello-maven</artifactId>
  <version>1.0-SNAPSHOT</version>
  <properties>
    <maven.compiler.release>17</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
</project>
```

- **标准目录结构是约定，不是配置**：主代码在 `src/main/java`，资源在 `src/main/resources`，测试代码在 `src/test/java`——Maven 默认就从这些位置找，目录错了编译出来是空的；`modelVersion` 固定写 4.0.0（pom 的 schema 版本，照抄即可）
- **`maven.compiler.release` 优于 source/target**：`release` 同时约束 `-source` 与 `-target` 且禁止用到更新版本的 API——JDK 17 基线下直接写 17（旧工程常见的 `source/target=1.8` 是历史写法）
- **SNAPSHOT 与正式版的区别**：`1.0-SNAPSHOT` 表示开发中快照，允许重复构建覆盖；正式版本 `1.0.0` 一经发布不允许再改，这是可复现构建的第一道约束（4.6）

### 3.5 依赖管理：scope 与传递依赖

依赖通过坐标声明，**scope（依赖范围）**决定它出现在哪条 classpath 上、是否打进最终产物：

| scope | 编译 | 测试 | 运行 | 打进产物 | 典型场景 |
|-------|------|------|------|---------|---------|
| `compile`（默认） | ✔ | ✔ | ✔ | ✔ | 业务库（gson、logback） |
| `provided` | ✔ | ✔ | ✔ | ✘ | Servlet API（容器提供） |
| `runtime` | ✘ | ✔ | ✔ | ✔ | JDBC 驱动（编译期用接口） |
| `test` | ✘ | ✔ | ✘ | ✘ | JUnit、Mockito |

```xml
<dependencies>
  <dependency>
    <groupId>com.google.code.gson</groupId>
    <artifactId>gson</artifactId>
    <version>2.10.1</version>
  </dependency>
  <dependency>
    <groupId>junit</groupId>
    <artifactId>junit</artifactId>
    <version>4.13.2</version>
    <scope>test</scope>
  </dependency>
</dependencies>
```

- **传递依赖（Transitive Dependency）**：依赖 gson，gson 自己依赖的库会自动进入 classpath——这正是「只声明直接依赖」的前提；`mvn dependency:tree` 可查看整棵依赖树（实测 gson 2.10.1 无传递依赖，依赖树只有一行）
- **`optional`**：声明「我用得上但使用方未必需要」，如日志门面 slf4j 的各个实现，不让传递依赖污染使用方
- **`<exclusions>`**：排除某个传递依赖（如排除冲突的旧版 commons-xxx），是解决依赖冲突的最后一招（4.3）

### 3.6 Maven 生命周期与 mvn 常用命令

**生命周期（Lifecycle）**是 Maven 的核心抽象：一组**有序阶段（phase）**，执行任一阶段，前面的阶段会依次先执行（`mvn package` 会自动先 compile、test）。默认生命周期的主要阶段与默认绑定：

| 阶段 | 默认绑定插件 | 说明 |
|------|-------------|------|
| `validate` | - | 校验工程信息 |
| `compile` | maven-compiler-plugin | 编译 `src/main/java` → `target/classes` |
| `test` | maven-surefire-plugin | 运行 `src/test/java` 测试 |
| `package` | maven-jar-plugin | 打 jar / war 到 `target/` |
| `verify` | - | 集成校验（如 JaCoCo check 门槛） |
| `install` | maven-install-plugin | 安装到**本地仓库**（供本机其他工程引用） |
| `deploy` | maven-deploy-plugin | 部署到**远程仓库**（私服/中央） |

`clean` 是独立生命周期（清空 `target/`），所以发布前要组合成 roadmap 示例的 `mvn clean test package`——先清干净再完整构建。常用命令：

| 命令 | 作用 |
|------|------|
| `mvn clean test package` | 清空 → 编译 → 测试 → 打包（发布前典型组合） |
| `mvn install` / `mvn deploy` | 装进本地仓库 / 部署到远程仓库 |
| `mvn dependency:tree` | 打印依赖树，查冲突（4.3） |
| `mvn help:effective-pom` | 查看继承合并后的**完整** pom |
| `mvn -pl app -am package` | 只构建 app 及其依赖的兄弟模块（4.4） |

- **命令的本质是「插件:目标（plugin:goal）」**：`mvn dependency:tree` 中 dependency 是插件、tree 是目标；`compile`/`package` 这类阶段名是关键字，会触发一串绑定的目标
- **本地仓库（Local Repository）**：默认 `~/.m2/repository`，下载的 jar 按坐标缓存于此，`install` 就是把你的工程也放进去——离线也能构建；本环境实测时因沙箱禁止写 `~/.m2`，`install` 用 `-Dmaven.repo.local=<可写目录>`（沙箱特例：指向克隆的本地仓库，如 `/tmp/m2clone`）验证通过，正常环境直接 `mvn install` 即可
- **离线构建**：`mvn -o` 强制只用本地仓库缓存、不发网络请求——本阶段全部 Maven 实测即此模式；CI 里也常用它验证「离线可构建」

### 3.7 Gradle 视角：任务、DSL 与 wrapper

Gradle 的配置不是 XML，而是**构建脚本**：Groovy 写 `build.gradle`，Kotlin 写 `build.gradle.kts`，可以在里面写逻辑。同一件事两种工具的对比：

| 维度 | Maven | Gradle |
|------|-------|--------|
| 描述文件 | `pom.xml`（XML） | `build.gradle`（Groovy）/ `build.gradle.kts`（Kotlin DSL） |
| 构建模型 | 固定生命周期阶段 + 绑定插件 | 任务（Task）依赖图，自定义灵活 |
| 配置语言 | 声明式 XML | 编程式 DSL，可写条件与循环 |
| 增量构建 | 弱（靠插件各自判断） | 输入/输出快照，**增量强** |
| 常驻进程 | 每次启动新 JVM | **Gradle Daemon** 守护进程常驻，构建快 |
| 依赖体系 | 坐标 + scope | 同套坐标体系 + configuration |
| 多模块 | 聚合（modules）+ 继承（parent） | 多项目（include）+ 子项目配置 |

```groovy
// build.gradle（Groovy DSL）—— 与 3.4 最小 pom 同义（完整对照见 examples/ex06-gradle-script.md）
plugins { id 'java' }
group = 'com.example'
version = '1.0-SNAPSHOT'
repositories { mavenCentral() }
dependencies {
    implementation 'com.google.code.gson:gson:2.10.1'
}
jar { manifest { attributes 'Main-Class': 'com.example.HelloMaven' } }
```

- **Gradle 的 `implementation` ≈ Maven 的 compile**，语义更细（不把依赖暴露给使用方，进一步压缩传递面）；Kotlin DSL 写法是 `implementation("com.google.code.gson:gson:2.10.1")`
- **任务（Task）是 Gradle 的最小执行单元**：`build`、`test`、`jar` 都是任务，任务间声明依赖构成**任务依赖图**——对比 Maven 的固定阶段序列，这是两种构建模型的分水岭（4.5）
- **Gradle Wrapper（`gradlew`）**：把 Gradle 版本写进项目，团队任何人 `./gradlew build` 都得到同版本——这正是「构建产物可复现」的抓手，Maven 侧对应 `mvnw`（Maven Wrapper）
- 本阶段示例全部用 Maven 实测；学完 Maven 再读 Gradle 脚本，两三天即可迁移

> **本环境未安装 Gradle**（`gradle -version` → command not found），上例与 examples/ex06-gradle-script.md 中的 Gradle 命令均未实跑，只做概念讲解。

### 3.8 质量工具：Checkstyle / SpotBugs / JaCoCo

工程化不止「能编译能打包」，还包括**质量门禁**，三个工具分工不同：

| 工具 | 检查什么 | 典型配置 | 失败表现 |
|------|---------|---------|---------|
| Checkstyle | 代码风格（命名、缩进、行宽、Javadoc） | `google_checks.xml` / 团队自定规则 | `mvn checkstyle:check` 报违规 |
| SpotBugs | 缺陷模式（空指针、资源未关、并发误用） | spotbugs-maven-plugin + `spotbugs:check` | 报告列出 bug 类别与位置 |
| JaCoCo | 测试覆盖率（指令/分支/行/方法/类） | prepare-agent + report（完整实测配置见 exercises/sol-04） | 可配 check 阈值，不足则构建失败 |

- **三个工具都挂在生命周期上**：JaCoCo 的 prepare-agent 挂在 `initialize`（注入 javaagent 记录执行数据），report 挂在 `test` 后生成报告——这就是「插件绑定阶段」的实际应用
- **覆盖率不是唯一质量指标**：JaCoCo 告诉你「测没测到」，Checkstyle 管「像不像规范代码」，SpotBugs 管「有没有明显缺陷」，三者互补，ph12 再深入测试编写本身
- **JaCoCo 实测数字**（只测 add 不测 divide 时）：指令覆盖率 63%（7/11）、行 2/3、方法 2/3——覆盖率 = 测到的 ÷ 全部，测试没覆盖的分支就是风险敞口

### 3.9 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| 版本写 `RELEASE`/`LATEST` 或不写版本 | 构建不可复现，昨天能编今天报错 | 固定具体版本号，升级集中到 dependencyManagement |
| 依赖冲突没人管 | `NoSuchMethodError`、类版本错乱 | `mvn dependency:tree` 定位 + 显式仲裁（4.3） |
| 多模块循环依赖 | reactor 报 cycle 错误 | 依赖方向单向化，公共代码下沉到 common |
| scope 用错 | 测试能过、运行时 `ClassNotFoundException` | provided/test 不打进产物，确认 3.5 表格 |
| 单独构建子模块失败 | 找不到兄弟模块的 jar | 先 `mvn install` 父工程，或 `mvn -pl app -am` |
| 发布前不 clean | 改了代码却拿到旧产物 | `mvn clean test package`（roadmap 示例命令） |
| 薄 jar 直接 `java -jar` | 「中没有主清单属性」或运行期 `NoClassDefFoundError` | 打 fat jar（3.6 的 shade）或薄 jar + 清单 Class-Path（3.2） |
| 行数用 `split("\n")` 统计 | 结尾换行多算一行 | 用 `String.lines().count()`（与 `wc -l` 语义一致） |

## 4. 底层原理

### 4.1 jar、classpath 与 java -jar 的底层机制

jar 文件是 zip 容器 + 一条 `META-INF/MANIFEST.MF` 清单。`java -jar app.jar` 的启动路径是：JVM 打开 jar → 读清单 → 取 `Main-Class` 属性 → 加载该类并调用 `main`。`Class-Path` 清单属性里的路径**相对 jar 自身位置解析**（不是相对当前工作目录），所以薄 jar 部署时依赖目录必须与清单里的相对路径一致。

```text
javac 源码 ──▶ .class（含包名） ──jar──▶ app.jar（zip + META-INF/MANIFEST.MF）
                                          │  Main-Class: com.example.AppMain   ← java -jar 的入口
                                          │  Class-Path: lib/gson.jar          ← 相对 jar 解析外部依赖
                                          ▼
                                   java -jar app.jar
```

**fat jar（Uber Jar）**把依赖类的字节码**合并**进同一个 jar，Main-Class 依然在清单里，运行时无需任何外部 classpath——代价是**撞类风险**：两个依赖库带同包同类名时，合并时取舍方向依顺序而定（社区实现多倾向先出现者胜出，具体以 maven-shade-plugin 实测为准），最终 jar 里可能只剩某一方的类，运行期行为错乱（shade 构建时打印的 `define N overlapping resource` 警告就是预兆）。jlink 则是另一条路：不动应用 jar，而是把 JDK 镜像本身按模块裁剪，应用在裁剪后的 `bin/java` 上跑。

### 4.2 生命周期：阶段顺序与插件绑定

`mvn package` 为什么能自动编译、测试、打包？因为**阶段是顺序执行的**：调用 `package` 阶段，Maven 按 `validate → initialize → ... → compile → ... → test → ... → package` 依次执行，每个阶段上绑定的插件目标（Mojo，Maven 插件的最小执行单元）依次运行。`mvn test` 不会跳过 compile，因为 test 依赖 compile 先完成——阶段间的先后关系由生命周期定义，而非由你手动编排。

```text
validate → initialize → generate-sources → process-sources → generate-resources
→ process-resources → compile → process-classes → generate-test-sources
→ process-test-resources → test-compile → test → prepare-package → package
→ pre-integration-test → integration-test → verify → install → deploy
```

- **插件是生命周期的执行者**：compile 阶段绑定 maven-compiler-plugin，test 阶段绑定 maven-surefire-plugin，package 阶段绑定 maven-jar-plugin——阶段本身不干活，干活的都是插件；`<executions>` 把插件目标挂到指定阶段（3.8 的 JaCoCo 就是例子），`prepare-agent` 默认绑定 `initialize`，report 通过 `<phase>test</phase>` 显式挂到 test 之后
- **理解这个机制的意义**：排查「为什么我的插件没跑/跑错顺序」时，先查 execution 的 phase 与 goal 绑定，再查插件版本——90% 的构建问题出在这两处

### 4.3 依赖解析与冲突仲裁

依赖解析发生在构建初期：Maven 读 pom 的依赖声明，沿**传递依赖**展开成完整依赖树，再从仓库下载。**冲突仲裁（Dependency Mediation）**解决「同一个库被不同路径带出不同版本」的问题，规则是：

- **最近优先（Nearest Definition Wins）**：依赖树中路径最短的那个版本胜出
- **声明优先**：路径深度相同（同属一级直接依赖）时，pom 中先声明的胜出
- **`dependencyManagement` 一票否决**：父工程 `<dependencyManagement>` 里显式声明的版本，压过一切传递版本——这是**显式管理版本冲突**的标准手段

```text
app
├─ com.google.code.gson:gson:2.10.1        ← 直接依赖，路径深度 1
└─ com.example:common:1.0-SNAPSHOT
   └─ com.google.code.gson:gson:2.8.9      ← 传递依赖，路径深度 2，被最近优先淘汰
```

- **冲突的典型症状**：编译期都正常（每个库按自己的版本编译），运行期 `NoSuchMethodError`/`NoClassDefFoundError`——两个版本的类同时或错误地出现在 classpath
- **排查四步**：`mvn dependency:tree` 看树 → 找出同一坐标的多个版本 → 在 `dependencyManagement` 显式钉死目标版本 → 必要时 `exclusions` 排除多余分支
- **Gradle 默认乐观升级取最高版本**：版本冲突时取最高版本（如 1.1 vs 1.3 → 1.3），**不直接失败**；要让冲突失败，须显式 `resolutionStrategy.failOnVersionConflict()`——这是把「显式管理」从最佳实践升级为强制约束的开关

### 4.4 多模块：聚合、继承与依赖方向

多模块工程（multi-module project）把一个大工程拆成多个可独立构建的模块。父 pom 用 `packaging=pom` 同时做两件事：**聚合（Aggregation）**——`<modules>` 声明子模块，一次 `mvn package` 按依赖顺序构建全部模块（reactor 构建）；**继承（Inheritance）**——子模块 `<parent>` 指向父 pom，继承属性、依赖管理与插件配置。

- **依赖方向必须单向**：模块依赖只能指向「下层」，公共代码放 `common`，业务模块依赖 common，严禁 common 反向依赖业务模块——一旦成环，reactor 直接报 `cycle` 错误，因为构建顺序无法确定
- **版本集中管理**：父 pom 的 `dependencyManagement` 声明所有第三方版本，子模块引用时**不写版本**（`<version>` 可省），升版本只改一处；兄弟模块依赖用 `${project.version}` 保证与父工程永远一致
- **reactor 构建顺序**：Maven 先解析模块依赖图，被依赖的模块先构建；所以 `mvn package` 在根目录跑，common 一定先于 app 产出 jar
- **子模块单独构建的前提**：兄弟模块的 jar 必须先在本地仓库（`mvn install`）——reactor 只在根目录整批构建时生效；CI 里用 `mvn -pl app -am package`（-am 同时构建依赖模块），本阶段项目的完整模板见 [`project/`](./project/)

### 4.5 Gradle 增量构建、daemon 与构建缓存

Gradle 快的底层原因有三个。**增量构建（Incremental Build）**：每个任务声明输入（源码、配置）与输出（产物），Gradle 对输入做**内容快照**，输入没变的任务直接标记 up-to-date 跳过——改一个文件只重编受影响的部分；Maven 的增量依赖插件各自判断，粒度粗得多。**守护进程（Daemon）**：构建逻辑常驻内存（Gradle Daemon），后续构建复用已加载的类与依赖元数据，省掉每次 JVM 启动开销。**构建缓存（Build Cache）**：任务输出按输入哈希缓存，同一输入在其他机器/分支上构建过，直接复用缓存产物，CI 与本地共享缓存时收益最明显。

- **增量构建的前提是「输入声明完整」**：漏声明输入（如读了外部文件但没列入 inputs）会导致缓存错用——这是 Gradle 缓存玄学问题的根源；Gradle 7+ 的**配置缓存（Configuration Cache）**进一步缓存构建脚本的配置阶段结果
- **对 Maven 用户的启示**：Maven 的慢是设计使然（无守护进程、弱增量），所以大工程常配 maven daemon（mvnd）或直接转 Gradle——工具选型是工程决策，不是信仰问题

### 4.6 可复现构建

**可复现构建（Reproducible Build）**指：同一份源码 + 同一份构建描述，在任何时间、任何机器上产出**逐字节一致**的产物。它保证「CI 上能出、本地就一定能出」，是交付可信度的基础。要做到：

- **固定所有版本**：依赖版本、插件版本都写死，禁止 RELEASE/LATEST；`dependencyManagement` 同时锁住传递依赖（或 Gradle 的 dependency locking 生成锁文件）
- **固定构建工具版本**：用 Wrapper（`mvnw` / `gradlew`）把 Maven/Gradle 版本写进仓库，团队与 CI 用同版本构建；`project.build.outputTimestamp` 可固定 jar 内的时间戳——插件级支持、无 Maven 版本前置（Maven 4.0.0-beta-5 起默认开启）
- **隔离环境因素，一次构建出一份产物**：构建路径、时区、locale 不影响产物；CI 上 `mvn clean test package` 全量构建，禁止「上次的 target 接着用」，发布产物的哈希应可预期、可校验

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 新项目从零搭建 | 标准目录结构 + pom.xml 骨架（3.4、examples/ex04） |
| 引入第三方库（JSON/日志/数据库驱动） | 坐标、scope、传递依赖（3.5、examples/ex05、exercises 练习 2） |
| 提交代码前统一构建 | `mvn clean test package` 生命周期（3.6） |
| 交付可运行的服务/CLI | shade 打可执行 fat jar（examples/ex05、exercises 练习 3） |
| 拆分多模块工程（common/app） | 聚合、继承与依赖方向（4.4、project/） |
| 依赖冲突排查 | `mvn dependency:tree` + dependencyManagement（4.3） |
| 质量门禁与覆盖率 | Checkstyle / SpotBugs / JaCoCo（3.8、exercises 练习 4） |
| 容器/离线环境分发 | jdeps + jlink 裁剪运行时（3.3、examples/ex03） |

**不适合**此阶段的事项：

- **单元测试的编写与设计**（JUnit 断言、Mockito、参数化测试、Testcontainers）——[ph12 单元测试与工程质量阶段](../ph12-testing-quality/12-testing-quality.md)；本阶段只借最简 JUnit 4 冒烟测试演示覆盖率
- **Web 工程的工程化**（Spring Boot starter、多环境 profile、打 war 部署容器）——ph15 Spring 全家桶阶段（roadmap 第 15 节，[详细展开版见](../ph15-spring-family/15-spring-family.md)）
- **CI/CD 流水线与制品治理**（Jenkins、GitHub Actions、Docker 镜像、Nexus/Artifactory 私服搭建）——ph19 DevOps 与部署阶段（roadmap 第 19 节，目录待建）；本阶段理解坐标与仓库机制即可

## 6. 代码示例

> 本阶段示例全部**本机实测通过**（OpenJDK 17.0.18 + Maven 3.9.12；本环境沙箱禁止写默认本地仓库 `~/.m2`，Maven 用 `mvn -o` 离线模式、依赖/插件取自本地仓库缓存——正常联网环境直接 `mvn clean package` 即可）。ex01~ex03 是 javac/jar/jlink 手工构建（纯 JDK，无需 Maven）；ex04/ex05 是 Maven 工程；**ex06 为 Gradle 概念对照，本环境未安装 Gradle，未实跑**。

### 示例 1：javac 手工构建（`examples/ex01-manual-javac.java`）

多文件、包、`-d` 输出目录与 `-cp` classpath 拼接的完整演示，对应 3.1：

```bash
# 1. 一次编译两个源文件到 build/
javac -d build ex01-manual-javac.java ex01-helper.java
# 2. 运行（实测输出: Hello, mosslau!）
java -cp build manual.ManualJavacDemo "mosslau"
```

### 示例 2：jar 打包与清单（`examples/ex02-jar-manifest.java`）

Main-Class 与 `java -jar` 的关系，对应 3.2。关键实测：无 Main-Class 的 jar 运行报 `app-plain.jar中没有主清单属性`；`jar cfe` 带上入口类后 `java -jar` 输出 `hello from jar`；`jar ufe` 可事后补主类。

### 示例 3：jlink 裁剪运行时（`examples/ex03-jlink-runtime.java`）

jdeps 分析 + jlink 裁剪 + 体积对比，对应 3.3。实测数字：`java.base,java.logging` 两模块裁剪出 **41M** 运行时（完整 JDK **305M**），只漏 `java.logging` 即 `NoClassDefFoundError`。

### 示例 4：手写最小 Maven 工程（`examples/ex04-maven-minimal/`）

pom.xml + 一个类，`mvn package` 打可执行 jar，对应 3.4。pom 关键点：`maven.compiler.release=17` + maven-jar-plugin 的 archive/manifest/mainClass（不写这段配置，`java -jar` 会报「没有主清单属性」，对照示例 2）：

```bash
cd examples/ex04-maven-minimal
mvn clean package                # 实测产物 target/hello-maven.jar（2552 字节）
java -jar target/hello-maven.jar # 实测输出: hello maven
```

### 示例 5：gson 依赖 + shade fat jar（`examples/ex05-maven-fatjar/`）

声明第三方依赖并打成可执行 fat jar，对应 3.5 与 3.6。实测：`mvn dependency:tree` 只有 `\- com.google.code.gson:gson:jar:2.10.1:compile` 一行；`target/cli-tool.jar` **287538 字节（≈280KB，含 gson）** vs `target/original-cli-tool.jar` **3462 字节**；运行输出 `{"file":"demo.txt","lines":3,"chars":18}`：

```xml
<!-- pom 关键点：依赖 + shade（完整版见 examples/ex05-maven-fatjar/pom.xml） -->
<dependencies>
  <dependency>
    <groupId>com.google.code.gson</groupId>
    <artifactId>gson</artifactId>
    <version>2.10.1</version>
  </dependency>
</dependencies>
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-shade-plugin</artifactId>
      <version>3.5.1</version>
      <executions>
        <execution>
          <phase>package</phase>
          <goals><goal>shade</goal></goals>
          <configuration>
            <transformers>
              <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                <mainClass>com.example.CliTool</mainClass>
              </transformer>
            </transformers>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

### 示例 6：Gradle 构建脚本对照（`examples/ex06-gradle-script.md`）

Groovy/Kotlin DSL 与 Maven 写法的对照表 + 标准命令，对应 3.7 与 4.5。**本环境未安装 Gradle，命令未实跑**——只做概念对照，学完示例 4/5 再看迁移成本极低。

## 7. 总结

### 关键要点

1. **构建工具负责依赖、编译、测试和打包四件事**——从 ph10 的 `javac` 手工编译升级为一条 `mvn clean test package` 自动化流水线
2. **手动构建先于工具**：javac `-d`/`-cp` 拼 classpath、jar 清单的 Main-Class、jlink 裁剪运行时——先理解 Maven 在自动化什么，才能用好 Maven
3. **坐标 `groupId:artifactId:version` 唯一定位构件**，依赖从本地仓库 → Maven Central/私服逐级解析；SNAPSHOT 是开发版，正式版发布后不可变
4. **scope 决定依赖出现在哪条 classpath**——compile 进产物、test 只在测试、provided 由容器提供（3.5 表格）
5. **生命周期阶段顺序执行**，阶段本身不干活，干活的是绑定在阶段上的插件目标（Mojo）——排查构建问题先查 execution 绑定
6. **依赖版本冲突需要显式管理**——最近优先 + 声明优先是默认仲裁，`dependencyManagement` 显式钉版本，`mvn dependency:tree` 排查，`exclusions` 兜底
7. **多模块要控制依赖方向**——依赖单向（app → common），公共代码下沉，循环依赖直接报 cycle；reactor 按依赖顺序构建，子模块单独构建需先 install
8. **打可执行 jar 两条路**——shade 打 fat jar（合并依赖 + 写 Main-Class，注意撞类风险），或薄 jar + 清单 `Class-Path`（相对 jar 解析外部依赖）
9. **构建产物应可复现**——版本写死、wrapper 固定工具版本、隔离环境因素、CI 全量 clean 构建
10. **质量工具挂在生命周期上**——Checkstyle 管风格、SpotBugs 管缺陷、JaCoCo 管覆盖率，覆盖率不是唯一质量指标
11. **Gradle 是 Maven 的现代替代**——Groovy/Kotlin DSL、任务依赖图、增量构建 + daemon + 构建缓存更快，Android 默认构建工具

### 阶段验收清单

- [ ] 能手工完成多文件工程构建：javac `-d`/`-cp` 编译、jar 打包与 Main-Class 清单、`java -jar` 运行（3.1/3.2、examples/ex01/ex02）
- [ ] 能用 jdeps + jlink 裁剪出可运行的精简运行时并解释体积差（3.3、examples/ex03）
- [ ] 能独立创建 Maven 工程：手写标准目录结构与 pom.xml，`mvn compile`/`mvn clean test package` 跑通（examples/ex04）
- [ ] 能解决依赖冲突：`mvn dependency:tree` 定位同一坐标多版本，用 dependencyManagement 显式仲裁（4.3）
- [ ] 能打包运行服务：shade 打可执行 fat jar，`java -jar target/xxx.jar` 直接运行（examples/ex05）
- [ ] 能配置覆盖率：JaCoCo prepare-agent + report，`mvn test` 后打开 `target/site/jacoco/index.html` 并读懂三类数字（exercises 练习 4）

### 跨语言对比：构建与工程化

| 维度 | Java / Maven（Gradle） | C++ / CMake | Go / Modules | Python / pip + pyproject.toml | Rust / Cargo |
|------|----------------------|-------------|--------------|------------------------------|--------------|
| 构建描述文件 | pom.xml（XML） | CMakeLists.txt（CMake DSL） | go.mod（声明式，自动维护） | pyproject.toml（TOML） | Cargo.toml（TOML） |
| 依赖来源 | Maven Central / 私服 | 系统库、vcpkg、conan | 模块代理（proxy.golang.org） | PyPI | crates.io |
| 版本冲突处理 | 最近优先 + dependencyManagement（显式） | 链接期可见性，靠组织规范 | 最小版本选择（MVS） | 解析器 + 锁定文件 | 语义化版本 + Cargo.lock |
| 增量/缓存 | 插件级增量，Gradle 强缓存 | ccache / ninja | 模块级缓存 | pip 缓存 | 增量编译 + 缓存 |
| 主要产物 | jar / war（fat jar 可执行） | 可执行文件 / 静态库 | 二进制可执行文件 | wheel / sdist | 二进制 / rlib |

对比结论：五种语言都走向「**声明式描述 + 中央仓库 + 版本解析**」的同一模式，差异在冲突策略与构建粒度：Maven 用「最近优先 + 显式覆盖」保留灵活性，Go 用最小版本选择追求简单，Rust 的 Cargo.lock 与 Python 的锁定文件把版本完全锁死换可复现；C++ 的 CMake 依赖库来自系统层，冲突在链接期才暴露，最需要组织规范兜底。Java 工程化的独特优势是**生命周期抽象 + 插件生态**：质量工具、打包、部署动作都能声明式挂进构建流水线，这是本阶段 `mvn` 命令背后整套机制的价值。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续：

- **创建 Maven 项目**（★）：手写最小 pom.xml + `src/main/java`，`mvn package` 打可执行 jar
- **引入第三方依赖**（★★）：声明 gson 并在代码中使用，`mvn dependency:tree` 观察依赖树
- **打可执行 jar**（★★★）：shade 打 fat jar，`java -jar` 运行，对比薄 jar 体积
- **配置覆盖率**（★★）：JaCoCo 两个 execution，读懂报告三类数字

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Maven 多模块模板**——父 pom（packaging=pom）+ `common` + `app` 两个子模块，dependencyManagement 集中管理第三方版本，依赖方向单向（app → common），`app` 用 shade 打可执行 fat jar，配套 `build.sh` 构建脚本；「可执行 CLI jar」整合进 `app` 模块一并落地。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[单元测试与工程质量阶段](../ph12-testing-quality/12-testing-quality.md) — 在 ph11 的工程骨架与 JaCoCo 覆盖率之上，深入学习 JUnit 5 断言、参数化测试、Mockito 隔离外部依赖、AssertJ 断言风格与 Testcontainers 集成测试，让「覆盖率报告」从数字变成可信的质量证据。
