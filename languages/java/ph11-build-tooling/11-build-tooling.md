# Java Maven / Gradle 与工程化阶段

> 面向企业级后端、微服务方向，本阶段掌握 Maven / Gradle 构建工具并具备真实项目工程化能力——管得了依赖与生命周期，拿得起 pom.xml、多模块工程与可执行 jar。

## 1. 概述

构建工具阶段的目标是：**能管理真实 Java 项目**——用 Maven（或 Gradle）把依赖、编译、测试、打包串成一条自动化的流水线，而不是像 ph10 那样用 javac 手工编译。`javac Hello.java` 只适合单文件与临时 classpath，真实项目动辄几十个第三方库（JSON、日志、数据库驱动、测试框架），它们的 jar 从哪来、版本谁管、冲突怎么办、如何打包交付，就是本阶段要解决的问题：**构建工具（Build Tool）负责依赖、编译、测试和打包**，多模块工程要**控制依赖方向**，依赖版本冲突要**显式管理**，构建产物要**可复现**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 构建工具 | Maven 与 Gradle 选型、pom.xml / build.gradle、普通 jar 与可执行 fat jar（shade） |
| 坐标与仓库 | groupId:artifactId:version、本地仓库 / Maven Central / 私服 |
| 依赖管理 | 传递依赖、scope、冲突仲裁、dependencyManagement |
| 生命周期 | validate → compile → test → package → verify → install → deploy |
| 多模块工程 | 聚合与继承、依赖方向控制 |
| 质量工具 | Checkstyle、SpotBugs、JaCoCo 覆盖率 |

本阶段承接 ph10 JVM——javac 只能编译零散源码、classpath 全靠手工拼接，真实项目需要构建工具统一管理依赖、编译、测试与打包；不涉及单元测试框架深入（ph12：JUnit 断言、mock、覆盖率工程化）、Web 框架与 Spring 生态（ph15）、分布式问题（ph16）等。

## 2. 来源与演变

Java 诞生后的头十年，构建靠 `javac` 手工编译加 **Ant**（Apache Ant，2000 年发布）：用 XML 编写构建脚本（compile/jar 等 target），灵活但每个项目一套脚本、没有统一的依赖管理与生命周期，属于「脚本式构建」。真正的转折是 **Maven**：Maven 1.0（2004 年）引入**项目对象模型（Project Object Model, POM）**与**坐标（Coordinates）**，用 `groupId:artifactId:version` 三要素唯一定位一个构件（artifact），并依托 2002 年成立的 **Maven Central**（中央仓库）实现「声明依赖即自动下载」；Maven 2.0（2005 年）把**生命周期（Lifecycle）**与**传递依赖（Transitive Dependency）**定型——只声明直接依赖，它依赖的库会层层带下来，从此「约定优于配置（Convention over Configuration）」成为 Java 工程的事实标准。

**Gradle** 走的是另一条路：2007 年诞生、2012 年发布 1.0，用基于 **Groovy** 的领域特定语言（DSL）描述构建，构建模型是**任务依赖图（Task Graph）**而非固定阶段，天然支持**增量构建（Incremental Build）**；2018 年 Gradle 5.0 引入 **Kotlin DSL**，配置可静态类型检查。Gradle 构建更快、更灵活，是 Android 官方构建工具，但 Maven 生态更成熟、上手更平缓，企业存量工程仍以 Maven 为主——本阶段以 Maven 为主线（示例全部用 Maven 实测），Gradle 作为对比理解。

质量工具与构建工具并行演进：**Checkstyle**（2001 年）做代码风格静态检查；**FindBugs**（2006 年）做缺陷静态分析，2016 年社区 fork 为 **SpotBugs** 继续维护；**JaCoCo**（2014 年，EclEmma 核心的独立分支）做测试覆盖率统计，`mvn test` 后生成 HTML 报告，成为覆盖率的事实标准。三者与 Maven 的关系，见 3.5。

| 版本/年份 | 演进 |
|-----------|------|
| Ant（2000） | XML 脚本式构建，灵活但无依赖管理、无生命周期 |
| Maven 1.0（2004） | 引入 POM 与坐标；依托 Maven Central 中央仓库 |
| Maven 2.0（2005） | 生命周期与传递依赖定型，约定优于配置成为标准 |
| Gradle（2007 诞生 / 2012 1.0） | Groovy DSL 描述任务依赖图，增量构建、构建快 |
| Gradle 5.0（2018） | 引入 Kotlin DSL，配置可类型检查 |
| 质量工具 | Checkstyle（2001）、FindBugs（2006）→ SpotBugs（2016）、EclEmma（2005）→ JaCoCo（2014） |

