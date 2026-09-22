package com.example;

import com.example.accountservice.AccountServiceApplication;
import com.example.ordersaga.OrderSagaApplication;
import com.example.ordersaga.PlaceOrderRequest;
import com.example.ordersaga.SagaOrder;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** Saga 实测：成功路径扣款确认 / 余额不足取消不补偿 / 物流失败补偿退款 / sagaId 幂等不重复扣 */
class SagaTransactionTest {

    private static ConfigurableApplicationContext accountApp;
    private static ConfigurableApplicationContext orderApp;
    private static RestClient orderClient;
    private static RestClient accountClient;

    @BeforeAll
    static void startBoth() {
        accountApp = new SpringApplicationBuilder(AccountServiceApplication.class).run("--server.port=0");
        int accountPort = ((WebServerApplicationContext) accountApp).getWebServer().getPort();
        orderApp = new SpringApplicationBuilder(OrderSagaApplication.class)
                .run("--server.port=0", "--account-service.base-url=http://localhost:" + accountPort);
        int orderPort = ((WebServerApplicationContext) orderApp).getWebServer().getPort();
        orderClient = RestClient.create("http://localhost:" + orderPort);
        accountClient = RestClient.create("http://localhost:" + accountPort);
    }

    @AfterAll
    static void stopBoth() {
        orderApp.close();
        accountApp.close();
    }

    private SagaOrder place(String sagaId, long accountId, String item, long amount) {
        return orderClient.post().uri("/saga/orders")
                .body(new PlaceOrderRequest(sagaId, accountId, item, amount))
                .retrieve().body(SagaOrder.class);
    }

    private long balanceOf(long accountId) {
        Map<?, ?> body = accountClient.get().uri("/accounts/" + accountId).retrieve().body(Map.class);
        return ((Number) body.get("balance")).longValue();
    }

    private List<String> compensations() {
        return orderClient.get().uri("/saga/compensations")
                .retrieve().body(new ParameterizedTypeReference<>() {
                });
    }

    @Test
    void happyPathConfirmsAndDebits() {
        long before = balanceOf(1L);
        int compensationsBefore = compensations().size();
        SagaOrder order = place("saga-ok-1", 1L, "charger", 200L);
        assertThat(order.status()).isEqualTo("CONFIRMED");
        assertThat(balanceOf(1L)).isEqualTo(before - 200L);
        assertThat(compensations()).hasSize(compensationsBefore);   // 成功路径不产生补偿
    }

    @Test
    void insufficientFundsCancelsWithoutCompensation() {
        long before = balanceOf(2L);   // 账户 2 只有 50
        int compensationsBefore = compensations().size();
        SagaOrder order = place("saga-poor-1", 2L, "charger", 200L);
        assertThat(order.status()).isEqualTo("CANCELLED");
        assertThat(balanceOf(2L)).isEqualTo(before);       // 没扣成
        assertThat(compensations()).hasSize(compensationsBefore);   // 业务失败不产生补偿
    }

    @Test
    void fulfillmentFailureTriggersCompensationRefund() {
        long before = balanceOf(1L);
        int compensationsBefore = compensations().size();
        SagaOrder order = place("saga-fragile-1", 1L, "fragile", 300L);   // 易碎品：物流步骤必败
        assertThat(order.status()).isEqualTo("FAILED");
        assertThat(balanceOf(1L)).isEqualTo(before);       // 扣款已被补偿退回
        assertThat(compensations()).hasSize(compensationsBefore + 1);
        assertThat(compensations()).contains("saga-fragile-1 refunded 300");
    }

    @Test
    void sameSagaIdResubmissionReplaysTerminalState() {
        long before = balanceOf(1L);
        SagaOrder first = place("saga-retry-1", 1L, "charger", 100L);
        SagaOrder replay = place("saga-retry-1", 1L, "charger", 100L);   // 客户端超时重试同一 sagaId
        assertThat(first.status()).isEqualTo("CONFIRMED");
        assertThat(replay.status()).isEqualTo("CONFIRMED");
        assertThat(balanceOf(1L)).isEqualTo(before - 100L); // 只扣了一次（debit 按 txId 幂等 + sagaId 幂等双保险）
    }
}
