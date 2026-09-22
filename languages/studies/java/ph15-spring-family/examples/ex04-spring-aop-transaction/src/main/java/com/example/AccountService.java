package com.example;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;

/**
 * 账户服务：@Transactional 的「回滚规则 / 传播行为 / 自调用陷阱」实验台。
 * 事务与切面都靠代理生效——本类里所有方法都要被代理包住才有效，
 * 而「类内部 this.xxx() 自调用」会绕过代理，这是本示例要实测的核心陷阱。
 */
@Service
public class AccountService {

    private final JdbcTemplate jdbc;
    /** 延迟自引用：拿到的是【代理后的自己】——用于演示「显式走代理」与「this 自调用」的差别 */
    private final ObjectProvider<AccountService> self;

    public AccountService(JdbcTemplate jdbc, ObjectProvider<AccountService> self) {
        this.jdbc = jdbc;
        this.self = self;
    }

    /** 走代理的本服务引用（ObjectProvider 在调用时才取，避免构造期循环依赖） */
    public AccountService proxiedSelf() {
        return self.getObject();
    }

    @Transactional
    public void createAccount(String name, int balance) {
        jdbc.update("INSERT INTO accounts(name, balance) VALUES (?, ?)", name, balance);
    }

    @Transactional(readOnly = true)
    public int balance(String name) {
        Integer b = jdbc.queryForObject("SELECT balance FROM accounts WHERE name = ?", Integer.class, name);
        return b == null ? -1 : b;
    }

    // ------------------------------------------------------------------
    // 1) 成功转账：两条 UPDATE 在一个事务里，要么都成要么都滚
    // ------------------------------------------------------------------

    @Transactional
    public void transfer(String from, String to, int amount) {
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, from);
        jdbc.update("UPDATE accounts SET balance = balance + ? WHERE name = ?", amount, to);
    }

    // ------------------------------------------------------------------
    // 2) 运行时异常（RuntimeException）→ 默认整事务回滚
    // ------------------------------------------------------------------

    /** 先扣两边再抛运行时异常：走代理调用时两条扣款都要被回滚 */
    @Transactional
    public void doubleDebitThenThrowRuntime(String from, String to, int amount) {
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, from);
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, to);
        throw new IllegalStateException("模拟故障：扣款后系统崩溃（RuntimeException 默认回滚）");
    }

    /** 自调用陷阱：this.xxx() 绕过代理 → @Transactional 与切面都不生效 */
    public void callInsideClassBypassesProxy(String from, String to, int amount) {
        this.doubleDebitThenThrowRuntime(from, to, amount);
    }

    // ------------------------------------------------------------------
    // 3) 受检异常（IOException 等）→ 默认【不回滚】，需要 rollbackFor 显式声明
    // ------------------------------------------------------------------

    @Transactional
    public void doubleDebitThenThrowChecked(String from, String to, int amount) throws IOException {
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, from);
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, to);
        throw new IOException("模拟受检异常：默认不回滚");
    }

    /** rollbackFor 显式声明受检异常也回滚 */
    @Transactional(rollbackFor = IOException.class)
    public void doubleDebitCheckedWithRollbackFor(String from, String to, int amount) throws IOException {
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, from);
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, to);
        throw new IOException("模拟受检异常：rollbackFor=IOException 声明后回滚");
    }

    // ------------------------------------------------------------------
    // 4) 传播行为：REQUIRES_NEW 在独立事务里提交，外层回滚不影响它
    // ------------------------------------------------------------------

    @Transactional
    public void outerDebitThenFailWithMarker(String from, int amount, String markerLabel) {
        jdbc.update("UPDATE accounts SET balance = balance - ? WHERE name = ?", amount, from);
        // 走代理调用 REQUIRES_NEW 方法：挂起外层事务，独立提交后再恢复外层
        proxiedSelf().markerRequiresNew(markerLabel);
        throw new IllegalStateException("外层事务随后失败——REQUIRES_NEW 的标记应已独立提交");
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markerRequiresNew(String label) {
        jdbc.update("INSERT INTO events(label) VALUES (?)", label);
    }

    public int eventCountByPrefix(String prefix) {
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM events WHERE label LIKE ?", Integer.class, prefix + "%");
        return n == null ? 0 : n;
    }
}
