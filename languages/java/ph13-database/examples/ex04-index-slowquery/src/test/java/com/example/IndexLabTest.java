package com.example;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

/**
 * 索引效果实测（HSQLDB 2.5.0，20000 行）。
 * 注意：本类用例按 @Order 顺序共享同一张表（造数贵，只做一次）——
 * 这是「集成测试共享昂贵环境」的合理例外，与「单元测试零共享」不矛盾。
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class IndexLabTest {

    private static final int ROWS = 20_000;
    private static final int LOOKUPS = 100;

    private static Connection conn;
    private static IndexLab lab;

    @BeforeAll
    static void openDb() throws SQLException {
        conn = DriverManager.getConnection("jdbc:hsqldb:mem:indexdb", "sa", "");
        lab = new IndexLab(conn);
        lab.createTable();
        lab.seed(ROWS);
    }

    @AfterAll
    static void closeDb() throws SQLException {
        conn.close();
    }

    @Test
    @Order(1)
    @DisplayName("无索引：执行计划是 FULL SCAN（全表扫描）")
    void withoutIndex_planIsFullScan() throws SQLException {
        String plan = lab.planFor("SELECT * FROM users WHERE email = 'u19999@x.com'");
        assertTrue(plan.contains("access=FULL SCAN"),
                "无索引时应全表扫描，实测计划:\n" + plan);
    }

    @Test
    @Order(2)
    @DisplayName("建索引后：执行计划变为走索引（INDEX PRED），并出现索引名")
    void withIndex_planUsesIndex() throws SQLException {
        lab.createEmailIndex();
        String plan = lab.planFor("SELECT * FROM users WHERE email = 'u19999@x.com'");
        assertFalse(plan.contains("access=FULL SCAN"), "有索引后不应再全表扫描");
        assertTrue(plan.contains("IDX_USERS_EMAIL"),
                "计划里应出现索引名，实测计划:\n" + plan);
    }

    @Test
    @Order(3)
    @DisplayName("计时对比：同一等值查询 ×100，走索引显著快于全表扫描")
    void indexedLookup_isMeasurablyFaster() throws SQLException {
        // 先在有索引状态下计时，再 DROP 索引对比——两次同库同行数，公平
        long indexedMs = lab.timeEmailLookup("u19999@x.com", LOOKUPS);
        lab.dropEmailIndex();
        long noIndexMs = lab.timeEmailLookup("u19999@x.com", LOOKUPS);
        lab.createEmailIndex();   // 恢复现场

        System.out.printf("[IndexLab] %d 行 × %d 次等值查询: 无索引 %d ms, 有索引 %d ms%n",
                ROWS, LOOKUPS, noIndexMs, indexedMs);
        assertTrue(indexedMs < noIndexMs,
                "走索引应更快: 无索引 " + noIndexMs + " ms, 有索引 " + indexedMs + " ms");
    }
}
