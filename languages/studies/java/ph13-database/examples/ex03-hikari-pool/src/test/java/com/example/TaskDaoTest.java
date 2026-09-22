package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** HikariCP 连接池实测：池化 CRUD、连接复用、并发下小池扛大流量 */
class TaskDaoTest {

    private static TaskDao dao;

    @BeforeAll
    static void init() throws SQLException {
        // 池上限 4 条物理连接
        dao = new TaskDao("jdbc:hsqldb:mem:pooldb", 4);
        dao.createTable();
    }

    @AfterAll
    static void tearDown() {
        dao.close();
    }

    @BeforeEach
    void clearTable() throws SQLException {
        dao.clear();   // 测试隔离：每个用例从空表开始（借的就是池里的连接）
    }

    @Test
    @DisplayName("池化 CRUD：借连接、操作、归还，调用方无感知")
    void pooledCrud_works() throws SQLException {
        long id = dao.insert("写 ph13 笔记");
        assertTrue(id > 0);
        assertEquals(1, dao.count());
    }

    @Test
    @DisplayName("串行借还 200 次，物理连接数始终不超过池上限（复用的直接证据）")
    void pool_reusesConnections() throws Exception {
        int before = dao.count();
        for (int i = 0; i < 200; i++) {
            dao.insert("task-" + i);
        }
        assertEquals(before + 200, dao.count());
        var mxStats = dao.poolStats();
        // total 不会超过 maximumPoolSize=4——200 次操作全靠复用这几条连接
        assertTrue(mxStats.startsWith("total="), "应能读出池状态");
        int total = Integer.parseInt(mxStats.substring("total=".length(), mxStats.indexOf(',')));
        assertTrue(total <= 4, "物理连接总数应 <= 池上限 4，实测 " + mxStats);
    }

    @Test
    @DisplayName("8 线程并发写 200 次：池上限 4 也能扛住，靠排队等连接")
    void concurrentWrites_withSmallPool() throws Exception {
        int before = dao.count();
        int threads = 8;
        int perThread = 25;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        try {
            List<Callable<Void>> jobs = new ArrayList<>();
            for (int t = 0; t < threads; t++) {
                int base = t * perThread;
                jobs.add(() -> {
                    for (int i = 0; i < perThread; i++) {
                        dao.insert("concurrent-" + (base + i));   // 池满时借连接会排队等待
                    }
                    return null;
                });
            }
            for (Future<Void> f : pool.invokeAll(jobs)) {
                f.get();   // 任何线程抛异常都在这里暴露
            }
        } finally {
            pool.shutdown();
        }
        assertEquals(before + threads * perThread, dao.count());
    }
}
