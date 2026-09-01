# ph14 Web 后端开发 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0 + jjwt 0.12.5 + JUnit Jupiter 5.10.2。本机 Maven 实测用 `mvn -o` 离线模式（沙箱禁止写默认本地仓库 `~/.m2`，依赖来自本地缓存 `/tmp/m2clone`）；正常联网环境直接 `mvn clean test` 即可。
> 五题与 Roadmap「ph14 Web 后端开发阶段」练习小节一一对应：Todo API（练习 1/4，纯 JDK 与 Spring Boot 各一遍）/ 文件上传（练习 4 的 upload 端点）/ 登录注册（练习 5）/ 设备管理 API 方向（练习 5 的注册表即设备/用户资源）。sol-* 为参考实现（文件头已注明验证环境、命令与实测数字），做完再看；sol 文件是「源代码 + 注释里的完整 pom 与配套类」，建工程时按注释把 pom 与配套类写入自己的工程。
> 练习 4/5 的 pom 复制 [../examples/ex04-spring-boot-rest/pom.xml](../examples/ex04-spring-boot-rest/pom.xml)（练习 5 用 [../examples/ex06-spring-boot-jwt-cors-openapi/pom.xml](../examples/ex06-spring-boot-jwt-cors-openapi/pom.xml) 的，含 jjwt 与「离线版本仲裁」注释）；练习 1/2/3 是零依赖的独立 java 文件（`javac` + `java`）。

## 练习 1：纯 JDK Todo REST API（★）

**目标**：用手写 `HttpServer`（零第三方依赖）实现 Todo 资源的四个 HTTP 方法，REST 语义完整。
**要求**：

- 实现 `com.example.TodoServer`：`GET /api/todos` 列表、`POST /api/todos` 创建（title 必填非空，空则 400）、`PATCH /api/todos/{id}` 局部更新（done/title）、`DELETE /api/todos/{id}` 删除
- 状态码语义化：创建 201、删除成功 204、目标不存在 404、方法不支持 405、title 空白 400
- JSON 手工解析可复用 `examples/ex01-jdk-httpserver/src/com/example/MiniJson.java`（练习重点在 HTTP 服务不在 JSON 库）；内存表用 `Map<Long, Map<String,Object>>`
- 编译运行：`javac -d out src/com/example/TodoServer.java src/com/example/MiniJson.java && java -cp out com.example.TodoServer 18087`

**验收**：参考实现实测——POST 创建 201 回带 id 的 todo、title 空白 400、GET 列表 200、PATCH done 200、DELETE 204、GET 不存在 404（curl 逐条比对，见 sol-01 文件头实测块）。

## 练习 2：手写参数校验器（★）

**目标**：零依赖实现非空/格式/范围/长度四类校验，先理解校验逻辑本身，再看框架注解替你做什么。
**要求**：

- 实现 `com.example.UserValidator.validate(UserInput)`，`UserInput` 是 record（name/email/age）
- 校验规则：name 非空白且 ≤20 字符；email 非空、≤50 字符且匹配邮箱正则；age 在 18~120
- 返回 `Map<String,String>`（字段名 → 错误信息），空 Map 表示通过；main 里用断言自测 6 个用例

**验收**：参考实现实测输出 `VALIDATOR TESTS PASSED (6 assertions)`（合法通过 + 5 种失败逐一断言）；能说出「为什么 Controller 里不写 if 校验」——声明式校验（ex05 的 `@Valid`）把规则和数据模型放一起。

## 练习 3：手写 JWT 签发与验签（★★）

**目标**：手写 HMAC-SHA256 签名的 JWT（不引库），理解「签名到底签了什么」。
**要求**：

- 实现 `com.example.HandmadeJwt.issue(secret, claims, ttlSeconds)`：header 固定 `{"alg":"HS256","typ":"JWT"}`，payload 含 `iat`/`exp` + 自定义 claims（如 sub、role），三段 base64url 以 `.` 连接
- 实现 `verifyAndGet(secret, token, claimKey)`：重算签名常量时间比对 + exp 过期检查，通过则返回 claim 值
- main 里断言 6 个用例：三段结构、验签取回 role、验签取回 sub、篡改签名失败、换密钥失败、过期失败

**验收**：参考实现实测输出 `JWT TESTS PASSED (6 assertions)`；能解释「为什么篡改 payload 会被识破」（签名覆盖完整 header.payload 字符串）。

## 练习 4：Spring Boot Todo API + MockMvc 测试（★★）

**目标**：用 Spring Boot 重做练习 1 的 Todo API，对比框架替你做了什么；掌握 Controller 层测试。
**要求**：

- `@RestController` + `@RequestMapping("/api/todos")`：GET 列表 / POST 创建（title 空白抛业务异常）/ PATCH 完成 / DELETE 删除，全部返回统一响应 `ApiResponse`
- **文件上传**（roadmap 练习「文件上传」）：`POST /api/todos/upload`，`@RequestParam("file") MultipartFile` 接收文件、回显文件名与大小
- 业务异常 `TodoException` 用控制器内联 `@ExceptionHandler` 转 400 + 业务码（全局统一是练习 5 的主题）
- 测试：`@WebMvcTest` + MockMvc 六用例（创建、列表、完成、删除、title 校验 400、文件上传），`@BeforeEach` 重置内存表保证 id 断言确定

**验收**：参考实现实测 `Tests run: 6, Failures: 0, Errors: 0`（pom 复制 ex04 的，含离线版本仲裁）；能对比练习 1 与本题代码量差异，说出框架接管了哪些事（参数绑定、JSON、状态码、请求体解析）。

## 练习 5：登录注册 + JWT + 全局异常处理（★★★）

**目标**：把前四题串成完整闭环——注册（校验 + 落内存表）→ 登录（验密码 + 签发 JWT）→ 受保护接口（拦截器验签），全局异常处理统一收口。
**要求**：

- 注册 `POST /api/auth/register`：username 非空、password ≥6 位（否则 400 + 40000）；用户名重复 409 + 40900；成功返回 token
- 登录 `POST /api/auth/login`：密码错 401 + 40100；成功返回 token
- `GET /api/me`：`HandlerInterceptor` 从 `Authorization: Bearer <token>` 验签，无/坏 token 401 + 40101，OPTIONS 预检放行
- `@RestControllerAdvice` 全局异常处理：四种业务异常 + 兜底 500，全部返回统一响应壳；**advice 类与异常类都要 public**（包私有会被组件扫描发现但 advice 代理/反射会踩坑）
- 测试：`@SpringBootTest` + MockMvc 六用例（注册成功、重复用户名 409、登录成功、密码错 401、带 token 访问 me、无 token 401）；每个测试用独立用户名避免共享内存表耦合

**验收**：参考实现实测 `Tests run: 6, Failures: 0, Errors: 0`（pom 复制 ex06 的，含 jjwt 与离线版本仲裁）；能说清「认证（你是谁，JWT 验签）和授权（你能干什么，ph15 Spring Security）的区别」。
