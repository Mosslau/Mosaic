// exercises/sol-01-user-crud.java —— 练习 1 参考实现：用户表 CRUD（HSQLDB 内存库）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + HSQLDB 2.5.0（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol01-user-crud</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>org.hsqldb</groupId>
//         <artifactId>hsqldb</artifactId>
//         <version>2.5.0</version>
//       </dependency>
//       <dependency>
//         <groupId>org.junit.jupiter</groupId>
//         <artifactId>junit-jupiter</artifactId>
//         <version>5.10.1</version>
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
// 本文件内容放 src/main/java/com/example/CrudUserDao.java
//
// 测试类（src/test/java/com/example/CrudUserDaoTest.java）:
//
//   package com.example;
//   import static org.junit.jupiter.api.Assertions.*;
//   import java.sql.Connection;
//   import java.sql.DriverManager;
//   import org.junit.jupiter.api.*;
//
//   class CrudUserDaoTest {
//       private static Connection conn;
//       private static CrudUserDao dao;
//
//       @BeforeAll static void openDb() throws Exception {
//           conn = DriverManager.getConnection("jdbc:hsqldb:mem:sol01db", "sa", "");
//           dao = new CrudUserDao(conn);
//           dao.createTable();
//       }
//       @AfterAll static void closeDb() throws Exception { conn.close(); }
//       @BeforeEach void clear() throws Exception {
//           try (var st = conn.createStatement()) { st.execute("DELETE FROM users"); }
//       }
//
//       @Test void save_blankName_rejected() throws Exception {
//           assertThrows(IllegalArgumentException.class, () -> dao.save("  ", "a@x.com"));
//           assertThrows(IllegalArgumentException.class, () -> dao.save(null, "a@x.com"));
//           assertEquals(0, dao.count());
//       }
//       @Test void save_assignsId_findById_roundTrips() throws Exception {
//           long id = dao.save("mosslau", "m@x.com");
//           assertTrue(id > 0);
//           var found = dao.findById(id);
//           assertTrue(found.isPresent());
//           assertEquals("m@x.com", found.get().email());
//       }
//       @Test void findByEmail_hitAndMiss() throws Exception {
//           dao.save("alice", "a@x.com");
//           assertTrue(dao.findByEmail("a@x.com").isPresent());
//           assertTrue(dao.findByEmail("nobody@x.com").isEmpty());
//       }
//       @Test void save_duplicateEmail_rejectedByUniqueConstraint() throws Exception {
//           dao.save("a", "same@x.com");
//           assertThrows(java.sql.SQLException.class, () -> dao.save("b", "same@x.com"));
//           assertEquals(1, dao.count(), "被拒绝的插入不能留下数据");
//       }
//       @Test void updateAndDelete_returnAffectedRows() throws Exception {
//           long id = dao.save("bob", "b@x.com");
//           assertEquals(1, dao.updateName(id, "bobby"));
//           assertEquals("bobby", dao.findById(id).orElseThrow().name());
//           assertEquals(0, dao.updateName(999L, "x"));
//           assertEquals(1, dao.delete(id));
//           assertEquals(0, dao.delete(id));
//       }
//   }
//
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - 业务校验（名字非空）在 Java 层快速失败；数据完整性（邮箱唯一）由数据库 UNIQUE 约束兜底——两层各有分工
//   - 全部走 PreparedStatement：@BeforeEach 清表才用普通 Statement（无参数、无注入面）
//   - UPDATE/DELETE 的返回值是「受影响行数」，0 行就是「目标不存在」，不用先 SELECT 判断
// ---------------------------------------------------------------------------

package com.example;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Optional;

/** 练习 1 参考实现：用户表 CRUD + Java 层业务校验 + 数据库层唯一约束 */
public class CrudUserDao {

    public record User(long id, String name, String email) {}

    private final Connection conn;

    public CrudUserDao(Connection conn) {
        this.conn = conn;
    }

    public void createTable() throws SQLException {
        try (Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE users ("
                    + "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
                    + "name VARCHAR(64) NOT NULL, "
                    + "email VARCHAR(128) NOT NULL UNIQUE)");
        }
    }

    public long save(String name, String email) throws SQLException {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("姓名不能为空");   // Java 层快速失败
        }
        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO users(name, email) VALUES (?, ?)", Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, name.trim());
            ps.setString(2, email);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    public Optional<User> findById(long id) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "SELECT id, name, email FROM users WHERE id = ?")) {
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next()
                        ? Optional.of(map(rs))
                        : Optional.empty();
            }
        }
    }

    public Optional<User> findByEmail(String email) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "SELECT id, name, email FROM users WHERE email = ?")) {
            ps.setString(1, email);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next()
                        ? Optional.of(map(rs))
                        : Optional.empty();
            }
        }
    }

    public int updateName(long id, String newName) throws SQLException {
        if (newName == null || newName.isBlank()) {
            throw new IllegalArgumentException("姓名不能为空");
        }
        try (PreparedStatement ps = conn.prepareStatement("UPDATE users SET name = ? WHERE id = ?")) {
            ps.setString(1, newName.trim());
            ps.setLong(2, id);
            return ps.executeUpdate();
        }
    }

    public int delete(long id) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement("DELETE FROM users WHERE id = ?")) {
            ps.setLong(1, id);
            return ps.executeUpdate();
        }
    }

    public int count() throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement("SELECT COUNT(*) FROM users");
             ResultSet rs = ps.executeQuery()) {
            rs.next();
            return rs.getInt(1);
        }
    }

    private static User map(ResultSet rs) throws SQLException {
        return new User(rs.getLong("id"), rs.getString("name"), rs.getString("email"));
    }
}
