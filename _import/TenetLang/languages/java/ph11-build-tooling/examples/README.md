# ph11 构建工具与工程化 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，覆盖「javac/jar/jlink 手动构建 → Maven 自动化 → Gradle 概念对照」的完整链路。验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）**；**本机未安装 Gradle，ex06 只做概念对照、命令未实跑**。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：本环境沙箱禁止写默认本地仓库 `~/.m2`（`Operation not permitted`），而所需构件（gson 2.10.1、maven-shade-plugin 3.5.1、jacoco-maven-plugin 0.8.11、junit 4.13.2 等）已在本地仓库缓存，`mvn -o` 可完全离线构建。**在正常联网环境直接执行 `mvn clean package` 即可**（首次运行会从 Maven Central 下载插件与依赖，之后走本地缓存）。

## 类名与文件名说明

ex01~ex03 沿用 ph10 的惯例：文件名（`ex0X-*.java`）与类名不一致，因此这些类**刻意不声明为 `public`**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译用**文件名**，运行用**类名**。ex04/ex05 是完整 Maven 工程（pom.xml + src 目录），在各自目录内构建。

## 示例列表

| 文件/目录 | 类名 | 说明 | 编译 | 运行 |
|-----------|------|------|------|------|
| ex01-manual-javac.java（+ ex01-helper.java） | manual.ManualJavacDemo | javac 手动构建：多文件、包、`-d` 输出目录、`-cp` classpath 拼接 | `javac -d build ex01-manual-javac.java ex01-helper.java` | `java -cp build manual.ManualJavacDemo "mosslau"` |
| ex02-jar-manifest.java | JarManifestDemo | jar 打包与清单：无 Main-Class 报错 → `cfe` 带主类 → `ufe` 事后补主类，`java -jar` 运行 | `javac -d build ex02-jar-manifest.java` | `jar cfe app-main.jar JarManifestDemo -C build .` 后 `java -jar app-main.jar` |
| ex03-jlink-runtime.java | JlinkRuntimeDemo | jdeps 分析依赖模块 + jlink 裁剪精简运行时 + 体积对比 + 缺模块后果 | `javac -d build ex03-jlink-runtime.java` | `jlink --add-modules java.base,java.logging --output runtime-min` 后 `runtime-min/bin/java -cp build JlinkRuntimeDemo` |
| ex04-maven-minimal/ | com.example.HelloMaven | 手写最小 Maven 工程：pom.xml + 一个类，`mvn package` 打可执行 jar | `mvn clean package` | `java -jar target/hello-maven.jar` |
| ex05-maven-fatjar/ | com.example.CliTool | 声明 gson 依赖 + shade 打 fat jar：文本统计 CLI，`java -jar` 单命令运行 | `mvn clean package` | `printf 'line1\nline2\nline3\n' > demo.txt && java -jar target/cli-tool.jar demo.txt` |
| ex06-gradle-script.md | — | Gradle 概念对照（Groovy/Kotlin DSL + 标准命令），**未实跑** | — | — |

## 验证状态与实测输出要点

全部 ex01~ex05 已在本环境（OpenJDK 17.0.18 + Maven 3.9.12，Apple Silicon / macOS）编译运行验证，记录如下：

### ex01：javac 手动构建

- 一次编译两文件：`javac -d build ex01-manual-javac.java ex01-helper.java` → 产物 `build/manual/ManualJavacDemo.class` + `build/manual/Helper.class`（`-d` 自动按包建目录）
- `java -cp build manual.ManualJavacDemo "mosslau"` → 实测输出 `Hello, mosslau!`
- classpath 分离：helper 单独编译到 `build-lib`，主程序 `javac -d build-app -cp build-lib ...` 编译、`java -cp build-lib:build-app ...` 运行，同样输出 `Hello, mosslau!`——**javac 从 classpath 解析已编译类，这就是「编译期 classpath」**
- 与 ph10 的关系：ph10 只演示单文件 `javac Hello.java` 与 class 文件结构；本示例展示多文件工程的手工构建，是 Maven 自动化掉的那条链