## 3. 语法与参数

### 3.1 pom.xml 的结构：坐标与 packaging

Maven 工程的核心是根目录下的 `pom.xml`（Project Object Model），它声明了工程的**身份**、**依赖**与**构建方式**。最关键的几个元素：

| 元素 | 作用 | 示例 |
|------|------|------|
| `groupId` | 组织/公司唯一标识（反域名） | `com.example` |
| `artifactId` | 工程（模块）名称 | `hello-maven` |
| `version` | 版本号，SNAPSHOT 表示开发中快照 | `1.0-SNAPSHOT` |
| `packaging` | 打包类型，默认 jar | `jar` / `war` / `pom`（聚合父工程） |
| `properties` | 定义可复用属性（如 Java 版本） | `maven.compiler.source=1.8` |
| `dependencies` | 直接依赖列表 | gson、junit 等 |
| `dependencyManagement` | 集中声明版本，供子模块继承 | 见 4.2 |
| `build` | 构建配置（插件、finalName 等） | maven-shade-plugin |
| `modules` / `parent` | 多模块聚合 / 继承（4.3） | `<module>common</module>` |

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>hello-maven</artifactId>
  <version>1.0-SNAPSHOT</version>
  <properties>
    <maven.compiler.source>1.8</maven.compiler.source>
    <maven.compiler.target>1.8</maven.compiler.target>
  </properties>
