# examples/ex06-gradle-script.md —— Gradle 构建脚本概念对照（概念讲解，非可运行示例）

> **本机未安装 Gradle（`gradle -version` → command not found），本示例只做概念对照，命令未实跑。**
> 对应主文档 3.7 与 4.5：Gradle 用任务（Task）依赖图代替固定生命周期，Groovy/Kotlin DSL 代替 XML。

## 同一件事：Maven 与 Gradle 的写法对照

| 维度 | Maven（pom.xml, XML） | Gradle（build.gradle, Groovy DSL / build.gradle.kts, Kotlin DSL） |
|------|----------------------|------------------------------------------------------------------|
| 插件声明 | `<plugin>` 坐标 | `plugins { id 'java' }` / `plugins { id("java") }` |
| 工程坐标 | `<groupId>com.example</groupId>` | `group = 'com.example'` / `group = "com.example"` |
| 仓库 | `<repositories>` 或继承默认中央仓库 | `repositories { mavenCentral() }` / `mavenCentral()` |
| 依赖 | `<dependencies><dependency>...` | `dependencies { implementation 'com.google.code.gson:gson:2.10.1' }` / `implementation("com.google.code.gson:gson:2.10.1")` |
| 打可执行 jar | maven-jar-plugin archive/manifest | `jar { manifest { attributes 'Main-Class': 'com.example.HelloGradle' } }` |
| 执行构建 | `mvn clean test package` | `./gradlew clean test jar`（或 `build`） |

## build.gradle（Groovy DSL）示例

```groovy
// build.gradle —— Groovy DSL, 本机未实测, 仅供对照
plugins {
    id 'java'                          // 引入 java 插件: 自动带来 compileJava/test/jar 等任务
}

group = 'com.example'
version = '1.0-SNAPSHOT'

repositories {
    mavenCentral()                     // 依赖来源: Maven Central（与 Maven 同一仓库体系）
}

dependencies {
    implementation 'com.google.code.gson:gson:2.10.1'   // 坐标写法与 Maven 完全同构
    testImplementation 'junit:junit:4.13.2'
}

jar {
    manifest {
        attributes 'Main-Class': 'com.example.HelloGradle'   // 打可执行 jar, 对应 ex04 的 archive/manifest
    }
}
```

## build.gradle.kts（Kotlin DSL）示例

```kotlin
// build.gradle.kts —— Kotlin DSL, 类型可检查（Gradle 5.0 起支持）, 本机未实测, 仅供对照
plugins {
    java
}

group = "com.example"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    implementation("com.google.code.gson:gson:2.10.1")
    testImplementation("junit:junit:4.13.2")
}

tasks.jar {
    manifest {
        attributes["Main-Class"] = "com.example.HelloGradle"
    }
}
```

## 标准命令（未实跑）

```bash
./gradlew build                  # 编译 + 测试 + 打 jar（Gradle Wrapper, 版本随项目, 对应 mvn clean test package）
./gradlew tasks                  # 列出所有可用任务（对应 mvn help:plugins 或直接看生命周期）
./gradlew dependencies           # 打印依赖树（对应 mvn dependency:tree）
gradle wrapper --gradle-version 8.10   # 生成 gradlew 包装器, 把 Gradle 版本写进项目
```

## 关键概念一句话

- **任务（Task）**：Gradle 的最小执行单元，`build`、`test`、`jar` 都是任务；任务之间声明依赖关系，构成**任务依赖图**，而不是 Maven 那种固定阶段序列
- **增量构建**：每个任务声明输入/输出，输入没变的任务标记 `up-to-date` 直接跳过（主文档 4.5 详述）
- **Gradle Daemon**：守护进程常驻内存，省掉每次构建的 JVM 启动开销——Gradle 快的两大原因之一
- **implementation ≈ Maven 的 compile**，但语义更细：不把依赖暴露给使用方，压缩传递面

> 本示例所有命令均未在本环境执行（未安装 Gradle）；学完 Maven（ex04/ex05）再读这份对照，两三分钟即可迁移。
