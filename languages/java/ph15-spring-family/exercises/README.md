# ph15 Spring 全家桶 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0（父 POM 统一管 Spring Framework 6.1.8 / Hibernate 6.5.2 / AspectJ 1.9.22 / Spring Security 6.3.4）+ jjwt 0.12.5 + HSQLDB 2.5.0。本机 Maven 实测用 `mvn -o` 离线模式（依赖来自本地缓存 `/tmp/m2clone`）；正常联网环境直接 `mvn clean test` 即可。

**与 roadmap「ph15 Spring 全家桶阶段」练习小节的对应**：roadmap 列的「REST API 服务 / 统一响应结构」是 ph14 已练过的题目（REST Todo API、统一响应 `{code,message,data}` 分别在 ph14 练习 1/4/5 与 project），「Redis 缓存」在 [ph13 数据库阶段练习 4](../../ph13-database/exercises/README.md) 已落地（需本机 redis-server），故本阶段五题对准 §15 学习内容本身的容器机制与工程设施——练习 1 手写 DI 管「对象创建与依赖」，练习 2 生命周期/循环依赖，练习 3 profile 管「环境差异」，练习 4 AOP/事务管「横切与一致性」，练习 5 用 Security 重做「JWT 登录认证」（ph14 的 Controller 拦截器版升级为 Filter 链原生版）。

sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看。sol-01 是零依赖单文件（在 exercises/ 目录就地 `javac` + `java`，命令见练习 1 与文件头）；sol-02~05 是「源代码合集 + 注释里的 pom 来源」，按文件内注释把每个文件写入标准 Maven 工程后 `mvn -o -Dmaven.repo.local=/tmp/m2clone test` 验证（pom 分别复制 examples/ex01/ex02/ex04/ex06 的）。

## 练习 1：手写微型 DI 容器（★★）

**目标**：零第三方依赖，用反射实现「构造器参数类型 → 递归创建依赖 → 单例缓存」的微型容器，理解 IOC 的本质（容器管创建，代码只管声明依赖）。
**要求**：

- 实现 `com.example.MiniDiContainer`：`<T> T get(Class<T> type)` 按**唯一构造器**的参数类型递归实例化依赖；同类型只建一次（单例缓存）；构造器不止一个时报错
- 循环依赖检测：A 依赖 B、B 依赖 A 时 `get(A)` 必须抛带「循环依赖」字样的异常，而不是栈溢出
- 被测组件：`Car(Engine engine)`（构造器注入）、互相引用的 `ServiceA/ServiceB`；main 里用断言计数自测 4 个用例（注入可用、单例共享、引擎单例、循环检测）
- 编译运行（在 exercises/ 目录就地执行）：`javac -d out sol-01-mini-di-container.java && java -cp out com.example.MiniDiContainer`

**验收**：参考实现实测输出 `MINI DI TESTS PASSED (4 assertions)`；能说出「Spring 的 @ComponentScan + 构造器注入」与这段代码的对应关系（扫类 → 看构造器 → 递归造依赖 → 缓存）。

## 练习 2：构造器循环依赖实测与 @Lazy 解法（★）

**目标**：亲手让 Spring 撞一次纯构造器循环（Ping ↔ Pong），读报错，再用 `@Lazy` 修好——理解「容器为什么解不开构造器循环」。
**要求**：

- 工程复制 examples/ex01 的 pom（spring-context 即可，无 Web）
- `cycle` 包：`PingService(PongService)` 与 `PongService(PingService)` 互相构造器引用，`CycleConfig` 只扫该包
- `fix` 包：`PingLazyService(@Lazy PongService)` + 无回依赖的 `PongService`，`FixConfig` 只扫该包
- 两个测试：① 启动 `CycleConfig` 抛异常且错误信息含 `currently in creation`；② `FixConfig` 能启动且 `ping()` 输出 `ping(lazy) -> pong`
- 验证命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`

**验收**：参考实现实测 `Tests run: 2, Failures: 0`；能解释「字段/setter 注入的循环能被解开而构造器循环不能」（对象没建完无法提前暴露）；能说出依赖环是设计味道、优先拆环而非上 @Lazy。

## 练习 3：profile + 条件装配 + 类型安全配置（★★）

**目标**：做一个小型「通知服务」：同一 jar 用 dev/prod 两套 profile 切换行为，验证 profile 文件覆盖、`@ConfigurationProperties` 强类型绑定、`@ConditionalOnProperty` 条件装配三者联动。
**要求**：

- 工程复制 examples/ex02 的 pom（可去掉 actuator 依赖）
- `NotifyProperties`：`@ConfigurationProperties(prefix = "notify")` 绑定 `enabled` 与 `channel`（record + 构造器绑定）
- `NotifyConfig`：`notify.enabled=true` 才注册 `SmsSender` Bean（`@ConditionalOnProperty`）
- `GET /api/notify` 返回 `{enabled, channel, smsSenderPresent}`
- 配置文件：基础文件默认激活 dev；dev 开短信（channel=sms）、prod 关短信（channel=email）
- 测试：默认（dev）与 `spring.profiles.active=prod` 两个上下文分别断言三种状态
- 验证命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`