</project>
```

- **标准目录结构是约定，不是配置**：主代码在 `src/main/java`，资源在 `src/main/resources`，测试代码在 `src/test/java`——Maven 默认就从这些位置找，目录错了编译出来是空的；`modelVersion` 固定写 4.0.0（pom 的 schema 版本，照抄即可）
- **SNAPSHOT 与正式版的区别**：`1.0-SNAPSHOT` 表示开发中快照，允许重复构建覆盖；正式版本 `1.0.0` 一经发布不允许再改，这是可复现构建的第一道约束

### 3.2 依赖管理：scope 与传递依赖

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

- **传递依赖（Transitive Dependency）**：依赖 gson，gson 自己依赖的库会自动进入 classpath——这正是「只声明直接依赖」的前提；`mvn dependency:tree` 可查看整棵依赖树
- **`optional`**：声明「我用得上但使用方未必需要」，如日志门面 slf4j 的各个实现，不让传递依赖污染使用方
- **`<exclusions>`**：排除某个传递依赖（如排除冲突的旧版 commons-xxx），是解决依赖冲突的最后一招（4.2）

### 3.3 Maven 生命周期与 mvn 常用命令

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
| `mvn dependency:tree` | 打印依赖树，查冲突（4.2） |
| `mvn help:effective-pom` | 查看继承合并后的**完整** pom |
| `mvn -pl app -am package` | 只构建 app 及其依赖的兄弟模块（4.3） |

- **命令的本质是「插件:目标（plugin:goal）」**：`mvn dependency:tree` 中 dependency 是插件、tree 是目标；`compile`/`package` 这类阶段名是关键字，会触发一串绑定的目标
- **本地仓库（Local Repository）**：默认 `~/.m2/repository`，下载的 jar 按坐标缓存于此，`install` 就是把你的工程也放进去——离线也能构建；Maven 3.8+ 默认屏蔽 HTTP 仓库，私服必须走 HTTPS 或显式放行

### 3.4 Gradle 视角：build.gradle 与 Kotlin DSL 对比

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

Gradle 脚本示例（Groovy DSL；Kotlin DSL 写 `build.gradle.kts`，括号语法）：`plugins { id 'java' }`、`group = 'com.example'`、`repositories { mavenCentral() }`、`dependencies { implementation 'com.google.code.gson:gson:2.10.1' }`（Kotlin 写法 `implementation("...")`）。

- **Gradle 的 `implementation` ≈ Maven 的 compile**，`testImplementation` ≈ test，语义更细（implementation 不把依赖暴露给使用方，进一步压缩传递面）；Kotlin DSL 写法是 `implementation("com.google.code.gson:gson:2.10.1")`
- **Gradle Wrapper（`gradlew`）**：把 Gradle 版本写进项目，团队任何人 `./gradlew build` 都得到同版本——这正是「构建产物可复现」的抓手，Maven 侧对应 `mvnw`（Maven Wrapper）
- 本阶段示例全部用 Maven 实测；学完 Maven 再读 Gradle 脚本，两三天即可迁移

### 3.5 质量工具：Checkstyle / SpotBugs / JaCoCo

工程化不止「能编译能打包」，还包括**质量门禁**，三个工具分工不同：

| 工具 | 检查什么 | 典型配置 | 失败表现 |
|------|---------|---------|---------|
| Checkstyle | 代码风格（命名、缩进、行宽、Javadoc） | `google_checks.xml` / 团队自定规则 | `mvn checkstyle:check` 报违规 |
| SpotBugs | 缺陷模式（空指针、资源未关、并发误用） | spotbugs-maven-plugin + `spotbugs:check` | 报告列出 bug 类别与位置 |
| JaCoCo | 测试覆盖率（指令/分支/行/方法/类） | prepare-agent + report（完整配置见示例 5） | 可配 check 阈值，不足则构建失败 |

- **三个工具都挂在生命周期上**：JaCoCo 的 prepare-agent 挂在 `initialize`（注入 javaagent 记录执行数据），report 挂在 `test` 后生成报告——这就是「插件绑定阶段」的实际应用
- **覆盖率不是唯一质量指标**：JaCoCo 告诉你「测没测到」，Checkstyle 管「像不像规范代码」，SpotBugs 管「有没有明显缺陷」，三者互补，ph12 再深入测试编写本身

### 3.6 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| 版本写 `RELEASE`/`LATEST` 或不写版本 | 构建不可复现，昨天能编今天报错 | 固定具体版本号，升级集中到 dependencyManagement |
| 依赖冲突没人管 | `NoSuchMethodError`、类版本错乱 | `mvn dependency:tree` 定位 + 显式仲裁（4.2） |
| 多模块循环依赖 | reactor 报 cycle 错误 | 依赖方向单向化，公共代码下沉到 common |
| scope 用错 | 测试能过、运行时 `ClassNotFoundException` | provided/test 不打进产物，确认 3.2 表格 |
| 单独构建子模块失败 | 找不到兄弟模块的 jar | 先 `mvn install` 父工程，或 `mvn -pl app -am` |
| 发布前不 clean | 改了代码却拿到旧产物 | `mvn clean test package`（roadmap 示例命令） |

## 4. 底层原理

### 4.1 生命周期：阶段顺序与插件绑定

`mvn package` 为什么能自动编译、测试、打包？因为**阶段是顺序执行的**：调用 `package` 阶段，Maven 按 `validate → initialize → ... → compile → ... → test → ... → package` 依次执行，每个阶段上绑定的插件目标（Mojo，Maven 插件的最小执行单元）依次运行。`mvn test` 不会跳过 compile，因为 test 依赖 compile 先完成——阶段间的先后关系由生命周期定义，而非由你手动编排。

```
validate → initialize → generate-sources → process-sources → generate-resources
→ process-resources → compile → process-classes → generate-test-sources
→ process-test-resources → test-compile → test → prepare-package → package
→ pre-integration-test → integration-test → verify → install → deploy
```

- **插件是生命周期的执行者**：compile 阶段绑定 maven-compiler-plugin，test 阶段绑定 maven-surefire-plugin，package 阶段绑定 maven-jar-plugin——阶段本身不干活，干活的都是插件；`<executions>` 把插件目标挂到指定阶段（3.5 的 JaCoCo 就是例子），`prepare-agent` 默认绑定 `initialize`，report 通过 `<phase>test</phase>` 显式挂到 test 之后
- **理解这个机制的意义**：排查「为什么我的插件没跑/跑错顺序」时，先查 execution 的 phase 与 goal 绑定，再查插件版本——90% 的构建问题出在这两处

### 4.2 依赖解析与冲突仲裁

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
- **Gradle 的仲裁更严格**：默认版本冲突直接**构建失败**，要求你用 `resolutionStrategy` 显式解决——它把「显式管理」从最佳实践变成了强制约束

### 4.3 多模块：聚合、继承与依赖方向

多模块工程（multi-module project）把一个大工程拆成多个可独立构建的模块。父 pom 用 `packaging=pom` 同时做两件事：**聚合（Aggregation）**——`<modules>` 声明子模块，一次 `mvn package` 按依赖顺序构建全部模块（reactor 构建）；**继承（Inheritance）**——子模块 `<parent>` 指向父 pom，继承属性、依赖管理与插件配置。

- **依赖方向必须单向**：模块依赖只能指向「下层」，公共代码放 `common`，业务模块依赖 common，严禁 common 反向依赖业务模块——一旦成环，reactor 直接报 `cycle` 错误，因为构建顺序无法确定
- **版本集中管理**：父 pom 的 `dependencyManagement` 声明所有第三方版本，子模块引用时**不写版本**（`<version>` 可省），升版本只改一处
- **reactor 构建顺序**：Maven 先解析模块依赖图，被依赖的模块先构建；所以 `mvn package` 在根目录跑，common 一定先于 app 产出 jar
- **子模块单独构建的前提**：兄弟模块的 jar 必须先在本地仓库（`mvn install`）——reactor 只在根目录整批构建时生效；CI 里用 `mvn -pl app -am package`（-am 同时构建依赖模块）

### 4.4 Gradle 增量构建、daemon 与构建缓存

Gradle 快的底层原因有三个。**增量构建（Incremental Build）**：每个任务声明输入（源码、配置）与输出（产物），Gradle 对输入做**内容快照**，输入没变的任务直接标记 up-to-date 跳过——改一个文件只重编受影响的部分；Maven 的增量依赖插件各自判断，粒度粗得多。**守护进程（Daemon）**：构建逻辑常驻内存（Gradle Daemon），后续构建复用已加载的类与依赖元数据，省掉每次 JVM 启动开销。**构建缓存（Build Cache）**：任务输出按输入哈希缓存，同一输入在其他机器/分支上构建过，直接复用缓存产物，CI 与本地共享缓存时收益最明显。

- **增量构建的前提是「输入声明完整」**：漏声明输入（如读了外部文件但没列入 inputs）会导致缓存错用——这是 Gradle 缓存玄学问题的根源；Gradle 7+ 的**配置缓存（Configuration Cache）**进一步缓存构建脚本的配置阶段结果
- **对 Maven 用户的启示**：Maven 的慢是设计使然（无守护进程、弱增量），所以大工程常配 maven daemon（mvnd）或直接转 Gradle——工具选型是工程决策，不是信仰问题

### 4.5 可复现构建

**可复现构建（Reproducible Build）**指：同一份源码 + 同一份构建描述，在任何时间、任何机器上产出**逐字节一致**的产物。它保证「CI 上能出、本地就一定能出」，是交付可信度的基础。要做到：

- **固定所有版本**：依赖版本、插件版本都写死，禁止 RELEASE/LATEST；`dependencyManagement` 同时锁住传递依赖（或 Gradle 的 dependency locking 生成锁文件）
- **固定构建工具版本**：用 Wrapper（`mvnw` / `gradlew`）把 Maven/Gradle 版本写进仓库，团队与 CI 用同版本构建；Maven 3.7+ 可用 `project.build.outputTimestamp` 固定 jar 内的时间戳
- **隔离环境因素，一次构建出一份产物**：构建路径、时区、locale 不影响产物；CI 上 `mvn clean test package` 全量构建，禁止「上次的 target 接着用」，发布产物的哈希应可预期、可校验

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 新建一个 Java 项目 | 标准目录结构 + pom.xml 骨架（3.1、示例 1） |
| 引入第三方库（JSON/日志/数据库驱动） | 坐标、scope、传递依赖（3.2、示例 2） |
| 提交代码前统一构建 | `mvn clean test package` 生命周期（3.3） |
| 交付可运行的服务/CLI | shade 打可执行 fat jar（示例 3） |
| 拆分多模块工程（common/api/service） | 聚合、继承与依赖方向（4.3、示例 4） |
| 依赖冲突排查 | `mvn dependency:tree` + dependencyManagement（4.2） |
| 质量门禁与覆盖率 | Checkstyle / SpotBugs / JaCoCo（3.5、示例 5） |

**不适合**此阶段的事项：
- **单元测试的编写与设计**（JUnit 断言、Mockito、参数化测试、Testcontainers）——ph12 单元测试与工程质量阶段；本阶段只借最简 JUnit 4 冒烟测试演示覆盖率
- **Web 工程的工程化**（Spring Boot starter、多环境 profile、打 war 部署容器）——ph15 Spring 生态阶段
- **CI/CD 流水线与制品治理**（Jenkins、GitHub Actions、Docker 镜像、Nexus/Artifactory 私服搭建）——ph19 DevOps 与部署阶段；本阶段理解坐标与仓库机制即可

## 6. 代码示例

> 以下示例全部本机实测通过（JDK 8 + Maven 3.8.2），新建工程时按 3.1 的标准目录结构放代码：`src/main/java` 与 `src/test/java`。

### 示例 1：手写最小 Maven 工程（pom.xml + 一个类，`mvn compile` 构建）

对应 roadmap 练习「创建 Maven 项目」与必会概念「构建工具负责依赖、编译、测试和打包」：不借助脚手架，用 3.1 的 pom.xml 与一个类跑通构建。
```java
// src/main/java/com/example/HelloMaven.java
package com.example;

