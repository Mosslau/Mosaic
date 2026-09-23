# ph16 微服务与分布式 示例

> 六个示例对应主文档「3. 语法与参数」五条主线：服务拆分与远程调用（ex01）→ 超时/重试/降级（ex02）→ 熔断与限流（ex03）→ 幂等（ex04）→ 分布式锁（ex05）→ 分布式事务 Saga（ex06）。每个示例是一个独立 Maven 工程，验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0**（父 POM 统一管理版本；Spring Framework 6.1.8 / lettuce 6.3.2.RELEASE / spring-data-redis 3.3.0）。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：沙箱禁止写默认本地仓库 `~/.m2`，依赖取自本地缓存克隆 `/tmp/m2clone`，构建命令统一为 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`（联网环境直接 `mvn test`）。各 pom 带「离线版本仲裁」注释的项：junit-platform-launcher 钉 1.10.1（Boot 3.3.0 默认管 1.10.2，离线缓存无 1.10.2，离线构建真实必需）；surefire 显式钉 3.2.5（恰为 Boot 3.3.0 默认管理版本，仅为显式化）；spring-boot-maven-plugin 钉 3.3.5（按构建时缓存快照钉住，现缓存已含默认 3.3.0）——后两项联网环境可删除，离线亦非必需。

## 框架可用性策略（缓存探测结果与实测标注）

ph16 的主题是中间件生态，本机离线缓存对中间件覆盖有限，**策略：缓存内构件一律实测；缓存外的只在主文档讲机制并如实标「未在本环境验证」，可运行示例用缓存内构件实现同构模式**。

| 构件 | 主文档对应小节 | 本机缓存（/tmp/m2clone） | 处理方式 |
|------|---------------|--------------------------|---------|
| spring-cloud-starter-gateway / openfeign 等 Spring Cloud | 3.2 | ⚠️ 2021.0.8 的 **jar 在缓存**（starter-gateway/starter-openfeign、gateway-server、openfeign-core 为 3.1.8，commons 为 3.1.7——同设备组件版本不统一、均属 3.1.x；2026-09-02 复核），但 2021.x 对应 Boot 2.x（javax），与本阶段 Boot 3.3.0 基线二进制不兼容（表述以构建时缓存快照口径为准） | 主文档讲机制（未在本环境验证）；ex01/ex02 用 RestClient 同构实测调用语义；网关用 exercises/sol-04 与 project 的手写 mini 网关演示 |
| Nacos / Sentinel（com.alibaba.cloud/csp） | 3.2/3.3 | ❌ 完全不在缓存（需中间件） | 主文档讲机制（未在本环境验证） |
| Resilience4j（io.github.resilience4j） | 3.3 | ❌ 只有 BOM，无核心 jar | 主文档讲机制（未在本环境验证）；ex03 手写熔断器/令牌桶同构实测 |
| Micrometer Tracing / OpenTelemetry bridge | 3.5 | ❌ 只有 micrometer-tracing-bom 与 opentelemetry-api，无 bridge jar | 主文档讲机制（未在本环境验证）；ex01 用 X-Trace-Id 头 + MDC 同构实测透传语义 |
| spring-boot-starter-web / actuator / test 3.3.0 | 全部 | ✅ | 实测（ex01/02/04/06，共 22 用例，2026-09-02 复测全绿） |
| spring-data-redis 3.3.0 + lettuce 6.3.2.RELEASE | 3.4 | ✅（Boot 3.3.0 管理的 lettuce 恰为 6.3.2.RELEASE，无需仲裁） | 实测（ex05，真实 redis-server 8.6.2 由测试用 ProcessBuilder 拉起） |
| jjwt 0.12.5 | 网关鉴权 | ✅ | 实测（exercises/sol-04 与 project） |

**Redis 说明**：ex05 的测试用 `ProcessBuilder` 在随机端口拉起真实 `redis-server`（本机 8.6.2，`--save "" --appendonly no` 不落盘），测完即关；找不到 redis-server 二进制的环境整组测试按 Assumptions 跳过并标注「未在本环境验证」。注意本机 6379 上已有一个**带密码的常驻 Redis**（`redis-cli ping` 返回 NOAUTH），ex05 不使用它（随机端口独立实例，互不影响）。

## 示例列表

| 目录 | 主题 | 依赖 | 验证命令 | 实测结果 |
|------|------|------|---------|---------|
| ex01-service-split-restcall/ | 单体拆分：user-service + order-service 两进程（测试同 JVM 双上下文）、RestClient 显式超时、X-Trace-Id 透传、actuator 健康端点 | starter-web + starter-actuator | `mvn -o -Dmaven.repo.local=/tmp/m2clone test` | Tests run: **6** |
| ex02-timeout-retry-fallback/ | 超时/重试/降级失败语义：4xx 不重试、5xx 与超时重试、仅幂等可重试、耗尽降级 | starter-web | 同上 | Tests run: **6** |
| ex03-circuit-breaker/ | 熔断器状态机（CLOSED/OPEN/HALF_OPEN，滑动窗口失败率）+ 令牌桶限流（纯 Java，Clock 注入确定性测试） | starter-test | 同上 | Tests run: **7** |
| ex04-idempotency/ | 幂等键：ConcurrentHashMap + CompletableFuture 并发去重、TTL 窗口、失败不缓存 | starter-web | 同上 | Tests run: **6** |
| ex05-redis-distributed-lock/ | Redis 分布式锁：SET NX PX 原子占位 + token 持有者校验 + Lua 原子释放（真实 redis-server 实测） | spring-data-redis + lettuce | 同上（自动拉起 redis-server） | Tests run: **5** |
| ex06-saga-distributed-transaction/ | Saga 编排式分布式事务：下单→扣款→预约物流，失败补偿退款；debit/refund 按 txId 幂等 | starter-web | 同上 | Tests run: **4** |

合计 **34 个测试用例全部通过**（本机离线实测）。

## 验证记录（实测输出要点）

### ex01：服务拆分 + RestClient 超时 + TraceId 透传（Tests run: 6）

- 同 JVM 起两个真实 HTTP 服务（随机端口）：`orderDetailComposesUserAcrossServices` 断言订单 1001 聚合出 user-service 远程返回的「张三」
- 超时实测：慢用户（sleep 1500ms）触发读超时 800ms → 504 `code 50400`，实测耗时 < 1400ms（调用方没被拖死）；日志里 user-service 侧出现 `AsyncRequestNotUsableException: ClosedChannelException`——调用方已超时断开，这是「下游还在算、上游已放弃」的真实痕迹，正是超时价值的反面教材
- TraceId：请求带 `X-Trace-Id: trace-test-0001` → 响应头原样返回且 order-service 聚合结果里的 `userServiceTraceId` 同为 `trace-test-0001`（透传到下游）；不带则由入口生成 UUID 并同样透传
- 双服务 `/actuator/health` 均 `UP`
- 踩坑记录（已写进测试注释）：`SpringApplicationBuilder.properties()` 设的默认属性优先级**低于** classpath 的 `application.properties`——测试注入随机端口必须用命令行参数 `run("--server.port=0", ...)`

### ex02：超时/重试/降级（Tests run: 6）

- `transientFailuresAreRetriedUntilSuccess`：下游 `/flaky?failBefore=2` 前两次 500，第 3 次成功；`/admin/hits` 实测下游被打了 3 次
- `persistent5xxFallsBackAfterMaxAttempts`：`/always-error` 打满 3 次后返回降级体 `degraded-default`
- `clientError4xxIsNotRetried`：404 只打 1 次——客户端错误重试无意义
- `readTimeoutIsRetriedThenFallsBack`：慢端点 900ms + 读超时 300ms，重试 3 次全超时 → 降级
- `nonIdempotentPostIsNotRetried` vs `idempotentPostIsRetriedUntilSuccess`：同一故障端点，非幂等 POST 只打 1 次直接降级，幂等 POST 重试到成功——**幂等是重试的前置条件**（roadmap 必会概念）

### ex03：熔断器 + 令牌桶（Tests run: 7）

- 熔断状态机：窗口 4、失败率 ≥50% 熔断。实测 2 次失败不熔断（窗口未满）→ 4 次失败 OPEN → OPEN 期调用快速失败且**下游调用计数为 0**（`AtomicInteger` 断言）→ 拨时钟过等待窗口进 HALF_OPEN → 2 次探测成功回 CLOSED / 探测失败立即回 OPEN 并重计时
- 令牌桶：容量 3、10 个/秒。突发取 3 个全过、第 4 个被拒；拨时钟 200ms 补 2 个；长时间后不超过容量上限

### ex04：幂等键（Tests run: 6）

- 同 key 重复提交：返回同一 orderId、`Idempotent-Replay: true`、业务计数器只 +1
- **16 线程并发撞同一 key**（CountDownLatch 发令枪）：全部拿到同一 orderId，业务只执行 1 次（CompletableFuture 占位语义）
- 不同 key 各自独立；缺 key → 400 `code 40001`
- TTL：窗口内重放、过期后重新处理；业务失败不缓存（重试可成功）

### ex05：Redis 分布式锁（Tests run: 5，真实 redis-server 8.6.2）

- 加锁/解锁闭环；持锁期间第二持有者被拒、释放后可得
- 错误 token 解不开他人锁（Lua 比对+删除原子执行）
- TTL 兜底：持有者「宕机」不解锁，300ms 后锁自动释放，下一个持有者能拿到——防死锁
- 12 线程并发抢锁：恰好 1 个赢家

### ex06：Saga 分布式事务（Tests run: 4）

- 成功路径：下单 → 扣款 → 预约物流 → CONFIRMED，余额减 200，无补偿记录
- 余额不足（账户 2 只有 50）：debit 409 → 订单 CANCELLED，余额不变，**不产生补偿**（业务失败不是技术故障）
- 物流失败（item=fragile 稳定触发）：钱已扣 → 自动补偿退款 → 订单 FAILED，余额恢复原值，补偿日志 1 条
- sagaId 幂等：同一 sagaId 重复提交返回同一终态，余额只扣一次（sagaId 幂等 + debit/refund 按 txId 幂等双保险）

## 端口说明

`spring-boot:run` 手工体验端口：ex01 user-service=18211 / order-service=18212，ex02 flaky-server=18213，ex04=18214，ex06 account-service=18215 / order-service=18216；ex03/ex05 无常驻服务（ex05 的 redis-server 用随机端口）。测试全部用随机端口（`--server.port=0`），互不冲突。退出即结束；测试中途如残留进程用 `lsof -ti tcp:<端口> | xargs kill` 清理。
