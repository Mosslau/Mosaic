package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** 事务转账实测：成功提交、业务失败回滚、中途故障回滚三种路径全覆盖 */
class AccountDaoTest {

    private static Connection conn;
    private static AccountDao dao;

    @BeforeAll
    static void openDb() throws SQLException {
        conn = DriverManager.getConnection("jdbc:hsqldb:mem:accountdb", "sa", "");
        dao = new AccountDao(conn);
        dao.createTable();
    }

    @AfterAll
    static void closeDb() throws SQLException {
        conn.close();
    }

    @BeforeEach
    void clearTable() throws SQLException {
        try (var st = conn.createStatement()) {
            st.execute("DELETE FROM accounts");
        }
    }

    @Test
    @DisplayName("成功转账：扣款与收款在同一个事务里一起生效")
    void successfulTransfer_commitsBothUpdates() throws SQLException {
        long alice = dao.open("alice", 100_00);
        long bob = dao.open("bob", 50_00);

        dao.transferCents(alice, bob, 30_00);

        assertEquals(70_00, dao.balanceCents(alice));
        assertEquals(80_00, dao.balanceCents(bob));
    }

    @Test
    @DisplayName("余额不足：转账被拒绝，双方余额分毫不变（原子性）")
    void insufficientFunds_leavesBothBalancesUntouched() throws SQLException {
        long alice = dao.open("alice", 10_00);
        long bob = dao.open("bob", 50_00);

        IllegalStateException ex = assertThrows(IllegalStateException.class,
                () -> dao.transferCents(alice, bob, 99_00));
        assertEquals("余额不足或付款账户不存在: " + alice, ex.getMessage());

        assertEquals(10_00, dao.balanceCents(alice), "失败的事务不能留下半拉子扣款");
        assertEquals(50_00, dao.balanceCents(bob));
    }

    @Test
    @DisplayName("收款账户不存在：扣款已执行，回滚把它撤销——这是 rollback 语义的真演示")
    void missingPayee_rollsBackTheDebit() throws SQLException {
        long alice = dao.open("alice", 100_00);

        // 收款方 id 999 不存在：第 1 步扣款成功、第 2 步收款失败 → rollback 撤销第 1 步
        assertThrows(IllegalStateException.class,
                () -> dao.transferCents(alice, 999L, 30_00));

        assertEquals(100_00, dao.balanceCents(alice),
                "扣款语句实际执行过，没有回滚机制的话这里只剩 70");
    }
}