public class HelloMaven {
    public static void main(String[] args) {
        System.out.println("hello maven");
    }
}
```
```bash
mvn compile    # 编译主代码
# 成功后产物在 target/classes/com/example/HelloMaven.class（等价于 ph10 的 javac 输出）
```
提示：pom.xml 直接使用 3.1 的最小 pom（改 artifactId 即可）。目录结构必须严格是 `src/main/java`；首次运行 Maven 会下载插件与依赖，之后走本地仓库缓存。`mvn package` 会连测试一起跑并打出 jar，ph10 里 `javac Hello.java && java Hello` 的两步，到这里变成一条命令。

### 示例 2：引入第三方依赖（gson）并在代码中使用，`mvn package` 打 jar

对应 roadmap 练习「引入第三方依赖」：坐标声明依赖，代码里直接用，观察传递依赖。pom = 3.1 最小 pom + gson 依赖（写法见 3.2 的 dependencies 片段）：
```java
// src/main/java/com/example/JsonTool.java
package com.example;

import com.google.gson.Gson;
import java.util.HashMap;
import java.util.Map;

public class JsonTool {
    public static void main(String[] args) {
        Map<String, Object> data = new HashMap<>();
        data.put("name", "Java");
        data.put("phase", 11);
        System.out.println(new Gson().toJson(data));
    }
}
```
```bash
mvn package                  # 编译 + 测试 + 打包，产物为约 2.6 KB 的薄 jar（不含 gson）
mvn dependency:tree          # 依赖树：只有 gson 一个节点（它没有传递依赖）
# [INFO] \- com.google.code.gson:gson:jar:2.10.1:compile
```
提示：这个 jar 里没有 gson 的类，直接 `java -jar` 会 `NoClassDefFoundError`——这正是示例 3 要解决的问题。gson 是「无传递依赖」的干净库，换成 slf4j + logback 就能在依赖树里看到一层层带下来的传递依赖。版本号写死在 pom 里（而不是写 RELEASE），是 4.5 可复现构建的第一步。

### 示例 3：打可执行 jar（maven-shade-plugin 打 fat jar，`java -jar` 运行）

对应 roadmap 练习「打可执行 jar」：把依赖的类合并进一个**fat jar（Uber Jar）**，并写入 Main-Class，实现一条命令直接运行。两种运行方式都实测通过：shade 插件打 fat jar 后用 `java -jar`，或 exec-maven-plugin 用 `mvn exec:java` 免打包调试。pom = 示例 2 的 pom（artifactId 改 `cli-tool`）+ 以下 `<build>` 块：
```xml
<build>
  <finalName>cli-tool</finalName>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-shade-plugin</artifactId>
      <version>3.4.1</version>
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
```java
// src/main/java/com/example/CliTool.java
package com.example;

import com.google.gson.Gson;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;

public class CliTool {
    public static void main(String[] args) throws Exception {
        String file = args[0];
        String content = new String(Files.readAllBytes(Paths.get(file)));
        Map<String, Object> data = new HashMap<>();
        data.put("file", file);
        data.put("lines", content.split("\n").length);
        System.out.println(new Gson().toJson(data));
    }
}
```
```bash
mvn clean package                          # 打 fat jar（cli-tool.jar 约 280 KB 含 gson；original-cli-tool.jar 为薄 jar）
echo -e "line1\nline2\nline3" > demo.txt
java -jar target/cli-tool.jar demo.txt     # 输出 {"file":"demo.txt","lines":3}
```
提示：shade 会把所有依赖类**重打包进一个 jar** 并生成 `META-INF/MANIFEST.MF` 的 `Main-Class`（ManifestResourceTransformer 干的事）——`java -jar` 靠它找到入口。`target/original-cli-tool.jar` 是不含依赖的原始产物，两者体积对比就是「依赖合并」的直观证据。调试期可另配 exec-maven-plugin（1.6.0，mainClass 指向 CliTool）后用 `mvn exec:java -Dexec.args="demo.txt"` 免打包运行（本机已实测）。fat jar 的问题是可能撞类（多个库带同包名类），复杂工程用 Spring Boot 的 layered jar 思路（ph15）更稳妥。

