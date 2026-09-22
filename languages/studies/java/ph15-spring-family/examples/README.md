# ph15 Spring 全家桶 示例

> 六个示例对应主文档「3. 语法与参数」六条主线：IOC/DI 与 Bean 生命周期 → Boot 自动配置/profile/actuator → MVC 拦截器 → AOP 与事务 → Spring Data JPA → Spring Security。每个示例是一个独立 Maven 工程，验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0**（父 POM 统一管理版本；Spring Framework 6.1.8 / Hibernate 6.5.2 / AspectJ 1.9.22 / Spring Security 6.3.4 / HSQLDB 2.5.0）。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：沙箱禁止写默认本地仓库 `~/.m2`，依赖取自本地缓存克隆 `/tmp/m2clone`，构建命令统一为 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`（联网环境直接 `mvn test`）。各 pom 带「离线版本仲裁」注释的项（junit-platform-launcher 1.10.1、surefire 3.2.5、spring-boot-maven-plugin 3.3.5、hsqldb 2.5.0、spring-security-bom 6.3.4 等）都是「缓存缺默认版本、用缓存内相近版本压过」的产物，**联网环境可删除**。

## 框架可用性策略（starter 缓存状态与实测标注）

| starter / 构件 | Boot 3.3.0 默认版本 | 本机缓存（/tmp/m2clone） | 实测状态 |
|---|---|---|---|
| spring-boot-starter-web | 3.3.0 | ✅ | ✅ 实测（ex02/03/06） |
| spring-boot-starter-test | 3.3.0（junit-platform-launcher 1.10.2 缺，钉 1.10.1） | ✅ | ✅ 实测（全部） |
| spring-boot-starter-actuator | 3.3.0 | ✅（micrometer-core 1.13.0） | ✅ 实测（ex02 /actuator/health、/info） |
| spring-boot-starter-aop | 3.3.0（AspectJ 1.9.22） | ✅ | ✅ 实测（ex04 @Aspect 代理计数） |
| spring-boot-starter-data-jpa | 3.3.0（Hibernate 6.5.2.Final） | ✅（hibernate-core 6.5.2.Final） | ✅ 实测（ex05 CRUD/派生查询/分页） |
| spring-boot-starter-jdbc | 3.3.0（HikariCP 5.1.0） | ✅ | ✅ 实测（ex04 连接池 + 事务） |
| HSQLDB | 2.7.2（默认，缓存缺） | ✅ 只有 2.5.0 → pom 钉 2.5.0 | ✅ 实测（见下「HSQLDB 说明」） |
| spring-boot-starter-security | 3.3.0（缓存缺） | ❌ | —（未用 starter，见下） |
| spring-security-web/config/core | Boot 3.3.0 管 6.3.0（缓存缺） | ✅ 6.3.4（BOM import 钉住） | ✅ 实测（ex06 认证/授权 8 用例） |
| spring-boot-starter-data-redis | — | ✅ 在缓存 | ⚠️ 未实测：Redis 服务器需单独启动，本机无（概念与「未在本环境验证」标注见主文档第 6 章，去向见 3.11 生态地图） |

**HSQLDB 说明（如实标注）**：Boot 3.3.0 默认管理 HSQLDB 2.7.2，但本机缓存只有 2.5.0，各 pom 钉到 2.5.0。Hibernate 6.5 对 HSQLDB 2.5.0 会打一条 WARN「2.5.0 低于官方支持下限 2.6.1，部分特性可能异常」——ex04/ex05 实测的建表、CRUD、派生查询、分页（`offset ... fetch next`）、事务回滚全部正常；建议联网环境升级到 2.7.x 消除 WARN。该差异不影响本阶段任何教学结论。

**Spring Security 版本仲裁说明**：Boot 3.3.0 的 BOM 把 Spring Security 管到 6.3.0（缓存缺），且 starter-security 3.3.0 缓存也缺；ex06/project 用 `<dependencyManagement>` import **spring-security-bom 6.3.4**（缓存有 6.3.4 全家）并直接声明 `spring-security-web/config`（不引 starter-security），离线实测通过。联网环境可改回 starter-security + 父 POM 管版本。

## 示例列表

| 目录 | 主题 | 依赖 | 验证命令 | 实测结果 |
|------|------|------|---------|---------|
| ex01-spring-core-ioc-lifecycle/ | IOC/DI 容器：构造器注入、@Primary/@Qualifier、生命周期回调顺序、作用域、条件装配 | spring-context（无 Web） | `mvn -o -Dmaven.repo.local=/tmp/m2clone test` | Tests run: **6** |
| ex02-spring-boot-autoconfig-profile-actuator/ | 自动配置追踪 + profile(dev/prod) + actuator + @ConfigurationProperties | starter-web + starter-actuator | test；`spring-boot:run -Dspring-boot.run.profiles=dev/prod` 后 curl | Tests run: **4**；curl dev/prod 全过；条件报告 **146 positive / 295 negative** |
| ex03-spring-mvc-interceptor/ | HandlerInterceptor 拦截器链顺序、短路、Filter vs Interceptor | starter-web | test；`spring-boot:run` 后 curl | Tests run: **3**；curl 200/403 |
| ex04-spring-aop-transaction/ | @Aspect 切面 + @Transactional 回滚规则/传播/自调用陷阱 | starter-aop + spring-jdbc + HikariCP + HSQLDB（无 Web） | test | Tests run: **6** |
| ex05-spring-data-jpa/ | Spring Data JPA：接口即实现、派生查询、@Query、分页 | starter-data-jpa + HSQLDB | test | Tests run: **5** |
| ex06-spring-security-authz/ | Spring Security：Basic 认证、URL 级/方法级授权、401/403 统一 JSON、BCrypt | starter-web + spring-security-web/config 6.3.4 | test；`spring-boot:run` 后 curl | Tests run: **8**；curl 401/403/200 |

## 验证记录（实测输出要点）

### ex01：Spring Core IOC/DI + 生命周期（Tests run: 6）

- 生命周期回调实测顺序（`LifecycleTest.lifecycleCallbacksFireInDocumentedOrder` 断言）：
  - 初始化：`constructor → @PostConstruct → afterPropertiesSet(InitializingBean) → customInit(@Bean initMethod)`
  - 销毁：`@PreDestroy → destroy(DisposableBean) → customDestroy(@Bean destroyMethod)`
- 作用域实测：singleton 两次 `getBean` 同一实例；prototype 每次新实例，且 `context.close()` 后 **prototype 不触发销毁回调**（容器不管理 prototype 生命周期）
- 条件装配实测：`System.setProperty("demo.feature.enabled", "true")` 前后，`getBean(FeatureToggleBean)` 从抛异常变为可用
- 自调用陷阱预告：ex04 用切面计数证明了 `this.xxx()` 绕过代理

### ex02：自动配置 + profile + actuator（Tests run: 4）

- `AutoConfigurationReportTest` 把容器的 `ConditionEvaluationReport` 拿出来数：**positive-match 自动配置类 145 个**（含 WebMvcAutoConfiguration、DispatcherServletAutoConfiguration、HealthEndpointAutoConfiguration 全部 isFullMatch）
  - 说明：145 与下一条 --debug 日志的 146 相差 1，是两种计数口径——测试按条件报告 Map 的条目（`isFullMatch()` 的 source）统计，日志报告按「Positive matches:」标题下展示的顶层条目统计；机制与结论一致（数量级相同、条目可互查）
- 运行实录（`--debug` 启动，日志 CONDITIONS EVALUATION REPORT）：
  - **Positive matches: 146 条**，如 `AopAutoConfiguration matched: - @ConditionalOnProperty (spring.aop.auto=true) matched`
  - **Negative matches: 295 条**，如 `ActiveMQAutoConfiguration: Did not match: - @ConditionalOnClass did not find required class 'jakarta.jms.ConnectionFactory'`（没引的中间件因缺 class 全被条件挡掉）
- profile 切换（dev 端口 18092 / prod 端口 18093，`-Dspring-boot.run.profiles=` 指定）：
  - dev：`GET /api/greeting` → `{"featureBeanPresent":true,"message":"dev-profile-greeting","profile":"[dev]","featureEnabled":true}`
  - prod：`{"featureEnabled":false,"featureBeanPresent":false,"message":"prod-profile-greeting","profile":"[prod]"}`——同一 jar 换环境配置驱动装配
- actuator：`GET /actuator/health` → `{"status":"UP",...}`；`GET /actuator/info` → `{"app":{"env":"dev","name":"ph15-ex02-profile-actuator"}}`

### ex03：MVC 拦截器（Tests run: 3）

- 完整链路实测顺序（`InterceptorFlowTest` 断言）：`filter.before → first.pre → second.pre → controller.hello → second.post → first.post → second.after → first.after → filter.after`
- 短路实测（`?block=true`）：`filter.before → first.pre → second.pre → second.pre.BLOCKED → first.after → filter.after`——Controller 不执行、postHandle 一律不执行、只有已放行的 first 收到 afterCompletion；HTTP 403
- 运行实录：拦截器日志 `first.pre -> 目标方法 HelloController#hello`、`first.after -> 耗时 15 ms（ex=null）`（HandlerMethod 可见 = Interceptor 与 Filter 的定位差）