### ex02：jar 打包与清单

- 无 Main-Class 的 jar：`java -jar app-plain.jar` → 实测报错 `app-plain.jar中没有主清单属性`（JDK 17 中文 locale 输出；英文环境为 `no main manifest attribute in ...`）
- `jar cfe app-main.jar JarManifestDemo -C build .` → 清单含 `Main-Class: JarManifestDemo`，`java -jar app-main.jar` → 实测输出 `hello from jar`
- `jar ufe app-plain.jar JarManifestDemo -C build .` 事后补主类 → `java -jar app-plain.jar` 同样可运行——**Main-Class 是清单属性，打包后仍可改**
- `jar cf` 与 `jar cfe` 的差别：`e` 选项写入口点（entrypoint），等价于打包后手工编辑 `META-INF/MANIFEST.MF` 加一行 `Main-Class`

### ex03：jlink 精简运行时

- `jdeps --print-module-deps build/JlinkRuntimeDemo.class` → 实测输出 `java.base,java.logging`（程序用到 `java.util.logging`）
- `jlink --add-modules java.base,java.logging --output runtime-min` → 生成独立运行时，`runtime-min/bin/java` 可运行（`-version` → 17.0.18）
- `runtime-min/bin/java -cp build JlinkRuntimeDemo` → 实测输出 `hello from jlink runtime`（`LOG.info` 输出走 stderr）
- 体积对比（本机实测）：精简运行时 **41M** vs 完整 JDK **305M**——裁掉约 87%
- 缺模块后果：只 `--add-modules java.base` 的运行时运行同一程序 → 实测 `NoClassDefFoundError: java/util/logging/Logger`——**jlink 按模块裁剪，漏模块就是运行期找不到类**

### ex04：最小 Maven 工程

- `mvn clean package` → BUILD SUCCESS，产物 `target/hello-maven.jar`（实测 **2552 字节**）
- `java -jar target/hello-maven.jar` → 实测输出 `hello maven`
- 清单实测含 `Main-Class: com.example.HelloMaven`（maven-jar-plugin 的 archive/manifest 配置生效）；若不加这段配置，`java -jar` 会报「没有主清单属性」（对照 ex02）

### ex05：gson 依赖 + shade fat jar

- `mvn dependency:tree` → 实测依赖树只有一行：`\- com.google.code.gson:gson:jar:2.10.1:compile`（gson 无传递依赖，是干净的演示库）
- 产物对比（实测）：`target/cli-tool.jar` **287538 字节（≈280KB，含 gson）** vs `target/original-cli-tool.jar` **3462 字节（薄 jar）**——体积差就是「依赖合并」的直观证据
- 运行：`printf 'line1\nline2\nline3\n' > demo.txt && java -jar target/cli-tool.jar demo.txt` → 实测输出 `{"file":"demo.txt","lines":3,"chars":18}`
- 不带参数 → 实测 stderr 打印用法、退出码 2（CliTool 的参数校验分支）
- shade 构建时会提示 `define 1 overlapping resource`（gson 的 `META-INF/maven/...` 资源重名）——**这是 fat jar 的正常噪声，不是错误**；复杂工程的撞类问题见主文档 4.1

## 产物清理

ex01~ex03 编译/打包后当前目录会产生 `.class`、`.jar`、`runtime-min/`、`runtime-base/` 等产物，验证完清理（不要把产物提交进仓库）：

```bash
# ex01
rm -rf build build-lib build-app
# ex02
rm -rf build app-plain.jar app-main.jar
# ex03
rm -rf build runtime-min runtime-base
# ex04 / ex05（Maven 工程）
cd ex04-maven-minimal && mvn clean && rm -f demo.txt   # demo.txt 是运行示例时自己生成的输入文件
cd ../ex05-maven-fatjar && mvn clean && rm -f demo.txt
```