### 示例 4：多模块项目（父 pom + common + app 两个子模块，控制依赖方向）

对应推荐项目「Maven 多模块模板」与必会概念「多模块要控制依赖方向」：父 pom 聚合两个子模块，app 依赖 common（单向），第三方版本在父工程集中管理。
```xml
<!-- 父 pom.xml（工程根目录） -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>multi-demo</artifactId>
  <version>1.0-SNAPSHOT</version>
  <packaging>pom</packaging>
  <modules>
    <module>common</module>
    <module>app</module>
  </modules>
  <properties>
    <maven.compiler.source>1.8</maven.compiler.source>
    <maven.compiler.target>1.8</maven.compiler.target>
  </properties>
  <dependencyManagement>
    <dependencies>
      <dependency><groupId>com.google.code.gson</groupId><artifactId>gson</artifactId><version>2.10.1</version></dependency>
    </dependencies>
  </dependencyManagement>
</project>
```
```xml
<!-- common/pom.xml：只声明 parent，无外部依赖 -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.example</groupId>
    <artifactId>multi-demo</artifactId>
    <version>1.0-SNAPSHOT</version>
  </parent>
  <artifactId>common</artifactId>
</project>
```
```java
// common/src/main/java/com/example/Strings.java（公共工具，放在依赖链最底层）
package com.example;

public class Strings {
    public static String repeat(String s, int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) sb.append(s);
        return sb.toString();
    }
}
```
```xml
<!-- app/pom.xml：依赖 common（版本随父工程）+ gson（版本由 dependencyManagement 提供） -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.example</groupId>
    <artifactId>multi-demo</artifactId>
    <version>1.0-SNAPSHOT</version>
  </parent>
  <artifactId>app</artifactId>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>common</artifactId>
      <version>${project.version}</version>
    </dependency>
    <dependency>
      <groupId>com.google.code.gson</groupId>
      <artifactId>gson</artifactId>
    </dependency>
  </dependencies>
</project>
```
```java
// app/src/main/java/com/example/AppMain.java
package com.example;

import com.google.gson.Gson;
import java.util.HashMap;
import java.util.Map;

public class AppMain {
    public static void main(String[] args) {
        Map<String, Object> data = new HashMap<>();
        data.put("msg", Strings.repeat("ha", 3));
        System.out.println(new Gson().toJson(data));
    }
}
```
```bash
mvn clean package     # 根目录跑：reactor 按依赖顺序构建 common → app，产出两个 jar
mvn install           # 把模块装进本地仓库（单独构建 app 的前提）
mvn dependency:tree   # app 的依赖树：common + gson，方向单向
# com.example:app:jar:1.0-SNAPSHOT
# +- com.example:common:jar:1.0-SNAPSHOT:compile
# \- com.google.code.gson:gson:jar:2.10.1:compile
```
提示：依赖方向是 `app → common`，common 绝不反向依赖 app；公共代码永远下沉。子模块单独 `mvn package` 会因找不到兄弟模块而失败，必须先 `mvn install` 父工程（或 `mvn -pl app -am package`）——这是 reactor 与本地仓库的协作机制（4.3）。注意 app 依赖 common 用了 `${project.version}`，保证版本与父工程永远一致。

