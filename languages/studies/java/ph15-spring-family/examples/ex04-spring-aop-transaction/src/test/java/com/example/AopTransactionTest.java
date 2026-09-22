package com.example;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.junit.jupiter.SpringExtension;

import java.io.IOException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * ex04 测试：AOP 代理生效性 / 事务回滚规则（运行时异常、受检异常、rollbackFor）/
 * 传播行为 REQUIRES_NEW / 自调用陷阱。全部用真实 HSQLDB + 真实事务断言余额。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@ExtendWith(SpringExtension.class)
@ContextConfiguration(classes = TxAopConfig.class)
class AopTransactionTest {

    @Autowired
    private AccountService accountService;

    @Autowired
    private ServiceAuditAspect auditAspect;

    private static final String A = "alice";
    private static final String B = "bob";

    /** 成功转账：两条 UPDATE 原子生效，切面计数增长（代理在起作用） */
    @Test
    void transferCommitsAtomicallyThroughProxy() {
        accountService.createAccount(A, 100);
        accountService.createAccount(B, 0);
        int before = auditAspect.proxyCallCount();

        accountService.transfer(A, B, 30);

        assertThat(accountService.balance(A)).isEqualTo(70);
        assertThat(accountService.balance(B)).isEqualTo(30);
        assertThat(auditAspect.proxyCallCount()).isGreaterThan(before); // create*2+transfer 都经过切面
    }

    /** 运行时异常 → 整个事务回滚（转账双方余额都不变） */
    @Test
    void runtimeExceptionRollsBackWholeTransaction() {
        accountService.createAccount("carol", 100);
        accountService.createAccount("dave", 100);

        assertThatThrownBy(() -> accountService.doubleDebitThenThrowRuntime("carol", "dave", 40))
                .isInstanceOf(IllegalStateException.class);

        assertThat(accountService.balance("carol")).isEqualTo(100); // 两条扣款都被回滚
        assertThat(accountService.balance("dave")).isEqualTo(100);
    }

    /** 自调用陷阱：this.xxx() 绕过代理 → 事务不生效 → 扣款各自自动提交、无人回滚 */
    @Test
    void selfInvocationBypassesProxyAndTransaction() {
        accountService.createAccount("erin", 100);
        accountService.createAccount("frank", 100);

        long c1 = auditAspect.proxyCallCount();
        assertThatThrownBy(() -> accountService.callInsideClassBypassesProxy("erin", "frank", 50))
                .isInstanceOf(IllegalStateException.class);
        long c2 = auditAspect.proxyCallCount();

        assertThat(accountService.balance("erin")).isEqualTo(50);  // 扣款已提交：无人回滚
        assertThat(accountService.balance("frank")).isEqualTo(50);
        // 计数只 +1：外层 callInsideClassBypassesProxy 经过代理（被计数）；
        // 它内部 this.doubleDebitThenThrowRuntime 自调用绕过代理——切面计数不涨，证明代理确实被绕过
        assertThat(c2 - c1).isEqualTo(1);
    }

    /** 受检异常（默认不回滚）：扣款提交了——@Transactional 默认只对 RuntimeException/Error 回滚 */
    @Test
    void checkedExceptionDoesNotRollBackByDefault() {
        accountService.createAccount("grace", 100);
        accountService.createAccount("heidi", 100);

        assertThatThrownBy(() -> accountService.doubleDebitThenThrowChecked("grace", "heidi", 20))
                .isInstanceOf(IOException.class);

        assertThat(accountService.balance("grace")).isEqualTo(80); // 没有回滚
        assertThat(accountService.balance("heidi")).isEqualTo(80);
    }

    /** rollbackFor = IOException.class 显式声明后，受检异常也回滚 */
    @Test
    void rollbackForMakesCheckedExceptionRollBack() {
        accountService.createAccount("ivan", 100);
        accountService.createAccount("judy", 100);

        assertThatThrownBy(() -> accountService.doubleDebitCheckedWithRollbackFor("ivan", "judy", 20))
                .isInstanceOf(IOException.class);

        assertThat(accountService.balance("ivan")).isEqualTo(100); // 回滚了
        assertThat(accountService.balance("judy")).isEqualTo(100);
    }

    /** 传播行为 REQUIRES_NEW：内层独立提交，外层回滚不影响它 */
    @Test
    void requiresNewMarkerSurvivesOuterRollback() {
        accountService.createAccount("kent", 100);
        String marker = "m" + System.nanoTime();

        assertThatThrownBy(() -> accountService.outerDebitThenFailWithMarker("kent", 60, marker))
                .isInstanceOf(IllegalStateException.class);

        assertThat(accountService.balance("kent")).isEqualTo(100);       // 外层扣款回滚
        assertThat(accountService.eventCountByPrefix(marker)).isEqualTo(1); // REQUIRES_NEW 标记已独立提交
    }
}
