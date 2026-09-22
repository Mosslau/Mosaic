// examples/ex06-idempotency-interceptor-demo/ex06-idempotency-interceptor-demo.java
// 接口幂等拦截器语义模拟（对应主文档 3.6）
// 教学映射：与 ph16 的 Idempotency-Key（请求头幂等键）与 ph17 的消费端去重是同构思想的不同落点——
//   接口层幂等要同时解决三件事：
//     ① 防重放：同一业务键在 TTL 窗口内重复请求 → 不再执行业务，直接返回首次结果（结果缓存）
//     ② 防并发重入：同一键的两个请求同时到达 → 只有 1 个真正执行业务，另一个等结果（in-flight 单飞）
//     ③ 窗口外兜底：TTL 只能覆盖「窗口内」，很晚的重放靠数据库唯一约束（@Idempotent 只负责接口层）
// 本文件把 Spring HandlerInterceptor / AOP 注解拦截器的核心语义用纯 Java 演出来：
//   @Idempotent 标方法（带 TTL），@IdempotentId 标「构成业务键」的参数，
//   拦截器反射解析注解 → 算出业务键 → 走「结果缓存 + in-flight 等待」。
// 教学性覆盖：生产版在 Spring AOP 里解析注解（或配 ph16 的请求头幂等键），本文件用反射直调演示同一语义；
//             结果用对象内存缓存（生产可换 Redis String + TTL），TTL 时钟用虚拟时钟驱动。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（在 examples/ex06-idempotency-interceptor-demo/ 目录下执行）
//   javac ex06-idempotency-interceptor-demo.java
//   # 2. 运行
//   java IdempotencyInterceptorDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.lang.annotation.Annotation;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Parameter;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** 幂等拦截器演示：注解幂等 + 结果缓存 + 并发防重入 */
final class IdempotencyInterceptorDemo {

    interface Clock {
        long now();
    }

    static final class ManualClock implements Clock {
        private long t;

        ManualClock(long start) {
            this.t = start;
        }

        void advance(long ms) {
            t += ms;
        }

        @Override
        public long now() {
            return t;
        }
    }

    // ------------------------------------------------------------------
    // 注解：方法级 @Idempotent（幂等窗口）+ 参数级 @IdempotentId（业务键来源）
    // ------------------------------------------------------------------
    @Retention(RetentionPolicy.RUNTIME)
    @Target(ElementType.METHOD)
    @interface Idempotent {
        /** 幂等窗口秒数：窗口内重复请求直接返回首次结果 */
        long ttlSeconds() default 60;
    }

    @Retention(RetentionPolicy.RUNTIME)
    @Target(ElementType.PARAMETER)
    @interface IdempotentId {
    }

    // ------------------------------------------------------------------
    // 业务服务（被拦截目标）：pay 每次被真正执行都会写一次库
    // ------------------------------------------------------------------
    static final class PaymentService {
        private final AtomicInteger dbWrites = new AtomicInteger();

        /** 演示方法：@IdempotentId 的参数值 orderId 构成幂等键 */
        @Idempotent(ttlSeconds = 600)
        public String pay(@IdempotentId String orderId, String userId, int amount) {
            dbWrites.incrementAndGet(); // 真实系统 = INSERT 订单（唯一约束兜底）
            return "PAID:" + orderId + ":user=" + userId + ":amount=" + amount;
        }

        int dbWriteCount() {
            return dbWrites.get();
        }
    }

    /**
     * 幂等拦截器：解析注解 → 取业务键 → 结果缓存 + in-flight 防重入。
     * 状态都按业务键隔离，互不干扰；结果缓存带 TTL（窗口），窗口过期后允许重放
     * —— 「很晚的重放」由业务表唯一约束兜底（本文件注释说明，不实现 DB）。
     */
    static final class IdempotencyInterceptor {
        record Cached(Object value, long expiresAt) {
        }

        private final Clock clock;
        private final Map<String, Cached> results = new ConcurrentHashMap<>();
        private final Map<String, Boolean> inFlight = new ConcurrentHashMap<>();
        private final Map<String, Object> monitors = new ConcurrentHashMap<>();

        IdempotencyInterceptor(Clock clock) {
            this.clock = clock;
        }

        /**
         * 拦截一次调用：同业务键在窗口内只执行一次业务，重复调用返回首次结果。
         * 异常语义：业务失败向上抛 RuntimeException（不缓存失败结果），并发等待方被唤醒后可自行重试。
         */
        Object intercept(Object target, Method method, Object[] args) {
            Idempotent spec = method.getAnnotation(Idempotent.class);
            String bizKey = resolveBizKey(method, args); // 反射解析 @IdempotentId 参数
            long now = clock.now();
            Object monitor = monitors.computeIfAbsent(bizKey, k -> new Object());

            synchronized (monitor) {
                Cached cached = results.get(bizKey);
                if (cached != null && cached.expiresAt > now) {
                    return cached.value; // 窗口内重复请求：不执行业务，直接返回首次结果
                }
                while (inFlight.getOrDefault(bizKey, false)) {
                    try {
                        monitor.wait(); // 同一键的并发请求：等首次执行完成，而不是自己也去执行
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("等幂等结果时被中断", e);
                    }
                }
                // 双检：等待期间首次执行可能已完成
                cached = results.get(bizKey);
                if (cached != null && cached.expiresAt > now) {
                    return cached.value;
                }
                inFlight.put(bizKey, true);
            }

            try {
                Object result = invoke(target, method, args); // 真正执行业务（只有 1 个线程能走到这）
                synchronized (monitor) {
                    results.put(bizKey, new Cached(result, clock.now() + spec.ttlSeconds() * 1_000));
                    inFlight.remove(bizKey);
                    monitor.notifyAll();
                }
                return result;
            } catch (RuntimeException t) {
                synchronized (monitor) { // 失败不缓存结果：释放 in-flight，让后续请求重试
                    inFlight.remove(bizKey);
                    monitor.notifyAll();
                }
                throw t;
            }
        }