### 示例 5：JaCoCo 覆盖率接入（`mvn test` 后生成 `target/site/jacoco/index.html`）

对应 roadmap 练习「配置覆盖率」：挂上 JaCoCo 插件，跑测试后自动生成覆盖率报告。这里只用最简 JUnit 4 冒烟测试演示（JUnit 的深入编写在 ph12）。pom = 3.1 最小 pom + 以下 `dependencies` 与 `build` 块：
```xml
<dependencies>
  <dependency>
    <groupId>junit</groupId>
    <artifactId>junit</artifactId>
    <version>4.13.2</version>
    <scope>test</scope>
  </dependency>
</dependencies>
```
```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.jacoco</groupId>
      <artifactId>jacoco-maven-plugin</artifactId>
      <version>0.8.11</version>
      <executions>
        <execution>
          <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
          <id>report</id>
          <phase>test</phase>
          <goals><goal>report</goal></goals>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```
```java
// src/main/java/com/example/Calculator.java
package com.example;

public class Calculator {
    public int add(int a, int b) { return a + b; }
    public int divide(int a, int b) { return a / b; }
}
```
```java
// src/test/java/com/example/CalculatorTest.java
package com.example;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class CalculatorTest {
    @Test
    public void testAdd() {
        assertEquals(3, new Calculator().add(1, 2));
    }
}
```
```bash
mvn clean test package          # 测试通过并触发 jacoco:report
# [INFO] --- jacoco-maven-plugin:0.8.11:prepare-agent ... argLine set to -javaagent:...jacoco.exec
# Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
open target/site/jacoco/index.html   # 浏览器打开覆盖率报告
```
```
报告中的实测数字（Calculator 类）：
- 指令覆盖率（Instruction）63%（7/11）——add 的指令被覆盖，divide 没有
- 行覆盖率 2/3、方法覆盖率 2/3——testAdd 只测了 add，divide 无人问津
```
提示：JaCoCo 的原理是 **prepare-agent 阶段给 surefire 注入 javaagent**（输出里的 `argLine set to -javaagent:...`），测试执行时记录字节码覆盖数据到 `target/jacoco.exec`，report 目标再把它渲染成 HTML/CSV。覆盖率报告要同时看指令、分支、行三类数字；分叉逻辑（if/switch）才有分支覆盖概念。想看 100% 就把 divide 也测了——这也预告了 ph12 的主题：覆盖率只是结果，测试设计才是源头。

