# ph11 阶段项目：Maven 多模块模板（文本统计 CLI）

## 需求

对应 Roadmap「ph11 Maven / Gradle 与工程化阶段」推荐项目第一个「**Maven 多模块模板**」：父 pom（`packaging=pom`）+ `common` + `app` 两个子模块，`dependencyManagement` 集中管理第三方版本，依赖方向单向（`app → common`），`mvn install` 后子模块可独立构建。推荐项目第二个「可执行 CLI jar」整合进 `app` 模块：`app` 打可执行 fat jar（shade），一条 `java -jar` 命令即可分发运行——两个推荐项目一次落地。

项目内容：一个**文本统计 CLI**——读入文本文件，输出行数/单词数/字符数的 JSON。`common` 模块提供纯 JDK 的统计工具（不依赖任何第三方），`app` 模块依赖 `common` + gson 完成序列化与参数校验，正好演示「业务依赖公共代码、第三方依赖只进业务层」的模块边界。

## 文件结构

```text
project/
├── build.sh                        # 构建脚本：mvn clean package + 运行演示（支持 offline 参数）
├── demo.txt                        # 演示输入文件（2 行, 3 个空白分隔词, 21 个字符）
├── pom.xml                         # 父 pom：聚合（modules）+ 继承（parent）+ dependencyManagement
├── common/
│   ├── pom.xml                     # 无外部依赖的公共模块
│   └── src/main/java/com/example/common/TextStats.java
└── app/
    ├── pom.xml                     # 依赖 common（${project.version}）+ gson（版本随父工程）; shade 打 fat jar
    └── src/main/java/com/example/app/AppMain.java
```

## 功能清单

- [ ] 父 pom 聚合两个子模块，根目录一次构建按依赖顺序产出全部模块（reactor 构建）
- [ ] `dependencyManagement` 集中声明 gson 版本，`app` 引用时不写 `<version>`，升版本只改父 pom 一处
- [ ] 依赖方向单向：`app → common`，`common` 不反向依赖任何业务代码（公共代码永远下沉）
- [ ] `common.TextStats` 提供 countLines/countWords/countChars 三个纯 JDK 工具方法（含空文本边界）
- [ ] `app.AppMain` 参数校验（无参数 → stderr 用法提示 + 退出码 2）、gson 输出 JSON
- [ ] shade 打可执行 fat jar（Main-Class 写入清单），`java -jar app/target/app-1.0-SNAPSHOT.jar <文件>` 直接运行
- [ ] 构建脚本 `./build.sh`（含 `offline` 离线模式）

## 验收标准

- `./build.sh` 构建成功，reactor 顺序为 `common → app`（子模块按依赖排序，公共模块先构建）
- `java -jar app/target/app-1.0-SNAPSHOT.jar demo.txt` 输出 `{"file":"demo.txt","lines":2,"words":3,"chars":21}`（本机实测输出）
- 空文件输入输出 `{"file":"empty.txt","lines":0,"words":0,"chars":0}`（边界正确）
- 无参数运行退出码为 2 且 stderr 有用法提示
- `mvn dependency:tree -pl app` 依赖树为 `app → common + gson` 两条边，方向单向
- `mvn install` 后 `app` 可脱离 reactor 单独构建（`mvn -pl app -am package` 亦可——本机实测 `-am` 方式 BUILD SUCCESS）

## 实测记录（本机 OpenJDK 17.0.18 + Maven 3.9.12）

- 构建：根目录 `mvn -o clean package` → BUILD SUCCESS；reactor `[1/3] text-stats → [2/3] common → [3/3] app`
- 产物（实测字节数）：

| 产物 | 大小 | 说明 |
|------|------|------|
| `common/target/common-1.0-SNAPSHOT.jar` | 2356 B | 公共模块薄 jar |
| `app/target/app-1.0-SNAPSHOT.jar` | 289012 B（≈282KB） | fat jar, 含 common + gson 的类 |
| `app/target/original-app-1.0-SNAPSHOT.jar` | 3210 B | shade 保留的薄 jar 副本 |

- 运行：`java -jar app/target/app-1.0-SNAPSHOT.jar demo.txt` → 实测 `{"file":"demo.txt","lines":2,"words":3,"chars":21}`；`empty.txt` → `{"file":"empty.txt","lines":0,"words":0,"chars":0}`
- 依赖树：`com.example:app:jar:1.0-SNAPSHOT` → `+- com.example:common:jar:1.0-SNAPSHOT:compile`、`\- com.google.code.gson:gson:jar:2.10.1:compile`
- `mvn install`：本环境沙箱禁止写默认本地仓库 `~/.m2`，实测时用 `-Dmaven.repo.local=/tmp/m2clone`（克隆的本地仓库）验证 install 成功——**正常环境直接 `mvn install` 即可**，效果是把 common/app 两个 jar 装进本地仓库供其他工程引用
- 本机 Maven 全程 `-o` 离线模式（依赖/插件来自本地仓库缓存）；联网环境执行 `./build.sh` 标准命令即从 Maven Central 拉取

## 扩展方向

- **子模块独立构建**：本工程 `mvn install` 后（或在 CI 里用 `mvn -pl app -am package`），`app` 可脱离 reactor 单独构建——把模板复制为 ph12 起的工程骨架，每阶段练习往 `modules` 里加新模块
- **可执行 CLI jar 分发**：把 `app` 的 fat jar 作为「可执行 CLI jar」分发给同事/服务器（`java -jar` 单命令），对照 4.6 可复现构建：固定依赖与插件版本、用 Wrapper（`mvnw`）固定 Maven 版本
- **质量门禁**：按 exercises 练习 4 的方式给 `common.TextStats` 挂 JaCoCo + JUnit，把覆盖率阈值写进 `verify` 阶段（`jacoco:check`）——衔接 ph12 单元测试与工程质量阶段（roadmap 第 12 节，目录待建）
- **CI 化**：GitHub Actions 里 `mvn -B clean verify` + 缓存 `~/.m2`——CI/CD 本身属于 ph19 DevOps 与部署阶段（roadmap 第 19 节，目录待建）

## 验证环境与命令

- 工具链：OpenJDK 17.0.18（Homebrew，`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version`）；jlink/jar/jdeps 为 JDK 自带
- 构建与运行：

```bash
# 1. 全量构建（reactor: common → app）
./build.sh                 # 或 ./build.sh offline（本机实测模式）
# 2. 运行 app（fat jar）
java -jar app/target/app-1.0-SNAPSHOT.jar demo.txt
# 3. 边界：空文件
: > empty.txt && java -jar app/target/app-1.0-SNAPSHOT.jar empty.txt && rm -f empty.txt
# 4. 查看依赖树
mvn dependency:tree -pl app
# 5. 清理产物
mvn clean
```

已在本环境用 OpenJDK 17.0.18 + Maven 3.9.12 编译运行验证（离线模式，产物数字见上表；构建产物 target/ 由 `mvn clean` 清理，`build.sh` 本身不入库产物）。
