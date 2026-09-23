# ph16 阶段项目：微服务订单系统（最小骨架）

## 需求

roadmap「ph16 微服务与分布式阶段」推荐项目之一是**微服务订单系统**——本项目是其最小骨架，把 ph15 的单体按业务边界拆成三个独立服务，串出一条完整的微服务调用链：**client → gateway（JWT 验签 + 路由转发）→ order-service（聚合订单详情）→ user-service（远程取用户名）**，外加两个贯穿全局的横切机制：**网关与 user-service 共享同一 JWT 密钥**（user-service 签发、gateway 验签，下游服务信任网关注入的 `X-Auth-User`/`X-Auth-Role` 身份头）与 **`X-Trace-Id` 全链路透传**（入口生成 → MDC → RestClient 拦截器逐跳透传）。数据纪律遵循主文档 3.1「**数据跟着服务走**」：order-service 不直连用户库，要用户名就走 user-service 的 API（`examples/ex01` 的同构模式）；每个服务独立进程、独立端口、内存表当私有库（不引数据库，聚焦拆分与调用语义，持久化是 ph13/ph15 的内容）。

对比 [ph15 project](../../ph15-spring-family/project/README.md)（单体：JPA + Security 全在一个进程里）：同一批「用户 + 订单」需求被拆成多进程后，单体内的方法调用变成了网络调用，于是本阶段项目专讲拆出来后的新问题——**网关把认证收敛到入口**（下游不再各自验签）、**远程调用要有超时与降级**（roadmap 必会概念）、**跨进程问题用 traceId 定位**（主文档 3.5 的同构最小实现）。

## 技术栈与验证环境

- OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + jjwt 0.12.5（随 msdemo-common 传递引入）
- 模块结构：`common`（纯 jar 契约库）→ `user-service` → `order-service` → `gateway`，四个模块在父 pom 的 reactor 里按序构建
- 默认端口：user-service=18311、order-service=18312、gateway=18313（各模块 `src/main/resources/application.properties`；测试全部用 `--server.port=0` 随机端口）
- 本机离线实测命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`（联网环境直接 `mvn test`；依赖全在 `/tmp/m2clone` 缓存）
- 手工体验命令（三个终端，或每个一条后台任务）：
  - `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run`（在 `user-service/`、`order-service/`、`gateway/` 各执行一次；首次需先 `mvn -o -Dmaven.repo.local=/tmp/m2clone -DskipTests -Dspring-boot.repackage.skip=true install` 把模块 jar 装进缓存，否则 `spring-boot:run` 解析不到 reactor 兄弟模块）

## 功能清单

- [x] **网关 JWT 鉴权**：`OncePerRequestFilter` 除 `POST /api/auth/login` 外一律验 `Authorization: Bearer`，无 token / 篡改 token / 过期 → `401 {"code":40100}` 统一 JSON（复用 common 的 `JwtService`，与 user-service 共享 `jwt.secret`）
- [x] **网关路由转发**：按路径谓词分发——`/api/auth/**`、`/api/users/**` → user-service，`/api/orders/**` → order-service（`Spring Cloud Gateway` 路由表的同构手写版）；转发时注入验签得到的 `X-Auth-User`/`X-Auth-Role` 头（内网信任边界，生产需网络隔离/mTLS），未知路由 → `40400`
- [x] **转发客户端踩坑规避**：用 `JdkClientHttpRequestFactory`——`SimpleClientHttpRequestFactory`（HttpURLConnection）在 POST + 下游 401 时会抛 `HttpRetryException`「cannot retry due to server authentication, in streaming mode」（已实测，见 `exercises/sol-04` 文件头）
- [x] **order-service 聚合详情**：`GET /api/orders/{id}` 本地订单（内存表）+ RestClient 远程调 user-service 取用户名（显式连接/读超时）；订单不存在 → `40400`
- [x] **远程失败降级（有损服务）**：用户服务 5xx/超时/连不上 → HTTP 仍 200、`degraded=true`、用户名显示「（用户服务暂不可用，降级展示）」，订单本体不丢（参照 `exercises/sol-02` 与主文档 3.3）；用户不存在（下游 404，确定答案）→ `40400` 透传不降级不重试
- [x] **X-Trace-Id 全链路透传**：三个服务都注册 common 的 `TraceIdFilter`（入口生成/接力 + MDC + 响应头回显），order-service 与 gateway 的下游 RestClient 挂 `TraceIdClientInterceptor`——实测同一 traceId 穿过 gateway → order → user 三跳一字不差
- [x] **身份头透传**：gateway 注入的 `X-Auth-User` 经 order-service 原样转发给 user-service（user-service 的 `GET /api/users/{id}` 需要该头，链上任何一跳断了它聚合就会失败）
- [x] **统一响应契约**：全部端点返回 `{code,message,data}` 壳（common 的 `ApiResponse`），业务码沿用 ph15/ph16 语义：40000 参数校验（user-service 登录/建号必填项，code/100 → 400）、40100 未认证、40101 登录失败、40300 无权限、40400 不存在、40901 用户名冲突、50000 兜底（三个服务的 GlobalExceptionHandler）；40001（缺幂等键）/50200（下游异常）/50400（下游超时）已列入 common `BizCodes`，本骨架未触发（幂等下单是「扩展方向」）；错误 HTTP 状态 = 业务码 / 100——完整码表见 common 的 `BizCodes.java`
- [x] **actuator 健康端点**：三个服务 `/actuator/health` 均 UP（监控端点是微服务标配，主文档 3.5）

## 验收标准

- `mvn -o -Dmaven.repo.local=/tmp/m2clone test`（在 `project/` 下跑整个 reactor）→ **BUILD SUCCESS**，四模块测试全绿：
  - common：无测试（纯契约库）
  - user-service：**Tests run: 7, Failures: 0**（登录签发 / 密码错 40101 / 缺身份头 40100 / USER 列用户 40300 / 查用户 / ADMIN 建号后可登录 / health）
  - order-service：**Tests run: 8, Failures: 0**（聚合成功取回远程用户名 / 订单不存在 40400 / 引用的用户不存在 40400 / 缺身份头 40100 / traceId 透传到 user-service / 双服务 health / user-service 宕机降级 degraded=true / 宕机时本地订单 404 不受影响）
  - gateway：**Tests run: 9, Failures: 0**（经网关登录签发 3 段 JWT / 密码错 40101 透传（验证 Jdk 客户端不抛 HttpRetryException）/ 无 token 40100 / 篡改 token 40100 / 有效 token 全链路聚合到 alice / 订单 40400 透传 / traceId 跨三服务透传 / 角色头注入生效（USER 40300、ADMIN 200）/ 三服务 health）
- curl 演示流（运行实录，默认端口 18311/18312/18313；TOKEN 为登录返回的 JWT，每段输出均已实测）：

```bash
# 1) 登录签发（经网关转发到 user-service；JWT 三段式）
$ curl -s -X POST http://localhost:18313/api/auth/login \
    -H 'Content-Type: application/json' -d '{"username":"alice","password":"alice123"}'
{"code":0,"message":"ok","data":{"token":"eyJhbGciOiJIUzM4NCJ9.eyJzdWIiOiJhbGljZSIsInJvbGUiOiJVU0VSIiwiaWF0IjoxNzg4MzQ5MzQwLCJleHAiOjE3ODgzNTY1NDB9.ldZr...","username":"alice","role":"USER"}}

# 2) 无 token 访问订单 → 网关拒（401，code 40100）
$ curl -s http://localhost:18313/api/orders/1001
{"code":40100,"message":"missing or malformed Authorization header"}     [HTTP 401]

# 3) 篡改 token（签名中间改一位）→ 40100（JWT 验签是「改了任何一个字节都拒」）
$ curl -s http://localhost:18313/api/orders/1001 -H "Authorization: Bearer $TOKEN_CHANGED"
{"code":40100,"message":"invalid or expired token"}                       [HTTP 401]

# 4) 全链路聚合：gateway(验签+注入 alice) → order-service → user-service 取回用户名 alice
$ curl -s http://localhost:18313/api/orders/1001 -H "Authorization: Bearer $TOKEN"
{"code":0,"message":"ok","data":{"orderId":1001,"item":"电动补能电器","userName":"alice","degraded":false,"userServiceTraceId":"a53e123d-..."}}   [HTTP 200]

# 5) X-Trace-Id 透传：响应头与聚合结果里的 userServiceTraceId 都是 curl-demo-trace-1
$ curl -s -i http://localhost:18313/api/orders/1001 \
    -H "Authorization: Bearer $TOKEN" -H "X-Trace-Id: curl-demo-trace-1"
HTTP/1.1 200
X-Trace-Id: curl-demo-trace-1
{"code":0,...,"userServiceTraceId":"curl-demo-trace-1"}

# 6) 订单不存在 → 40400
$ curl -s http://localhost:18313/api/orders/4041 -H "Authorization: Bearer $TOKEN"
{"code":40400,"message":"order not found: 4041","data":null}               [HTTP 404]

# 7) 密码错 → 40101（POST + 下游 401，Jdk 客户端不抛 HttpRetryException 才能原样透传）
$ curl -s -X POST http://localhost:18313/api/auth/login \
    -H 'Content-Type: application/json' -d '{"username":"alice","password":"wrong"}'
{"code":40101,"message":"username or password incorrect","data":null}      [HTTP 401]

# 8) 降级：停掉 user-service 后仍可查订单详情（degraded=true 占位，HTTP 200）
$ curl -s http://localhost:18312/api/orders/1001 -H 'X-Auth-User: alice'
{"code":0,"message":"ok","data":{"orderId":1001,"item":"电动补能电器","userName":"（用户服务暂不可用，降级展示）","degraded":true,"userServiceTraceId":null}}   [HTTP 200]
```

- 能画出链路并说出每跳在做什么：client → gateway（验签一次，注入身份头）→ order-service（聚合，身份头 + traceId 透传）→ user-service（按网关注入的身份头放行，返回用户名）；并说明与真实 Spring Cloud Gateway + 认证过滤器、OpenFeign、Nacos 的对应关系（主文档 3.2，见下）。

## 扩展方向

- **接真实 Spring Cloud Gateway / OpenFeign / Nacos**（未在本环境验证，原因如实标注）：离线缓存里 Spring Cloud 2021.0.8 的 **jar 齐备**（starter-gateway/starter-openfeign、gateway-server、openfeign-core 为 3.1.8，commons 为 3.1.7——同设备组件版本不统一、均属 3.1.x；2026-09-02 复核），但 2021.x 对应 Boot 2.x（javax），与本项目 Boot 3.3.0 基线二进制不兼容——所以真实 Gateway/OpenFeign 只能讲机制（主文档 3.2 有完整路由/谓词/过滤器与声明式客户端对照），本项目用「手写 mini 网关 + RestClient」同构实测了同一套语义；换到真实组件时：网关路由表换成 `spring.cloud.gateway.routes` 配置（`Path=/api/orders/**` 谓词 + `StripPrefix` 过滤器）、下游调用换成 `@FeignClient` 接口 + 注册中心服务名、`user-service.base-url` 硬编码换成 Nacos 服务发现，鉴权过滤器与 X-Trace-Id 拦截器逻辑原样保留
- **幂等下单**：主文档阶段项目愿景里的「订单服务幂等下单」本骨架未做（当前只有 GET 聚合读）；加 `POST /api/orders` 时把 `examples/ex04` 的 Idempotency-Key 占位去重机制搬进来，下单前经 user-service 校验用户（其 `findById` 已带调用计数供白盒断言）
- **韧性补全**：order-service 的 UserClient 目前是「超时一次即降级」；把 `examples/ex02` 的「瞬时故障重试一次 + 熔断」接上，注意只有幂等 GET 才敢重试
- **身份与安全**：内网信任边界当前靠 `X-Auth-User`/`X-Auth-Role` 注入头，生产应加网络隔离/mTLS 或服务级凭证；JWT 密钥三处配置写死相同值仅为演示，生产走配置中心/环境变量注入
- **可观测性升级**：把 `X-Trace-Id` 手写透传换成 Micrometer Tracing + OpenTelemetry（bridge jar 不在离线缓存，未在本环境验证，机制与字段对应见主文档 3.5）
- **持久化**：三个服务的内存表换成各自独立数据库（JPA 见 ph15 project），表结构按服务私有数据边界拆分

## 附录：构建注意点（父 pom 的 httpclient5 测试依赖）

父 pom `<dependencies>` 补了一条 **test-scope 的 httpclient5**：user-service 自带测试用 `TestRestTemplate` POST 登录并预期 401 响应，而 Boot 在 classpath 上没有 Apache HttpClient 时会把 `RestTemplateBuilder` 回退到 `SimpleClientHttpRequestFactory`（HttpURLConnection），后者在 POST 收到 401 时抛 `HttpRetryException`「cannot retry due to server authentication, in streaming mode」导致该用例 Error——同一踩坑在 `exercises/sol-04` 已实测并记录（网关因此改用 JdkClientHttpRequestFactory）。补上 httpclient5（Boot 3.3.0 仲裁为 5.3.1，离线缓存有 jar）后 Boot 自动选中 Apache 客户端、401 按普通响应处理，仅影响测试 classpath、不进任何产物 jar。若某天 user-service 测试改用带显式 request factory 的客户端，此条可删。