## 7. 总结

### 关键要点

1. **构建工具负责依赖、编译、测试和打包四件事**——从 ph10 的 `javac` 手工编译升级为一条 `mvn clean test package` 自动化流水线
2. **坐标 `groupId:artifactId:version` 唯一定位构件**，依赖从本地仓库 → Maven Central/私服逐级解析；SNAPSHOT 是开发版，正式版发布后不可变
3. **scope 决定依赖出现在哪条 classpath**——compile 进产物、test 只在测试、provided 由容器提供（3.2 表格）
4. **生命周期阶段顺序执行**，阶段本身不干活，干活的是绑定在阶段上的插件目标（Mojo）——排查构建问题先查 execution 绑定
5. **依赖版本冲突需要显式管理**——最近优先 + 声明优先是默认仲裁，`dependencyManagement` 显式钉版本，`mvn dependency:tree` 排查，`exclusions` 兜底
6. **多模块要控制依赖方向**——依赖单向（app → common），公共代码下沉，循环依赖直接报 cycle；reactor 按依赖顺序构建，子模块单独构建需先 install
7. **打可执行 jar 要打 fat jar**——maven-shade-plugin 合并依赖并写 Main-Class，`java -jar` 才能直接跑；薄 jar 需要手工拼 classpath
8. **构建产物应可复现**——版本写死、wrapper 固定工具版本、隔离环境因素、CI 全量 clean 构建
9. **质量工具挂在生命周期上**——Checkstyle 管风格、SpotBugs 管缺陷、JaCoCo 管覆盖率（`target/site/jacoco/index.html`），覆盖率不是唯一质量指标
10. **Gradle 是 Maven 的现代替代**——Groovy/Kotlin DSL、任务依赖图、增量构建 + daemon + 构建缓存更快，Android 默认构建工具

### 跨语言对比：构建与工程化

