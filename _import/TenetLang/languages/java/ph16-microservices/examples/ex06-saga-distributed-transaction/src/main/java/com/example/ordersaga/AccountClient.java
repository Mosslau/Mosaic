package com.example.ordersaga;

import com.example.accountservice.AmountRequest;
import org.springframework.web.client.RestClient;

/** account-service 远程客户端：debit 失败按 HTTP 状态区分「业务失败 409」与「技术故障」 */
public class AccountClient {

    /** 业务失败（余额不足）——Saga 应取消而不是补偿 */
    public static class InsufficientFundsException extends RuntimeException {
        public InsufficientFundsException(String message) {
            super(message);
        }
    }

    private final RestClient restClient;

    public AccountClient(RestClient restClient) {
        this.restClient = restClient;
    }

    public void debit(long accountId, long amount, String txId) {
        post("/accounts/" + accountId + "/debit", amount, txId);
    }

    public void refund(long accountId, long amount, String txId) {
        post("/accounts/" + accountId + "/refund", amount, txId);
    }

    private void post(String uri, long amount, String txId) {
        restClient.post().uri(uri).body(new AmountRequest(amount, txId))
                .exchange((req, res) -> {
                    if (res.getStatusCode().value() == 409) {
                        throw new InsufficientFundsException("余额不足 txId=" + txId);
                    }
                    if (res.getStatusCode().isError()) {
                        throw new IllegalStateException("account-service 错误 " + res.getStatusCode().value());
                    }
                    return null;
                });
    }
}
