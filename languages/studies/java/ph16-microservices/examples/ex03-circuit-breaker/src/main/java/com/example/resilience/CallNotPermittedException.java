package com.example.resilience;

/** 熔断器 OPEN 时调用被直接拒绝（快速失败，不打下游） */
public class CallNotPermittedException extends RuntimeException {

    public CallNotPermittedException(String name) {
        super("circuit breaker '" + name + "' is OPEN — call not permitted");
    }
}
