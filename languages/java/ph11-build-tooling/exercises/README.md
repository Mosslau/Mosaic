# ph11 构建工具与工程化 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）。本机 Maven 实测用 `mvn -o` 离线模式（沙箱禁止写默认本地仓库 `~/.m2`，依赖来自本地缓存）；正常联网环境直接 `mvn clean package` 即可。
> 四题与 Roadmap「ph11 Maven / Gradle 与工程化阶段」练习小节一一对应：创建 Maven 项目 / 引入第三方依赖 / 打可执行 jar / 配置覆盖率。sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看；sol 文件是「源代码 + 注释里的完整 pom」，建工程时按注释把 pom 写入自己的 pom.xml。
> 练习 2、3 会从 Maven Central 下载依赖（本机为离线缓存），首次运行网络不通时检查镜像与本地仓库；练习 3 的 fat jar 体积数字与主文档 6 章示例 5 接近（sol-03 为 286933/2857 字节，示例 5 为 287538/3462 字节，差异原因见 sol-03 文件头）。

## 练习 1：创建 Maven 项目（★）

**目标**：不借助脚手架（不用 `mvn archetype:generate`），手写最小 Maven 工程跑通「编译 → 打包 → 运行」全链路——理解目录结构与 pom.xml 是约定不是配置。
**要求**：

- 手写 `pom.xml`：`groupId` / `artifactId` / `version` 三要素、`<properties>` 里设 `maven.compiler.release=17`、`<build>` 里用 maven-jar-plugin 的 `archive/manifest/mainClass` 把入口类写进清单
- 目录结构必须严格是 `src/main/java`（Maven 默认找这里，目录错了编译出来是空的）
- 写一个 `HelloMaven` 类（package `com.example`），main 打印一行文本

**验收**：`mvn clean package` 成功且产物 jar 在 `target/`；`unzip -p <jar> META-INF/MANIFEST.MF` 能看到 `Main-Class: com.example.HelloMaven`；`java -jar target/<你的jar>` 输出你写的那行文本。

## 练习 2：引入第三方依赖（★★）

**目标**：用坐标声明依赖并在代码中使用，观察依赖树——理解「声明依赖即自动下载/解析」与 scope。
**要求**：

- 在 练习 1 的 pom 上加 `com.google.code.gson:gson:2.10.1` 依赖（compile scope 是默认，可不写）
- 写一个 `JsonTool` 类：用 `new Gson().toJson(map)` 把一个 Map 序列化打印（Map 至少 3 个键值对，如 name/phase/tool）
- 运行 `mvn dependency:tree`，确认依赖树里只有 gson 一个节点（gson 无传递依赖，是干净演示）

**验收**：`mvn package` 成功；`mvn dependency:tree` 输出 `\- com.google.code.gson:gson:jar:2.10.1:compile`；`java -cp "target/<jar>:<gson jar 路径>" com.example.JsonTool` 输出合法 JSON。**提示**：这个薄 jar 里没有 gson 的类，`java -jar` 会报「没有主清单属性」或运行期找不到类——这正是练习 3 要解决的问题。

## 练习 3：打可执行 jar（★★★）

**目标**：用 maven-shade-plugin 把依赖合并进 fat jar 并写 Main-Class，实现 `java -jar` 一条命令直接运行——理解「依赖合并」与清单的关系。
**要求**：

- 在 练习 2 的 pom 上加 maven-shade-plugin（版本 3.5.1），execution 挂到 `package` 阶段，ManifestResourceTransformer 的 `mainClass` 指向你的入口类
- 写一个 `CliTool`：接收文件路径参数，读文件，用 gson 输出 `{"file":..., "lines":..., "chars":...}`（行数用 `String.lines().count()`，与 `wc -l` 语义一致；`split("\n")` 对结尾换行会多算一行——这是真实踩过的坑）
- 不带参数时打印用法到 stderr 并以非零码退出（参数校验是 CLI 的基本功）

**验收**：`mvn clean package` 后 `target/` 同时有 fat jar 与 `original-*.jar`（薄 jar），两者体积差就是依赖体积；`printf 'line1\nline2\nline3\n' > demo.txt && java -jar target/<fat>.jar demo.txt` 输出 JSON 且 lines=3；不带参数运行退出码非 0 且 stderr 有用法提示。

## 练习 4：配置覆盖率（★★）

**目标**：挂上 JaCoCo 插件跑测试并读懂覆盖率报告的三类数字——理解「覆盖率 = 测到的 ÷ 全部」与插件绑定生命周期。
**要求**：

- 在 练习 1 的 pom 上加 junit 4.13.2（scope `test`）与 jacoco-maven-plugin 0.8.11（两个 execution：`prepare-agent` + `report` 挂到 `test` 阶段后）
- 写一个 `Calculator` 类（`add` / `divide` 两个方法）和一个 JUnit 4 测试类，**只测 `add` 不测 `divide`**
- 跑 `mvn clean test`，打开 `target/site/jacoco/index.html`，记下 Calculator 的指令/行/方法三类覆盖率

**验收**：`mvn test` 输出 `Tests run: 1`（参考实现实测数字）且报告生成；报告中 divide 相关方法未被覆盖（指令覆盖率 **63%（7/11）**、行 2/3、方法 2/3——参考实现的实测数字）；把 divide 补一个测试后三类数字全部变 100%，能解释为什么。

完成 4 题后再对照 sol-* 复盘。sol 文件头是验证块（环境/命令/实测数字），sol 内的 pom 在注释里——先自己想清楚 pom 该长什么样，再对注释。
