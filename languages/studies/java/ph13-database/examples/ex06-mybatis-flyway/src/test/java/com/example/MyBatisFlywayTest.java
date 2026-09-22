package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.InputStream;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import org.apache.ibatis.io.Resources;
import org.apache.ibatis.session.SqlSession;
import org.apache.ibatis.session.SqlSessionFactory;
import org.apache.ibatis.session.SqlSessionFactoryBuilder;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

/**
 * Flyway 迁移 + MyBatis 映射 联调实测（HSQLDB 内存库）。
 * keeper 连接的作用：HSQLDB mem 库在「最后一条连接关闭」时销毁，
 * 测试期间持有一条常驻连接，保证 Flyway 与 MyBatis 各自的连接都连到同一个库。
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class MyBatisFlywayTest {

    private static final String URL = "jdbc:hsqldb:mem:mybatisdb";

    private static Connection keeper;
    private static SqlSessionFactory sessionFactory;

    @BeforeAll
    static void init() throws Exception {
        keeper = DriverManager.getConnection(URL, "sa", "");   // 常驻连接保住内存库

        // 1. Flyway 先迁移：V1 建表、V2 加索引（幂等——已执行的版本会跳过）
        Flyway flyway = Flyway.configure()
                .dataSource(URL, "sa", "")
                .locations("classpath:db/migration")
                .load();
        flyway.migrate();

        // 2. MyBatis 接管数据访问
        try (InputStream in = Resources.getResourceAsStream("mybatis-config.xml")) {
            sessionFactory = new SqlSessionFactoryBuilder().build(in);
        }
    }

    @AfterAll
    static void tearDown() throws SQLException {
        keeper.close();
    }

    @Test
    @Order(1)
    @DisplayName("Flyway 迁移后：flyway_schema_history 记录 V1/V2 两个版本")
    void flywayMigrate_recordsHistory() throws SQLException {
        try (PreparedStatement ps = keeper.prepareStatement(
                // Flyway 用引号建表，HSQLDB 中引号标识符区分大小写——查询必须带引号
                "SELECT \"version\", \"description\", \"success\" FROM \"flyway_schema_history\" ORDER BY \"installed_rank\"");
             ResultSet rs = ps.executeQuery()) {
            assertTrue(rs.next());
            assertEquals("1", rs.getString("version"));
            assertEquals("create users", rs.getString("description"));
            assertTrue(rs.getBoolean("success"));
            assertTrue(rs.next());
            assertEquals("2", rs.getString("version"));
            assertEquals("add email index", rs.getString("description"));
        }
    }

    @Test
    @Order(2)
    @DisplayName("MyBatis：insert 回填自增主键，findById/findAll 映射成 User 对象")
    void mapper_insertAndFind() {
        try (SqlSession session = sessionFactory.openSession()) {
            UserMapper mapper = session.getMapper(UserMapper.class);

            User u = new User("mosslau", "m@x.com");
            mapper.insert(u);
            session.commit();   // JDBC 事务管理器下，写操作要显式提交

            assertNotNull(u.getId(), "useGeneratedKeys 应把自增主键回填进实体");

            User found = mapper.findById(u.getId());
            assertEquals("mosslau", found.getName());
            assertEquals("m@x.com", found.getEmail());

            mapper.insert(new User("alice", "a@x.com"));
            session.commit();
            assertEquals(2, mapper.findAll().size());
        }
    }

    @Test
    @Order(3)
    @DisplayName("MyBatis：update/delete 返回受影响行数，删除后 findById 为 null")
    void mapper_updateAndDelete() {
        try (SqlSession session = sessionFactory.openSession()) {
            UserMapper mapper = session.getMapper(UserMapper.class);

            User u = new User("bob", "b@x.com");
            mapper.insert(u);
            session.commit();

            assertEquals(1, mapper.updateEmail(u.getId(), "b2@x.com"));
            assertEquals("b2@x.com", mapper.findById(u.getId()).getEmail());

            assertEquals(1, mapper.delete(u.getId()));
            session.commit();
            assertNull(mapper.findById(u.getId()));
            assertEquals(0, mapper.delete(999L));
        }
    }
}
