// exercises/sol-03-connection-pool.java —— 练习 3 参考实现：HikariCP 连接池（HSQLDB 内存库）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + HSQLDB 2.5.0 + HikariCP 5.0.1（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol03-connection-pool</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>com.zaxxer</groupId>
//         <artifactId>HikariCP</artifactId>
//         <version>5.0.1</version>
//       </dependency>
//       <!-- 离线版本仲裁：HikariCP 5.0.1 声明 slf4j-api 2.0.0-alpha1，本机缓存无该版本，
//            用缓存内的 2.0.9 压过（机制见 ph11 主文档依赖仲裁）。正常联网环境可删除本项 -->
//       <dependency>
//         <groupId>org.slf4j</groupId>
//         <artifactId>slf4j-api</artifactId>
//         <version>2.0.9</version>
//       </dependency>
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
// 本文件内容放 src/main/java/com/example/PooledTaskDao.java
//
// 测试类（src/test/java/com/example/PooledTaskDaoTest.java）:
//
//   package com.example;
//   import static org.junit.jupiter.api.Assertions.*;
//   import java.sql.SQLException;
//   import java.util.ArrayList;
//   import java.util.List;
//   import java.util.concurrent.*;
//   import org.junit.jupiter.api.*;
//
//   class PooledTaskDaoTest {
//       private static PooledTaskDao dao;
//
//       @BeforeAll static void init() throws SQLException {
//           dao = new PooledTaskDao("jdbc:hsqldb:mem:sol03db", 4);
//           dao.createTable();
//       }
//       @AfterAll static void tearDown() { dao.close(); }
//       @BeforeEach void clearTable() throws SQLException { dao.clear(); }
//
//       @Test void pooledCrud_works() throws SQLException {
//           long id = dao.insert("写 ph13 练习");
//           assertTrue(id > 0);
//           assertEquals(1, dao.count());
//       }
//       @Test void pool_reusesConnections() throws Exception {
//           for (int i = 0; i < 200; i++) { dao.insert("task-" + i); }
//           assertEquals(200, dao.count());
//           String stats = dao.poolStats();
//           int total = Integer.parseInt(stats.substring("total=".length(), stats.indexOf(',')));
//           assertTrue(total <= 4, "物理连接总数应 <= 池上限 4，实测 " + stats);
//       }
//       @Test void concurrentWrites_withSmallPool() throws Exception {
//           int threads = 8, perThread = 25;
//           ExecutorService pool = Executors.newFixedThreadPool(threads);
//           try {
//               List<Callable<Void>> jobs = new ArrayList<>();
//               for (int t = 0; t < threads; t++) {
//                   final int base = t * perThread;
//                   jobs.add(() -> { for (int i = 0; i < perThread; i++) dao.insert("c-" + (base + i)); return null; });
//               }
//               for (Future<Void> f : pool.invokeAll(jobs)) { f.get(); }
//           } finally { pool.shutdown(); }
//           assertEquals(threads * perThread, dao.count());
//       }
//   }
//
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - 建池即建连：maximumPoolSize 决定同时最多几条物理连接；close() 关池才真正断开全部连接
//   - try-with-resources 关闭连接 = 归还池里（不是真断开）——池心智的核心
//   - 串行 200 次借还物理连接数 ≤ 4：复用的直接证据
//   - 8 线程并发写、池上限 4 全部成功：池满时借连接排队等待（connectionTimeout 内）
//   - 连接是昂贵的（TCP+认证+会话初始化），池化把建连成本摊到启动期
// ---------------------------------------------------------------------------

package com.example;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/** 练习 3 参考实现：基于 HikariCP 的任务表访问 */
public class PooledTaskDao implements AutoCloseable {

    private final HikariDataSource dataSource;

    public PooledTaskDao(String jdbcUrl, int maxPoolSize) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername("sa");
        config.setPassword("");
        config.setMaximumPoolSize(maxPoolSize);
        this.dataSource = new HikariDataSource(config);
    }

    public void createTable() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE tasks ("
                    + "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
                    + "title VARCHAR(128) NOT NULL)");
        }
    }

    public long insert(String title) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO tasks(title) VALUES (?)", Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, title);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    public int count() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement("SELECT COUNT(*) FROM tasks");
             ResultSet rs = ps.executeQuery()) {
            rs.next();
            return rs.getInt(1);
        }
    }

    public void clear() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement()) {
            st.execute("DELETE FROM tasks");
        }
    }

    /** 池的实时状态（供教学观察）：当前物理连接总数 / 活跃 / 空闲 */
    public String poolStats() {
        var mx = dataSource.getHikariPoolMXBean();
        return "total=" + mx.getTotalConnections()
                + ", active=" + mx.getActiveConnections()
                + ", idle=" + mx.getIdleConnections();
    }

    @Override
    public void close() {
        dataSource.close();
    }
}
