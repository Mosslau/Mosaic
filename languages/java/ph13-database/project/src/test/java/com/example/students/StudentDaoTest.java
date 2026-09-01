package com.example.students;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * StudentDao 集成测试：HikariCP 连接池 + Flyway 迁移 + 真实 HSQLDB 引擎。
 * 顺序：先建池（常驻连接保住内存库）→ Flyway 迁移 V1/V2 → 业务测试。
 */
class StudentDaoTest {

    private static final String URL = "jdbc:hsqldb:mem:studentdb";

    private static StudentDao dao;

    @BeforeAll
    static void init() {
        dao = new StudentDao(URL, 4);            // 建池即建连：内存库由此存活
        Flyway flyway = Flyway.configure()
                .dataSource(URL, "sa", "")
                .locations("classpath:db/migration")
                .load();
        flyway.migrate();                         // V1 建表 + V2 建索引
    }

    @AfterAll
    static void tearDown() {
        dao.close();                              // 关池才真正断开，内存库随之销毁
    }

    @BeforeEach
    void clearTable() throws SQLException {
        try (Connection conn = dao.borrowConnection();
             Statement st = conn.createStatement()) {
            st.execute("DELETE FROM students");
        }
    }

    @Test
    @DisplayName("插入回填自增主键；findById 命中/未命中")
    void insertAndFindById() throws SQLException {
        long id = dao.insert("mosslau", "m@x.com", 5);
        assertTrue(id > 0, "主键应由数据库 IDENTITY 列生成");

        var found = dao.findById(id);
        assertTrue(found.isPresent());
        assertEquals(new Student(id, "mosslau", "m@x.com", 5), found.get());
        assertTrue(dao.findById(999L).isEmpty(), "不存在的主键应返回 Optional.empty");
    }

    @Test
    @DisplayName("findByEmail 命中；UNIQUE 约束拒绝重复邮箱")
    void findByEmailAndUniqueConstraint() throws SQLException {
        dao.insert("alice", "a@x.com", 3);

        assertTrue(dao.findByEmail("a@x.com").isPresent());
        assertTrue(dao.findByEmail("nobody@x.com").isEmpty());

        // 错误路径：email 列有 UNIQUE 约束，重复值必须被数据库拒绝
        assertThrows(SQLException.class, () -> dao.insert("alice2", "a@x.com", 3));
        assertEquals(1, dao.count(), "被拒绝的插入不能留下数据");
    }

    @Test
    @DisplayName("UPDATE/DELETE 返回受影响行数；0 行表示目标不存在")
    void updateAndDelete() throws SQLException {
        long id = dao.insert("bob", "b@x.com", 2);

        assertEquals(1, dao.updateGrade(id, 4));
        assertEquals(4, dao.findById(id).orElseThrow().grade());
        assertEquals(0, dao.updateGrade(999L, 1), "目标不存在时应影响 0 行");

        assertEquals(1, dao.delete(id));
        assertEquals(0, dao.delete(id), "重复删除应影响 0 行");
        assertEquals(0, dao.count());
    }

    @Test
    @DisplayName("串行借还 200 次，物理连接总数不超过池上限（复用的直接证据）")
    void poolReusesConnections() throws SQLException {
        for (int i = 0; i < 200; i++) {
            dao.insert("user" + i, "u" + i + "@x.com", 1);
        }
        assertEquals(200, dao.count());
        String stats = dao.poolStats();
        int total = Integer.parseInt(stats.substring("total=".length(), stats.indexOf(',')));
        assertTrue(total <= 4, "物理连接总数应 <= 池上限 4，实测 " + stats);
    }

    @Test
    @DisplayName("email 上的索引生效：执行计划不再全表扫描")
    void emailIndexIsUsedByPlanner() throws SQLException {
        dao.insert("carol", "c@x.com", 6);
        try (Connection conn = dao.borrowConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "EXPLAIN PLAN FOR SELECT * FROM students WHERE email = 'c@x.com'");
             ResultSet rs = ps.executeQuery()) {
            StringBuilder plan = new StringBuilder();
            while (rs.next()) {
                plan.append(rs.getString(1)).append('\n');
            }
            assertFalse(plan.toString().contains("access=FULL SCAN"),
                    "email 上有索引不应全表扫描，实测计划:\n" + plan);
            assertTrue(plan.toString().contains("access=INDEX PRED"),
                    "计划应走索引定位（INDEX PRED），实测计划:\n" + plan);
            // 教学点：email 列同时有 UNIQUE 约束（V1，隐含索引）与显式索引（V2），
            // 优化器选了约束的隐含索引（SYS_IDX_SYS_CT_...）——「见列就建索引」是浪费，
            // 正因为 UNIQUE/PRIMARY KEY 会自动建索引（对应主文档 3.4「索引影响查询和写入成本」）
        }
    }
}
