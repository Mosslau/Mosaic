package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.List;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** HSQLDB 内存库实测 JDBC CRUD：@BeforeEach 清表保证测试隔离 */
class UserDaoTest {

    private static Connection conn;
    private static UserDao dao;

    @BeforeAll
    static void openDb() throws SQLException {
        conn = DriverManager.getConnection("jdbc:hsqldb:mem:userdb", "sa", "");
        dao = new UserDao(conn);
        dao.createTable();
    }

    @AfterAll
    static void closeDb() throws SQLException {
        conn.close();   // 最后一个连接关闭，内存库随之销毁
    }

    @BeforeEach
    void clearTable() throws SQLException {
        try (var st = conn.createStatement()) {
            st.execute("DELETE FROM users");
        }
    }

    @Test
    @DisplayName("插入返回数据库生成的自增主键，且主键递增")
    void insert_returnsDatabaseGeneratedId() throws SQLException {
        long id1 = dao.insert("mosslau", "m@x.com");
        long id2 = dao.insert("alice", "a@x.com");

        assertTrue(id1 > 0, "主键应由数据库 IDENTITY 列生成");
        assertTrue(id2 > id1, "自增主键应递增");
    }

    @Test
    @DisplayName("findById 命中与未命中；findAll 按 id 有序返回")
    void find_byIdAndAll() throws SQLException {
        long id = dao.insert("mosslau", "m@x.com");
        dao.insert("alice", "a@x.com");

        var found = dao.findById(id);
        assertTrue(found.isPresent());
        assertEquals(new UserDao.User(id, "mosslau", "m@x.com"), found.get());

        assertTrue(dao.findById(999L).isEmpty(), "不存在的主键应返回 Optional.empty");

        List<UserDao.User> all = dao.findAll();
        assertEquals(2, all.size());
        assertEquals("mosslau", all.get(0).name());
    }

    @Test
    @DisplayName("UPDATE/DELETE 返回受影响行数；UNIQUE 约束让重复邮箱入库抛 SQLException")
    void update_delete_andUniqueConstraint() throws SQLException {
        long id = dao.insert("mosslau", "m@x.com");

        assertEquals(1, dao.updateEmail(id, "new@x.com"));
        assertEquals("new@x.com", dao.findById(id).orElseThrow().email());
        assertEquals(0, dao.updateEmail(999L, "x@x.com"), "目标不存在时应影响 0 行");

        // 错误路径：email 列有 UNIQUE 约束，重复值必须被数据库拒绝
        dao.insert("alice", "a@x.com");
        assertThrows(SQLException.class, () -> dao.insert("alice2", "a@x.com"));

        assertEquals(1, dao.delete(id));
        assertEquals(0, dao.delete(id), "重复删除应影响 0 行");
        assertEquals(1, dao.count());
    }

    @Test
    @DisplayName("PreparedStatement 把注入载荷当作纯数据存取，表安然无恙")
    void parameterization_treatsInjectionPayloadAsPlainData() throws SQLException {
        String payload = "x'); DROP TABLE users;--";

        dao.insert(payload, "evil@x.com");

        // 表没有被 DROP：载荷被当成普通字符串原样存进去了
        assertEquals(1, dao.count());
        assertEquals(payload, dao.findAll().get(0).name());
        dao.insert("still-works", "s@x.com");
        assertEquals(2, dao.count());
    }
}