        /** 反射解析：找出标了 @IdempotentId 的参数，其值即业务键（参数名不可靠，用注解最稳） */
        private static String resolveBizKey(Method method, Object[] args) {
            Parameter[] params = method.getParameters();
            for (int i = 0; i < params.length; i++) {
                for (Annotation a : params[i].getAnnotations()) {
                    if (a instanceof IdempotentId) {
                        return String.valueOf(args[i]);
                    }
                }
            }
            throw new IllegalArgumentException("方法缺少 @IdempotentId 参数: " + method);
        }

        /** 反射调用并把底层异常按原类型抛出的包装（不吞掉业务异常） */
        private static Object invoke(Object target, Method method, Object[] args) {
            try {
                return method.invoke(target, args);
            } catch (InvocationTargetException e) {
                Throwable cause = e.getCause();
                if (cause instanceof RuntimeException re) {
                    throw re;
                }
                throw new RuntimeException(cause);
            } catch (ReflectiveOperationException e) {
                throw new RuntimeException(e);
            }
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);
        PaymentService service = new PaymentService();
        IdempotencyInterceptor interceptor = new IdempotencyInterceptor(clock);
        Method pay = PaymentService.class.getMethod("pay", String.class, String.class, int.class);

        System.out.println("场景一：串行重复请求 —— 同订单只写一次库，重复请求返回首次结果");
        Object r1 = interceptor.intercept(service, pay, new Object[]{"order-1001", "user-1", 500});
        Object r2 = interceptor.intercept(service, pay, new Object[]{"order-1001", "user-1", 500});
        check(service.dbWriteCount() == 1, "同一 orderId 调用两次 → 业务（写库）只执行 1 次");
        check(r1.equals(r2), "第二次请求返回首次结果（结果缓存），调用方拿到的响应一致");
        Object rOther = interceptor.intercept(service, pay, new Object[]{"order-1002", "user-1", 300});
        check(rOther.toString().contains("order-1002"), "不同业务键互不影响（幂等按键隔离）");
        check(service.dbWriteCount() == 2, "order-1002 是新键 → 正常执行第 2 次业务");

        System.out.println("场景二：并发重复请求 —— 两个线程同时提交同订单，只有 1 个真正执行业务");
        PaymentService concurrentService = new PaymentService();
        IdempotencyInterceptor ci = new IdempotencyInterceptor(clock);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch go = new CountDownLatch(1);
        AtomicInteger resultMatches = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(2);
        for (int i = 0; i < 2; i++) {
            pool.submit(() -> {
                try {
                    go.await();
                    Object r = ci.intercept(concurrentService, pay, new Object[]{"order-2001", "user-2", 800});
                    if (r.toString().contains("order-2001")) {
                        resultMatches.incrementAndGet();
                    }
                } catch (Exception e) {
                    // 拦截器抛受检异常的包装：演示里不应当发生
                    throw new RuntimeException(e);
                } finally {
                    done.countDown();
                }
            });
        }
        go.countDown();
        done.await(5, TimeUnit.SECONDS);
        pool.shutdownNow();
        check(concurrentService.dbWriteCount() == 1, "并发重复提交：业务仍只执行 1 次（另一线程等结果，不是重放）");
        check(resultMatches.get() == 2, "两个调用方都拿到了结果（执行方拿真结果，等待方拿缓存结果）");

        System.out.println("场景三：TTL 窗口过期 —— 幂等窗口之外允许重放（兜底交给数据库唯一约束）");
        clock.advance(601_000); // 600 秒窗口已过
        Object r3 = interceptor.intercept(service, pay, new Object[]{"order-1001", "user-1", 500});
        check(r3.equals(r1), "重放返回的是再次执行的结果（内容与首次相同是因为业务是幂等的：重复支付同金额）");
        check(service.dbWriteCount() == 3, "窗口过期后同键请求重新执行业务 → 3 次写库");
        System.out.println("   注：真正的「不能重复」业务（如不允许同一订单支付两次）除接口幂等外，");
        System.out.println("   还必须在订单表做唯一约束/状态机 —— 接口幂等只管窗口内的重复与并发（主文档 3.6）");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.6 / ph16 幂等键 / ph17 消费幂等：");
        System.out.println("  - 接口层：结果缓存挡重复、in-flight 挡并发重入，TTL 管窗口 —— 本文件的语义");
        System.out.println("  - 生产：Spring 用注解 + AOP/Interceptor 落地；也可用 ph16 的请求头 Idempotency-Key");
        System.out.println("  - 三处幂等是同构的：请求层查重表、消息层去重表、接口层结果缓存 —— 都是「先占位后执行」");
    }
}