**验收**：参考实现实测 `Tests run: 2, Failures: 0`（dev → `{"enabled":true,"channel":"sms","smsSenderPresent":true}`；prod → `{"enabled":false,"channel":"email","smsSenderPresent":false}`）；能解释「profile 文件与 base 文件合并、同名属性 profile 胜出」的规则。

## 练习 4：支付服务的 AOP 切面与事务回滚（★★★）

**目标**：写一个真实事务服务：支付扣款 + 审计流水，业务异常回滚、审计 `REQUIRES_NEW` 独立提交，并挂一个耗时切面——把 ex04 的规则用到新领域。
**要求**：

- 工程复制 examples/ex04 的 pom（starter-aop + spring-jdbc + HikariCP + HSQLDB，无 Web）
- 表：`wallets(name, balance)`、`pay_audit(id, order_no, amount)`
- `PaymentService`：`pay(wallet, orderNo, amount)` 先查余额，不足抛**业务异常**（运行时，继承 IllegalStateException）；够则扣款并调 `proxiedSelf().audit(...)`（`@Transactional(propagation = REQUIRES_NEW)`）写流水
- `PaymentAuditAspect`：`@Around("execution(* ...PaymentService.pay(..))")` 计数 + 记耗时
- 测试：① 扣款成功余额减、审计 1 条；② 余额不足 → 余额不变、审计 0 条（回滚无副作用）；③ 切面计数随每次经代理的 pay 调用 +1
- 验证命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`

**验收**：参考实现实测 `Tests run: 3, Failures: 0`；能解释「为什么审计放在 REQUIRES_NEW」（主事务回滚也要留痕/通知）；能说清运行时异常默认回滚、受检异常要 `rollbackFor`（ex04 有对照实测）。

## 练习 5：Spring Security + JWT 无状态登录认证（★★★）

**目标**：把 ph14「拦截器验 JWT」升级为 Security 原生版：登录端点发 JWT、自定义 `OncePerRequestFilter` 验签写 SecurityContext、URL 级角色授权、401/403 统一 JSON——认证与授权都归框架管。
**要求**：

- 工程复制 examples/ex06 的 pom 并追加 jjwt 0.12.5 三坐标；属性 `jwt.secret`（≥32 字节，HS256 要求）
- `JwtService`：`issue(username, role)` 签发（sub/role/exp，2 小时）、`parse(token)` 验签
- `JwtAuthFilter extends OncePerRequestFilter`：`Authorization: Bearer <jwt>` → 验签 → 按 role 构造 `UsernamePasswordAuthenticationToken` 写 SecurityContext；非法/过期清空上下文（当作未认证）
- `SecurityConfig`：stateless、csrf 关、`/api/auth/login` permitAll、`/api/admin/**` hasRole('ADMIN')、其余 authenticated；401/403 写统一 JSON；filter 插在 `UsernamePasswordAuthenticationFilter` 之前；登录用 `AuthenticationManager`（内存用户 + BCrypt，同 ex06）
- 端点：`POST /api/auth/login`（成功返回 token）、`GET /api/me`（返回用户名 + authorities）、`GET /api/admin/users`（ADMIN 专属）
- 测试至少覆盖：登录发三段式 token、密码错 401、无 token 401（统一 JSON）、带 token 访问 /api/me、USER 访问 admin 403、ADMIN 放行、垃圾 token 401
- 验证命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`

**验收**：参考实现实测 `Tests run: 7, Failures: 0`（运行实录见 sol-05 文件头）；能画出「请求 → JwtAuthFilter 验签 → SecurityContext → authorizeHttpRequests → Controller」的链路，并说清它比 ph14 拦截器版多了什么（框架统一认证/授权/401/403，SecurityContext 贯穿服务层）。
