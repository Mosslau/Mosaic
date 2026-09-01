# ph12 阶段项目：带测试的用户服务

> 对应 Roadmap「ph12 单元测试与工程质量阶段」推荐项目之「带测试的用户服务」；「Testcontainers 示例」以 examples/ex07-testcontainers.md 概念文档 + 本项目 HSQLDB 集成测试（内存库替代路线）落地，Testcontainers 真容器版本因本沙箱无 Docker 未实跑。

## 需求

实现一个用户服务：注册（姓名/邮箱校验 + 邮箱查重 + 落库并分配 id）、按 id 查询、改邮箱、删除。核心是**用本阶段学的全部测试手段把它测到可信**——单元测试（Mockito 隔离存储）、参数化测试（校验规则事实表）、集成测试（HSQLDB 真实 JDBC 引擎）、覆盖率报告（JaCoCo）。

工程结构（标准 Maven 布局，纯 Java SE，无框架依赖）：

```text
src/main/java/com/example/users/
├── User.java                   # record：不可变用户实体
├── UserRepository.java         # 存储抽象接口（依赖倒置，替身能插进来的前提）
├── InMemoryUserRepository.java # 内存实现：原型/开发用，测试里天然是 fake
├── JdbcUserRepository.java     # JDBC 实现：真实 SQL 与数据库引擎协作（集成测试对象）
└── UserService.java            # 业务：校验 + 编排，不含任何外部调用本身
src/test/java/com/example/users/
├── UserServiceTest.java        # Mockito 单元测试：隔离存储，测编排与交互
├── UserValidationTest.java     # 参数化测试：校验规则「事实表」
├── InMemoryUserRepositoryTest.java # 内存仓库自身行为测试
└── JdbcUserRepositoryTest.java # HSQLDB 集成测试：真实 JDBC + 内存库
```

## 功能清单

- [x] 注册：姓名非空、邮箱格式合法（正则）、邮箱去重、首尾空白规范化、落库返回带分配 id 的用户
- [x] 查询：`findById` 存在返回、不存在抛 `IllegalArgumentException`
- [x] 改邮箱：新邮箱合法 + 未被占用（邮箱未变时短路跳过查重）、保留原 id 与姓名
- [x] 删除：返回是否删除成功
- [x] 两种存储实现可互换（接口驱动），集成测试连 HSQLDB 内存库验证真实 SQL

## 验收标准

- `mvn test` 全部通过：**Tests run: 39**（实测：UserServiceTest 8 + UserValidationTest 19 + InMemoryUserRepositoryTest 6 + JdbcUserRepositoryTest 6），Failures 0 / Errors 0
- JaCoCo 报告生成（`target/site/jacoco/index.html`），实测（主类，jacoco.csv/jacoco.xml）：

| 覆盖率类型 | 实测 | 说明 |
|-----------|------|------|
| 指令 INSTRUCTION | **92%**（368/397） | 测到的字节码指令 ÷ 全部 |
| 行 LINE | **92%**（73/79） | 测到的源码行 ÷ 全部 |
| 方法 METHOD | **100%**（21/21） | 全部方法都至少执行过 |
| 分支 BRANCH | **83%**（25/30） | 条件分支，缺口在错误路径 |
| 类 CLASS | **100%**（4/4） | — |

- 未覆盖分支已定位并理解：`UserService` 的 2 个未覆盖分支——`validateEmail` 的「email 为 null」短路分支（参数化列表里没放 null）、`updateEmail` 的「邮箱未变时短路跳过查重」分支（只测了换邮箱的路径；`findById` 无分支）；`JdbcUserRepository` 的 `SQLException → RuntimeException` 异常包装分支（集成测试只走了正常路径，没模拟数据库故障）——**这正说明「覆盖率 92% 不等于测全了错误路径」**，是「覆盖率不是唯一质量指标」的活例

## 验证环境与命令

- 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + Mockito 5.11.0 + AssertJ 3.25.3 + HSQLDB 2.5.0 + JaCoCo 0.8.11
- 本机实测（沙箱特例）：`mvn -o -Dmaven.repo.local=/tmp/m2clone clean test`（离线模式，依赖取自本地仓库缓存；沙箱禁止写 `~/.m2`）
- **正常联网环境**：`mvn clean test` 即可；打开报告：`open target/site/jacoco/index.html`
- 说明：pom 中「离线版本仲裁」注释标记的三项依赖（byte-buddy/objenesis）仅为本机离线缓存所需，正常联网环境可删除，让 Mockito/AssertJ 自行拉取声明版本

## 测试设计要点（本项目的教学增量）

- **单元测试只测业务层**：`UserServiceTest` 用 Mockito 把 `UserRepository` 完全隔离，验证的是「编排逻辑 + 交互」（stub 返回值、`verify` 交互、`never()` 验证没有发生），不碰数据库
- **参数化测试把校验规则写成表**：`UserValidationTest` 一行一组「输入 + 预期」，加规则只加一行；`@NullSource` 补上普通 `@ValueSource` 传不了的 null（这也是覆盖率报告里 validateEmail 缺的那个分支）
- **集成测试用内存库替代真容器**：`JdbcUserRepositoryTest` 连 HSQLDB 内存库（纯 Java、秒级启动），验证「代码 + SQL 与真实引擎协作」；需要验证生产 MySQL/PostgreSQL 专有行为时再上 Testcontainers（examples/ex07）
- **每个测试一个行为**：测试方法名 `register_rejectsDuplicateEmail_withoutSaving` 读起来像句子；断言用 AssertJ（`assertThatThrownBy(...).isInstanceOf(...).hasMessageContaining(...)`），失败信息可读

## 扩展方向（可选）

- 接 Testcontainers 跑 MySQL：把 `JdbcUserRepositoryTest` 换成 `MySQLContainer` 版（见 examples/ex07-testcontainers.md），对比内存库与真容器的行为差异
- 给 `JdbcUserRepository` 补「数据库故障」测试：用一个已经 close 的 `Connection` 构造仓库，验证 SQLException 被包装成 RuntimeException 的路径——把分支覆盖率从 83% 抬上去
- 引入 JaCoCo `check` 门槛：配置 `<rule>` 让覆盖率低于阈值时构建失败（质量门禁，见 ph11 3.8），接入 CI（ph19 DevOps 与部署阶段）
- 加更多业务：用户密码/状态字段、分页查询——每个新功能配同类测试，保持「测试与代码同步演进」
- JDBC 细节（连接池、事务、索引、ORM）属于 **ph13 数据库阶段**（roadmap 第 13 节，目录待建），本项目的 JDBC 只写最小可测 CRUD