### ex04：AOP + 事务（Tests run: 6，真实 HSQLDB 断言余额）

- 运行时异常 → 整事务回滚：`doubleDebitThenThrowRuntime` 抛 `IllegalStateException` 后双方余额不变
- 受检异常 → 默认**不回滚**：抛 `IOException` 后扣款已提交；`@Transactional(rollbackFor = IOException.class)` 后回滚
- REQUIRES_NEW：外层事务失败回滚，内层 `markerRequiresNew` 独立提交（events 表计数 = 1）
- 自调用陷阱：`this.doubleDebitThenThrowRuntime()` 绕过代理——扣款各自自动提交无人回滚，且切面代理计数在自调用期间**不增长**（只 +1 外层调用）

### ex05：Spring Data JPA（Tests run: 5）

- 派生查询编译成的 SQL（show-sql 实录）：`findByTitleContainingIgnoreCase("java")` → `select ... where upper(b1_0.title) like upper(?) escape '\'`；`existsByAuthor` → `select b1_0.id from book ... fetch first ? rows only`；`countByYearAfter` → `select count(...) where b1_0.year>?`
- 分页：`findAll(PageRequest.of(0,2,Sort.by(DESC,"year")))` 第一页两新书、第二页两旧书，`totalElements=4`（HSQLDB 2.5.0 分页 SQL 实测通过）
- Service 层事务：`importTwoThenFail` 两条插入 + 抛异常 → 仓库无残留（4 本 seed 之外为 0）

### ex06：Spring Security（Tests run: 8）

- 匿名访问 → 401 `{"code":40100,"message":"未认证：请携带有效凭证","data":null}`（自定义 AuthenticationEntryPoint）
- user（ROLE_USER）读 `/api/books` 200、删书 403 `{"code":40300,...}`（@PreAuthorize 方法级）、访问 `/api/admin/users` 403（URL 级 hasRole）
- admin（ROLE_ADMIN）全部放行；密码错 → 401
- BCrypt：`loadUserByUsername("admin").getPassword()` 以 `$2a$` 开头、不含明文

## 端口说明

ex02=18092(dev)/18093(prod)、ex03=18094、ex06=18095（各 application.properties 的 `server.port` 固定）；ex01/ex04/ex05 无服务进程。`spring-boot:run` 退出即结束；测试中途如残留进程用 `lsof -ti tcp:<端口> | xargs kill` 清理。
