package com.example;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.AfterThrowing;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * 横切切面：给 AccountService 所有方法加「审计日志 + 调用计数」。
 * 教学点 1：事务（@Transactional）与切面（@Aspect）走同一个代理——本切面的调用计数
 *          恰好能「证明代理有没有生效」：自调用（this.xxx）不经过代理，计数不会增长。
 * 教学点 2：Around = 手动接管「方法调用前/后/异常」；AfterThrowing = 只观察异常。
 *           横切逻辑不该散落在每个业务方法里——AOP 把它们收拢成「切面」。
 */
@Aspect
@Component
public class ServiceAuditAspect {

    private static final Logger log = LoggerFactory.getLogger(ServiceAuditAspect.class);
    private final AtomicInteger proxyCalls = new AtomicInteger();

    @Around("execution(* com.example.AccountService.*(..))")
    public Object audit(ProceedingJoinPoint pjp) throws Throwable {
        proxyCalls.incrementAndGet(); // 只有「经过代理」的调用才会到这儿
        String method = pjp.getSignature().getName();
        long start = System.nanoTime();
        try {
            Object result = pjp.proceed();
            log.info("audit.around -> {} ok, 耗时 {} ms", method, (System.nanoTime() - start) / 1_000_000);
            return result;
        } catch (Throwable t) {
            log.warn("audit.around -> {} 抛异常 {}: {}", method, t.getClass().getSimpleName(), t.getMessage());
            throw t; // 切面只观察，不吞异常——异常语义归业务方法自己
        }
    }

    @AfterThrowing(pointcut = "execution(* com.example.AccountService.*(..))", throwing = "t")
    public void onThrowing(Throwable t) {
        log.warn("audit.afterThrowing -> 观察到异常 {}", t.getClass().getSimpleName());
    }

    public int proxyCallCount() {
        return proxyCalls.get();
    }
}
