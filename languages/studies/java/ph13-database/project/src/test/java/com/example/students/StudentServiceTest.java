package com.example.students;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * StudentService 事务测试：批量导入「同生同死」——任何一条失败整体回滚。
 * 回滚语义实测：先插入成功、中途重复邮箱触发 UNIQUE 约束 → rollback 撤销先前的插入，
 * 表中不留半批数据。
 */
class StudentServiceTest {

    private static final String URL = "jdbc:hsqldb:mem:studentdb";

    private static StudentDao dao;
    private static StudentService service;

    @BeforeAll
    static void init() {
        dao = new StudentDao(URL, 4);
        Flyway flyway = Flyway.configure()
                .dataSource(URL, "sa", "")
                .locations("classpath:db/migration")
                .load();
        flyway.migrate();
        service = new StudentService(dao);
    }

    @AfterAll
    static void tearDown() {
        dao.close();
    }

    @BeforeEach
    void clearTable() throws SQLException {
        try (Connection conn = dao.borrowConnection();
             Statement st = conn.createStatement()) {
            st.execute("DELETE FROM students");
        }
    }

    @Test
    @DisplayName("批量导入成功：整批入库，返回导入条数")
    void importAll_success() throws SQLException {
        int imported = service.importStudents(List.of(
                new StudentService.StudentInput("a1", "a1@x.com", 1),
                new StudentService.StudentInput("a2", "a2@x.com", 2),
                new StudentService.StudentInput("a3", "a3@x.com", 3)));

        assertEquals(3, imported);
        assertEquals(3, dao.count());
    }

    @Test
    @DisplayName("重复邮箱触发 UNIQUE 约束：整批回滚，表中不留半批数据（原子性实测）")
    void importWithDuplicateEmail_rollsBackWholeBatch() throws SQLException {
        // 先占住 a1@x.com 的邮箱
        dao.insert("existing", "a1@x.com", 1);

        // 批次里第 2 条重复邮箱 → 第 1 条已插入成功，必须整体回滚
        assertThrows(SQLException.class, () -> service.importStudents(List.of(
                new StudentService.StudentInput("b1", "b1@x.com", 2),
                new StudentService.StudentInput("b2", "a1@x.com", 2),
                new StudentService.StudentInput("b3", "b3@x.com", 2))));

        assertEquals(1, dao.count(), "回滚后只应有预先插入的那条，批次数据一条不留");
        assertTrue(dao.findByEmail("b1@x.com").isEmpty(), "第 1 条插入已执行但被回滚");
    }

    @Test
    @DisplayName("业务校验失败（非法数据）：快速失败，不做任何写库")
    void importWithInvalidInput_rejectsBeforeWriting() throws SQLException {
        assertThrows(IllegalArgumentException.class, () -> service.importStudents(List.of(
                new StudentService.StudentInput("good", "good@x.com", 1),
                new StudentService.StudentInput("  ", "bad@x.com", 1))));

        // 校验先于事务：非法输入不触发任何 SQL，表保持为空
        assertEquals(0, dao.count());
    }

    @Test
    @DisplayName("单条注册：合法输入落库返回自增主键，年级越界被拒绝")
    void register_validatesAndPersists() throws SQLException {
        long id = service.register("carol", "carol@x.com", 6);
        assertTrue(id > 0);
        assertEquals("carol", dao.findById(id).orElseThrow().name());

        assertThrows(IllegalArgumentException.class,
                () -> service.register("dave", "d@x.com", 7), "年级 7 超出 1~6 范围");
        assertThrows(IllegalArgumentException.class,
                () -> service.register("eve", "not-an-email", 1));
    }
}
