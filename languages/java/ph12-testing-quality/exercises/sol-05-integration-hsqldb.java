// exercises/sol-05-integration-hsqldb.java —— 练习 5 参考实现：HSQLDB 内存库集成测试
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + HSQLDB 2.5.0（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 内存库 vs Testcontainers（练习要求写在文件头的对比）:
//   - HSQLDB 内存库：纯 Java、零 Docker、秒级启动，适合「验证代码 + SQL 能协作」的基础集成测试；
//     缺点是与生产 MySQL/PostgreSQL 行为不完全一致（索引策略、专有语法、事务隔离、时区）
//   - Testcontainers：Docker 起真实 MySQL/Postgres 容器，行为与生产一致，适合验证数据库专有行为；
//     缺点是要 Docker 守护进程、首次拉镜像慢（用法见 examples/ex07-testcontainers.md，本沙箱无 Docker 未实跑）
//   - 工程里通常「单元测试用 mock/fake + 集成测试用内存库/Testcontainers」分层，各司其职
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol05-integration-hsqldb</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>org.junit.jupiter</groupId>
//         <artifactId>junit-jupiter</artifactId>
//         <version>5.10.1</version>
//         <scope>test</scope>
//       </dependency>
//       <!-- HSQLDB 纯 Java 内存库：作为 JDBC 驱动跑在测试 JVM 里，无需 Docker -->
//       <dependency>
//         <groupId>org.hsqldb</groupId>
//         <artifactId>hsqldb</artifactId>
//         <version>2.5.0</version>
//         <scope>test</scope>
//       </dependency>
//     </dependencies>
//     <build>
//       <plugins>
//         <plugin>
//           <groupId>org.apache.maven.plugins</groupId>
//           <artifactId>maven-surefire-plugin</artifactId>
//           <version>3.2.5</version>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 业务接口（src/main/java/com/example/，User.java / UserRepository.java 同练习 2）:
//   UserRepository —— interface { Optional<User> findById(long); boolean existsByEmail(String); void save(User); }
//   本文件内容放 src/main/java/com/example/JdbcUserRepository.java
//
// 测试类（src/test/java/com/example/JdbcUserRepositoryTest.java）:
//
//   package com.example;
//   import org.junit.jupiter.api.AfterAll;
//   import org.junit.jupiter.api.BeforeAll;
//   import org.junit.jupiter.api.BeforeEach;
//   import org.junit.jupiter.api.Test;
//   import java.sql.Connection;
//   import java.sql.DriverManager;
//   import java.sql.Statement;
//   import java.util.Optional;
//   import static org.junit.jupiter.api.Assertions.assertEquals;
//   import static org.junit.jupiter.api.Assertions.assertFalse;
//   import static org.junit.jupiter.api.Assertions.assertThrows;
//   import static org.junit.jupiter.api.Assertions.assertTrue;
//
//   /** 集成测试：真实 JDBC 代码 + HSQLDB 内存库（纯 Java，无需 Docker）。 */
//   class JdbcUserRepositoryTest {
//       private static Connection conn;
//       private JdbcUserRepository repo;
//
//       @BeforeAll static void openDb() throws Exception {
//           // mem: 内存库；HSQLDB 通过 JDBC 服务发现自动注册驱动
//           conn = DriverManager.getConnection("jdbc:hsqldb:mem:userdb", "sa", "");
//           try (Statement st = conn.createStatement()) {
//               st.execute("CREATE TABLE users (id BIGINT PRIMARY KEY, name VARCHAR(64), email VARCHAR(128) UNIQUE)");
//           }
//       }
//       @AfterAll static void closeDb() throws Exception { conn.close(); }
//
//       @BeforeEach void setUp() throws Exception {
//           try (Statement st = conn.createStatement()) { st.execute("DELETE FROM users"); }
//           repo = new JdbcUserRepository(conn);
//       }
//
//       @Test void save_thenFindById_roundTrips() {
//           repo.save(new User(1L, "mosslau", "m@x.com"));
//           Optional<User> found = repo.findById(1L);
//           assertTrue(found.isPresent());
//           assertEquals("mosslau", found.get().name());
//           assertEquals("m@x.com", found.get().email());
//       }
//       @Test void findById_missing_returnsEmpty() {
//           assertFalse(repo.findById(99L).isPresent());
//       }
//       @Test void existsByEmail_trueAfterSave() {
//           repo.save(new User(2L, "bob", "bob@x.com"));
//           assertTrue(repo.existsByEmail("bob@x.com"));
//           assertFalse(repo.existsByEmail("nobody@x.com"));
//       }
//       @Test void save_duplicateEmail_violatesUniqueConstraint() {
//           repo.save(new User(3L, "a", "same@x.com"));
//           RuntimeException ex = assertThrows(RuntimeException.class,
//                   () -> repo.save(new User(4L, "b", "same@x.com")));
//           assertTrue(ex.getCause() instanceof java.sql.SQLException, "UNIQUE 约束应产生 SQLException");
//       }
//   }
//
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - 类名不用 *IT 后缀：surefire 默认只跑 *Test/*Tests/*TestCase，*IT 是 failsafe（ph11 构建工具）的约定
//   - @BeforeAll 建连接建表、@AfterAll 关连接（内存库随连接关闭销毁）、@BeforeEach 清表 —— 测试间互不污染
//   - 数据库 UNIQUE 约束的错误路径也要测：SQLException 被包装成 RuntimeException 抛给上层
//   - JDBC/SQL 细节属于 ph13 数据库阶段，这里只借「连真实引擎跑 SQL」演示集成测试怎么写
// ---------------------------------------------------------------------------
package com.example;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Optional;

/** JDBC 实现：真实 SQL 与数据库引擎协作（集成测试的对象）。JDBC 细节属于 ph13 数据库阶段，这里只演示「怎么测」。 */
public class JdbcUserRepository implements UserRepository {

    private final Connection conn;

    public JdbcUserRepository(Connection conn) {
        this.conn = conn;
    }

    @Override
    public Optional<User> findById(long id) {
        String sql = "SELECT id, name, email FROM users WHERE id = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return Optional.of(new User(rs.getLong(1), rs.getString(2), rs.getString(3)));
                }
                return Optional.empty();
            }
        } catch (SQLException e) {
            throw new RuntimeException("查询用户失败 id=" + id, e);
        }
    }

    @Override
    public boolean existsByEmail(String email) {
        String sql = "SELECT 1 FROM users WHERE email = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, email);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        } catch (SQLException e) {
            throw new RuntimeException("查询邮箱失败: " + email, e);
        }
    }

    @Override
    public void save(User user) {
        String sql = "INSERT INTO users (id, name, email) VALUES (?, ?, ?)";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, user.id());
            ps.setString(2, user.name());
            ps.setString(3, user.email());
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException("保存用户失败: " + user, e);
        }
    }
}
