# ex07 Testcontainers：真实容器化依赖（概念讲解，未在本环境验证）

> 本示例是**概念文档**，不是可运行工程 —— 运行前提是 Docker 守护进程。
> 验证状态：**未在本环境验证**（沙箱无 Docker 守护进程：`/var/run/docker.sock` 不存在；依赖 jar 在本地缓存中可解析，但运行需要 Docker，故不实跑）。
> 代码片段为 Testcontainers 1.19.x + JUnit 5 的标准用法，可放心照抄进联网 + 有 Docker 的环境。

## 要解决的问题

单元测试用 mock / 内存库隔离数据库，但**内存库与生产 MySQL/PostgreSQL 的行为并不一致**（索引策略、事务隔离级别、专有 SQL 语法、时区处理都有差异）。「集成测试验证真实组件协作」要求测试环境与生产环境足够接近 —— Testcontainers 的思路是：**测试时用 Docker 启动一个真实的 MySQL/PostgreSQL/Redis 容器，测完自动销毁**。

```text
测试开始 ──▶ 拉镜像并启动容器（随机端口）──▶ 等待就绪（wait strategy）
   ──▶ 测试代码连真实数据库执行 ──▶ 测试结束 ──▶ 自动 stop 并清理容器
```

## pom 依赖（Testcontainers 1.19.1 + JUnit 5 + MySQL）

```xml
<dependencies>
  <dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>5.10.1</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers</artifactId>
    <version>1.19.1</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>1.19.1</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>mysql</artifactId>
    <version>1.19.1</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>com.mysql</groupId>
    <artifactId>mysql-connector-j</artifactId>
    <version>8.3.0</version>
    <scope>test</scope>
  </dependency>
</dependencies>
```

## 标准用法（JUnit 5 扩展）

```java
package com.example;

import org.junit.jupiter.api.Test;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;

@Testcontainers                        // JUnit 5 扩展：管理容器生命周期
class MySqlContainerTest {

    // 启动一个真实的 MySQL 8 容器；随机端口避免与本机 MySQL 冲突
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.0")
                    .withDatabaseName("testdb")
                    .withUsername("test")
                    .withPassword("test");

    @Test
    void realMySqlIsUsable() throws Exception {
        // MYSQL.getJdbcUrl() 形如 jdbc:mysql://localhost:32768/testdb
        try (Connection conn = DriverManager.getConnection(
                MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
             Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE t (id INT PRIMARY KEY, v VARCHAR(16))");
            st.execute("INSERT INTO t VALUES (1, 'hello')");
            try (var rs = st.executeQuery("SELECT v FROM t WHERE id = 1")) {
                rs.next();
                System.out.println("读到真实 MySQL 的值: " + rs.getString(1));
            }
        }
    }
}
```

关键点：

- **`@Testcontainers` + `@Container`**：JUnit 5 扩展在测试前后自动 start/stop 容器（start 在第一个测试前，stop 在所有测试后）
- **随机端口**：容器端口映射到宿主机随机端口（如上例 `32768`），避免 CI 并行跑测试时的端口冲突
- **连接信息由容器对象提供**：`getJdbcUrl()` / `getUsername()` / `getPassword()`，不硬编码端口
- **等待策略**：`waitStrategy` 等容器内服务真正就绪再连（MySQL 默认等 TCP 端口 + 日志关键字），避免「容器起了但数据库还没就绪」
- 容器镜像需要在能访问 Docker Hub 的环境首次拉取；CI 里配 Testcontainers Cloud 或私有镜像仓库可加速

## 与本阶段的关系

- 集成测试的**替代路线**（本项目实测采用）：HSQLDB 内存库（见 [`project/`](../project/) 的 JdbcUserRepository 集成测试）——纯 Java、零 Docker、启动快，适合验证「代码与 SQL 能协作」；差异是它与生产 MySQL 的行为不完全一致
- 需要验证**数据库专有行为**（如 MySQL 的 `ON DUPLICATE KEY UPDATE`、JSON 类型、事务隔离）时，才值得上 Testcontainers
- 完整数据库编程（JDBC 细节、连接池、事务、索引）属于 **ph13 数据库阶段**（roadmap 第 13 节，目录待建），这里只借「连上真实库跑 SQL」这一件事演示集成测试