| 维度 | Java / Maven（Gradle） | C++ / CMake | Go / Modules | Python / pip + pyproject.toml | Rust / Cargo |
|------|----------------------|-------------|--------------|------------------------------|--------------|
| 构建描述文件 | pom.xml（XML） | CMakeLists.txt（CMake DSL） | go.mod（声明式，自动维护） | pyproject.toml（TOML） | Cargo.toml（TOML） |
| 依赖来源 | Maven Central / 私服 | 系统库、vcpkg、conan | 模块代理（proxy.golang.org） | PyPI | crates.io |
| 版本冲突处理 | 最近优先 + dependencyManagement（显式） | 链接期可见性，靠组织规范 | 最小版本选择（MVS） | 解析器 + 锁定文件 | 语义化版本 + Cargo.lock |
| 增量/缓存 | 插件级增量，Gradle 强缓存 | ccache / ninja | 模块级缓存 | pip 缓存 | 增量编译 + 缓存 |
| 主要产物 | jar / war（fat jar 可执行） | 可执行文件 / 静态库 | 二进制可执行文件 | wheel / sdist | 二进制 / rlib |

对比结论：五种语言都走向「**声明式描述 + 中央仓库 + 版本解析**」的同一模式，差异在冲突策略与构建粒度：Maven 用「最近优先 + 显式覆盖」保留灵活性，Go 用最小版本选择追求简单，Rust 的 Cargo.lock 与 Python 的锁定文件把版本完全锁死换可复现；C++ 的 CMake 依赖库来自系统层，冲突在链接期才暴露，最需要组织规范兜底。Java 工程化的独特优势是**生命周期抽象 + 插件生态**：质量工具、打包、部署动作都能声明式挂进构建流水线，这是本阶段 `mvn` 命令背后整套机制的价值。

### 阶段验收标准

- 能独立创建工程：手写标准目录结构与 pom.xml，`mvn compile`/`mvn clean test package` 跑通（示例 1、示例 2）
- 能解决依赖冲突：`mvn dependency:tree` 定位同一坐标多版本，用 dependencyManagement 显式仲裁（4.2）
- 能打包运行服务：shade 打可执行 fat jar，`java -jar target/xxx.jar` 直接运行（示例 3）
- 能配置覆盖率：JaCoCo prepare-agent + report，`mvn test` 后打开 `target/site/jacoco/index.html` 并读懂三类数字（示例 5）

### 进入下一阶段前

确保能完成以下练习：
- **创建 Maven 项目**：手写最小 pom.xml + `src/main/java` 目录，`mvn compile` 与 `mvn package` 跑通（提示：目录结构是约定不是配置；也可用 `mvn archetype:generate` 生成骨架，但建议先手写一遍理解结构）
- **引入第三方依赖**：声明 gson 并在代码中使用，`mvn dependency:tree` 观察依赖树（提示：gson 无传递依赖，换 slf4j + logback 才能看到传递依赖的层层展开）
- **打可执行 jar**：shade 配置 Main-Class 后 `java -jar` 运行；调试期可用 `mvn exec:java`（提示：对比 fat jar 与 original 薄 jar 的体积，理解「依赖合并」）
- **配置覆盖率**：JaCoCo 两个 execution（prepare-agent + report），`mvn test` 后打开报告（提示：故意不测某个方法，观察覆盖率下降，理解「覆盖率 = 测到的 ÷ 全部」）

### 推荐项目

- **Maven 多模块模板**：父 pom（packaging=pom）+ `common` + `app` 子模块，dependencyManagement 集中管理第三方版本，依赖方向单向（app → common），`mvn install` 后子模块可独立构建——把这个模板作为 ph12 起的**工程骨架**，后续每阶段练习都往里面加新模块
- **可执行 CLI jar**：做一个命令行小工具（JSON 格式化、文件行数统计、词频统计均可），引入 gson，用 shade 打成 fat jar，`java -jar xxx.jar 参数` 即可分发运行——覆盖「创建工程 → 引依赖 → 打包 → 运行」全链路，也是 ph12 测试练习的理想载体

### 下一阶段

**单元测试与工程质量阶段**（`ph12-unit-testing`，文档规划中）—— 在 ph11 的工程骨架与 JaCoCo 覆盖率之上，深入学习 JUnit 5 断言、Mockito 隔离外部依赖、AssertJ 断言风格与 Testcontainers 集成测试，让「覆盖率报告」从数字变成可信的质量证据。
