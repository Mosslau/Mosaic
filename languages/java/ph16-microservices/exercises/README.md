# ph16 微服务与分布式 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0（父 POM 统一管 Spring Framework 6.1.8）+ jjwt 0.12.5（练习 4）。本机 Maven 实测用 `mvn -o` 离线模式（依赖来自本地缓存 `/tmp/m2clone`）；正常联网环境直接 `mvn clean test` 即可。

**与 roadmap「16. 微服务与分布式阶段」练习小节的对应**：四题一一对应 roadmap 列的四个练习——练习 1 = 用户服务、练习 2 = 订单服务、练习 3 = 设备管理服务、练习 4 = 网关鉴权。四题合起来是一条最小微服务链路：服务拆分（练习 1/3）→ 服务间调用与失败处理（练习 2）→ 入口收敛与鉴权（练习 4），做完即具备本阶段 project（微服务订单系统）的全部零件。

sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看。四题都是「源代码合集 + 注释里的 pom 来源」：按文件内注释把每个文件写入标准 Maven 工程后 `mvn -o -Dmaven.repo.local=/tmp/m2clone test` 验证（pom 均复制 examples/ex01 的，练习 4 需追加 jjwt 0.12.5 三坐标，见文件头）。

## 练习 1：用户服务（★）

**目标**：把 ph15 单体里的「用户模块」拆成一个独立可运行的用户服务，理解「服务边界 = 进程边界 + 数据边界 + 接口契约」。
**要求**：

- 工程复制 examples/ex01 的 pom（starter-web + starter-actuator + starter-test），artifactId 改 `sol01-user-service`
- 内存用户表（`ConcurrentHashMap`），实现：`POST /users`（重名 409 业务码 40901）、`GET /users/{id}`（不存在 404 业务码 40400）、`GET /users` 列表
- `/actuator/health` 可访问（监控端点是微服务的标配，主文档 3.5）
- 测试：起真实服务（随机端口）断言创建/查回、重名 409、缺失 404、列表与健康端点

**验收**：参考实现实测 `Tests run: 4, Failures: 0`；能说出「独立部署、独立数据」与单体模块的区别。

## 练习 2：订单服务调用用户服务（★★）

**目标**：订单服务远程调用用户服务取用户名做聚合展示，亲手实现「超时 + 重试 + 降级」三件套。
**要求**：

- 同模块两个 Application（参照 examples/ex01）：用户服务（18322）提供正常/404/慢（1500ms）/首次 500 四种用户端点；订单服务（18323）`GET /orders/{id}` 聚合订单 + 用户名
- 调用端要求：连接/读超时显式设置；**仅幂等 GET 可重试**（最多重试 1 次）；4xx 不重试直接映射 40400；重试耗尽返回降级结果（`degraded=true` 占位文案），HTTP 仍 200
- 测试断言重试真实发生（用下游命中计数，不靠日志目测）

**验收**：参考实现实测 `Tests run: 4`（重试后成功且下游命中 2 次；慢调用降级；404 透传）；能解释「为什么非幂等请求不能自动重试」（主文档 4.1）。

## 练习 3：设备管理服务（★★）

**目标**：车联网风格的设备注册服务，把幂等写进接口契约。
**要求**：

- `POST /devices`（body 含 `sn`/`model`）必须带 `Idempotency-Key` 头，缺失 → 400（业务码 40001）；`GET /devices/{sn}` 查询
- 双重幂等：① 请求级——同 key 重放首个结果不重建；② 业务级——`sn` 唯一（`putIfAbsent`），换 key 重发同一 sn 也只建一条
- 暴露建单计数端点，测试断言：同 key 重放 count +1；12 线程并发注册同一 sn（各自不同 key）count 也只 +1

**验收**：参考实现实测 `Tests run: 4`；能说出两层幂等各自防什么（网络重试 vs 换键重发）。

## 练习 4：网关鉴权（★★★）

**目标**：手写 mini 网关——JWT 认证收敛到入口，下游服务不再各自验签。
**要求**：

- 工程 = examples/ex01 的 pom + jjwt 0.12.5 三坐标（参照 ph15 exercises/sol-05 的 jjwt 用法）
- 用户服务（18325）：`POST /api/auth/login` 签发 JWT（jjwt 按密钥长度自动选 HS 算法：32–47 字节 → HS256、48–63 → HS384、≥64 → HS512；本练习 44 字节密钥落在 HS256，两服务共享配置）；`GET /api/users/{id}` 回显收到的 `X-Auth-User` 头
- 网关（18326）：`OncePerRequestFilter` 验 Bearer token（登录路径除外），验过注入 `X-Auth-User`/`X-Auth-Role` 头转发；转发控制器按方法/路径/query 透传（**用 `JdkClientHttpRequestFactory`**——`SimpleClientHttpRequestFactory` 在 POST + 下游 401 时抛 HttpRetryException，参考实现注释有实测记录）
- 无 token / 篡改 token → 401 统一 JSON（code 40100）；密码错 → 401（code 40101，沿用 ph15 码义）

**验收**：参考实现实测 `Tests run: 5`；能画出「客户端 → 网关（验签+注入身份头）→ 下游（信任头）」的调用链，并说明与 Spring Cloud Gateway + 认证过滤器的对应关系（主文档 3.2）。
