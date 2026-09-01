# Java Web 后端开发阶段

> 面向企业级后端、微服务方向，本阶段把「能写 Java 程序」升级为「能写对外服务的 HTTP API」——从 HTTP/Servlet/Tomcat 的底层机制出发，掌握 REST API 与 JSON、参数校验与 JWT 认证、CORS 跨域、全局异常处理与日志、API 文档，最后用 Spring MVC / Spring Boot 把前面的心智全部框架化。

## 1. 概述

本阶段是整个 Java 学习路线的转折点：ph01~ph13 学的都是「单机程序怎么写得对、快、稳」（语法、集合、并发、JVM、构建、测试、数据库），本阶段把它们接进 **HTTP 服务**——别人（前端、车辆、其他服务）通过 URL 调用你的 Java 代码。目标（roadmap 第 14 节）：**能用 Java 写后端 API 服务**。从「HTTP 请求进来后发生了什么」的底层链路讲起（Servlet/Tomcat 是 Spring Boot 的底子），再讲 REST/JSON 的接口设计，接着是参数校验、JWT、CORS 这三个「接口安全与互操作」主题，然后是全局异常处理、日志、API 文档这三个「工程质量」主题，最后落到 Spring MVC / Spring Boot——前面手写的一切，框架替你做了大半。

| 核心维度 | 覆盖内容 |
|----------|---------|
| HTTP 与 Web 基础 | HTTP 方法/状态码/请求响应结构、URL 与查询参数、Content-Type 与 JSON、`com.sun.net.httpserver` 手写服务（零依赖实测） |
| Servlet 与 Tomcat | Servlet 生命周期、`doGet/doPost`、`@WebServlet` 注解与映射、嵌入式 Tomcat 启动（Spring Boot 内嵌 Tomcat 的底层机制） |
| REST API 与 JSON | 资源路径设计、方法语义（GET/POST/PATCH/DELETE）、状态码语义（201/204/400/404/405）、统一响应结构、Jackson 序列化 |
| 参数校验 | 手写校验 vs 声明式 `@Valid`（`@NotBlank/@Email/@Size/@Pattern/@Min/@Max`）、校验失败响应 |
| JWT 认证 | 手写 HMAC-SHA256 签名（理解机制）→ jjwt 库（生产用法）、签发/验签/过期/篡改检测、HandlerInterceptor 鉴权 |
| CORS | 同源策略、预检 OPTIONS、`Access-Control-Allow-Origin/Methods/Headers`、全局 CORS 配置 |
| 全局异常处理与日志 | `@RestControllerAdvice` + `@ExceptionHandler`、业务码与 HTTP 状态码分工、SLF4J 结构化日志 |
| API 文档 | springdoc-openapi 自动生成 OpenAPI 3 文档 + Swagger UI |
| Spring MVC / Spring Boot | `@RestController` 注解体系、`@RequestMapping/@GetMapping/@PathVariable/@RequestBody`、内嵌 Tomcat 自动配置、starter 依赖、`spring-boot:run` |

这个阶段只涉及 **Web 层本身**（HTTP 协议、Servlet 容器、REST 设计、框架注解），**不涉及 Spring 的 IOC/DI、Bean 生命周期、AOP、事务管理等容器机制**（那是 ph15 Spring 全家桶阶段的内容，roadmap 第 15 节，目录待建）、**不涉及微服务架构、服务注册发现、网关与熔断**（ph16 微服务与分布式阶段，roadmap 第 16 节，目录待建）、**不涉及消息队列与搜索中间件**（ph17 消息队列与搜索阶段，roadmap 第 17 节，目录待建）、**不涉及缓存穿透/击穿/雪崩、限流等高并发架构**（ph18 缓存与高并发阶段，roadmap 第 18 节，目录待建）、**不涉及服务的部署运维**（Docker/CI/CD，ph19 DevOps 与部署阶段，roadmap 第 19 节，目录待建）、**不涉及网络编程深入与 Netty**（ph20 高级 Java 阶段，roadmap 第 20 节，目录待建）。本阶段承接 [ph13 数据库阶段](../ph13-database/13-database.md)——那里讲透了「数据层怎么写得对」，本阶段把它们包成「别人能调的接口」，`VehicleStore` 之类的数据层接口形状保持不变、实现可平移。

## 2. 来源与演变

**HTTP**（HyperText Transfer Protocol）1991 年由 Tim Berners-Lee 在 CERN 提出（HTTP/0.9 只有 GET 一个方法），1996 年 HTTP/1.0（RFC 1945）、1997 年 HTTP/1.1（RFC 2068，持久连接、Host 头、方法扩展）定型为 Web 事实协议，2015 年 HTTP/2（多路复用、头部压缩）、2022 年 HTTP/3（基于 QUIC/UDP）持续演进。**REST**（Representational State Transfer）2000 年由 Roy Fielding 在博士论文中提出——不是协议而是架构风格：资源用 URL 标识、HTTP 方法表达操作、无状态、统一接口，后来成为 Web API 的事实设计标准。**JSON** 2001 年由 Douglas Crockford 从 JavaScript 对象字面量提炼而来，2006 年 RFC 4627 标准化；比 XML 轻、比二进制可读，2010 年代起成为 Web API 的默认数据格式。

**Servlet** 1997 年随 Java Servlet 规范诞生（Servlet 1.0 由 Sun 提出，1998 年 2.1 加入 `web.xml`），是 Java 处理 HTTP 请求的**官方标准 API**：容器（Tomcat/Jetty）负责 HTTP 协议解析、Servlet 生命周期管理，开发者只写业务处理。**Tomcat** 1999 年由 Sun 捐赠的 Java Web Server 代码演化而来，2005 年成为 Apache 顶级项目，长期是 Servlet 容器的事实标准。Servlet 规范演进：2.3（2001，Filter 过滤器）、2.5（2006，web.xml 配置为主，注解尚不存在）、3.0（2009，JSR 315，`@WebServlet`/`@WebFilter` 注解 + 异步请求）、3.1（2013，非阻塞 IO）、4.0（2017，HTTP/2）、5.0（2020，jakarta.* 命名空间，Eclipse 接管后的分水岭）、6.0（2022，Tomcat 10.1，本阶段基线）。

**Spring MVC** 2004 年随 Spring 1.0 发布（Spring 1.2 是 2005 年的后续版本；Rod Johnson 的《Expert One-on-One J2EE Design and Development》催生 Spring），把 Servlet API 包成 `DispatcherServlet` 分发 + 注解控制器（`@Controller`/`@RequestMapping` 2007 年 Spring 2.5 加入），让「写 Web 层」从手写 Servlet 变成写 POJO 方法。**Spring Boot** 2014 年由 Pivotal（Phil Webb 主导）发布，口号「Just Run」：约定大于配置、自动配置（`@EnableAutoConfiguration` 按 classpath 推断）、starter 依赖聚合、内嵌容器——把 Spring 工程的搭建成本从「配置几天」压到「一个注解」。**springdoc-openapi** 2019 年发布，用注解自动生成 OpenAPI 3 文档，省去手写 API 文档。

| 版本/里程碑 | 年份 | 主要变化 |
|-----------|------|---------|
| HTTP/1.1 | 1997 | 持久连接、Host 头、方法扩展——Web 协议定型 |
| Servlet 1.0 | 1997 | Java 处理 HTTP 的标准 API（容器 + 生命周期） |
| REST（论文） | 2000 | 资源 + 方法 + 无状态的架构风格，Web API 设计标准 |
| JSON（RFC 4627） | 2006 | Web API 默认数据格式（比 XML 轻、比二进制可读） |
| Servlet 2.5 | 2006 | web.xml 配置演进（注解尚不存在） |
| Servlet 3.0 | 2009 | `@WebServlet`/`@WebFilter` 注解 + 异步请求（本阶段注解映射的起点） |
| Spring MVC | 2004 | `DispatcherServlet` + 注解控制器，手写 Servlet 的框架化 |
| Spring Boot 1.0 | 2014 | 自动配置 + starter + 内嵌容器，「Just Run」 |
| Servlet 5.0 | 2020 | `jakarta.*` 命名空间（Eclipse 接管，包名分水岭） |
| Servlet 6.0 | 2022 | Tomcat 10.1 基线，本阶段嵌入式 Tomcat 实测版本 |
| Spring Boot 3.x | 2022 | 基于 Spring 6 + jakarta 命名空间，要求 Java 17+（本阶段基线） |
| springdoc-openapi | 2019 | 注解自动生成 OpenAPI 3 文档 + Swagger UI |

本文示例以 **OpenJDK 17.0.18 + Spring Boot 3.3.0 + Tomcat 10.1.31 + jjwt 0.12.5 + springdoc-openapi 2.3.0** 为基线（验证工具链：`javac -version` → 17.0.18、`mvn -version` → 3.9.12；配套 **Hibernate Validator 8.0.1.Final、Jackson 2.17.2** 由 starter 传递引入（仅 ex06/project 的 `jackson-dataformat-yaml` 因离线缓存压到 2.15.3，见各 pom 的「离线版本仲裁」注释），全部本机实测通过；**Spring Boot 3.3.0 与本机缓存完全兼容，全部示例 `mvn test` + `spring-boot:run` + curl 实测**——本阶段 Web 框架可用性策略见第 6 章说明）。本机 Maven 用 `mvn -o` 离线模式，依赖/插件取自本地仓库缓存（沙箱禁止写 `~/.m2`，用 `-Dmaven.repo.local=/tmp/m2clone` 指向可写目录的克隆；正常联网环境直接 `mvn test` 即可）。HTTP 与 Servlet 的 API 自 Servlet 3.0 起高度稳定，本阶段学的 Servlet 心智（请求/响应/生命周期）在 Spring Boot 里只是被框架接管而不是被推翻——这是本阶段「先讲底层再讲框架」的原因。

## 3. 语法与参数

### 3.1 HTTP 基础：方法、状态码与请求响应

HTTP 是无状态请求-响应协议：客户端发请求（方法 + URL + 头 + 可选 body），服务端回响应（状态码 + 头 + body）。**方法**表达操作语义——GET 读、POST 建、PATCH 局部改、PUT 整体替换、DELETE 删、OPTIONS 探测（CORS 预检用）；**状态码**表达结果语义——2xx 成功（200 OK / 201 Created / 204 No Content）、3xx 重定向、4xx 客户端错（400 参数错 / 401 未认证 / 403 无权限 / 404 不存在 / 405 方法不支持 / 409 冲突）、5xx 服务端错（500 内部错误 / 503 不可用）。

> ⚠️ **状态码是接口契约的一部分**：前端 switch 状态码决定 UI 分支，后端乱用（如一律 200 + body 里放错误）会让调用方无从判断。REST 语义化状态码 = 用 201 表示「创建成功」、404 表示「资源不存在」——本阶段 examples/ex01 实测了 200/201/400/404/405 五种（204「删除成功」的零响应体写法由 exercises/sol-01 的 DELETE 演示）。

```java
// examples/ex01-jdk-httpserver —— 纯 JDK HttpServer 起服务，零依赖实测
HttpServer server = HttpServer.create(new InetSocketAddress(18080), 0);
var ctx = server.createContext("/api");
ctx.setHandler(ex -> {                       // HttpExchange = 一次请求/响应的完整上下文
    String path = ex.getRequestURI().getPath();
    String method = ex.getRequestMethod();
    // 路由分发：路径 + 方法决定动作（「Controller 不写复杂业务」的最小雏形）
    // 读请求体：ex.getRequestBody().readAllBytes()
    // 写响应：ex.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8")
    //        ex.sendResponseHeaders(200, body.length) + ex.getResponseBody()
});
server.start();
```

**关键概念：无状态与幂等**。HTTP 每个请求独立（服务端不记「上次是谁」），所以「谁在调」要靠每次请求带上的凭证（Cookie/Token，本阶段讲 JWT）——这是 REST 与有状态 RPC 的本质区别。幂等（GET/PUT/DELETE 重复执行结果一致，POST 不保证）是接口设计的重要约束，ph16 微服务阶段的重试依赖它。

### 3.2 Servlet 与 Tomcat：请求进入 Java 的第一站

Servlet 是 Java 处理 HTTP 的标准 API：容器（Tomcat）解析 HTTP 报文、按 URL 匹配 Servlet、管理其生命周期（init → service → destroy），开发者继承 `HttpServlet` 覆写 `doGet/doPost` 等方法处理业务。

```java
// examples/ex02-servlet-tomcat —— 手写 Servlet + 嵌入式 Tomcat，实测
@WebServlet("/echo/*")                       // 注解映射 URL 模式（等效 web.xml 的 <servlet-mapping>）
public final class EchoServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        String path = req.getPathInfo();     // /hello（去掉前缀 /echo）
        String name = req.getParameter("name"); // 查询参数 ?name=Alice
        resp.setStatus(200);
        resp.setContentType("application/json; charset=UTF-8");
        resp.getWriter().write("{\"path\":\"" + path + "\",\"name\":\"" + name + "\"}");
    }
}
// 嵌入式启动（Spring Boot 内嵌 Tomcat 的底层机制，main 里直接 new Tomcat()）：
Tomcat tomcat = new Tomcat();
tomcat.setPort(18081);
Context ctx = tomcat.addContext("", new File(".").getAbsolutePath());
Tomcat.addServlet(ctx, "echo", new EchoServlet());
ctx.addServletMappingDecoded("/echo/*", "echo");
tomcat.start();
```

**Servlet 生命周期**：容器启动时加载 → `init()`（一次）→ 每个请求 `service()` 分发到对应 doXxx 方法 → 关闭时 `destroy()`。**请求处理链**：TCP 连接 → Connector 解析 HTTP → Engine/Host/Context 逐层匹配 → Servlet → 响应写回。理解这条链是理解 Spring Boot 内嵌 Tomcat 的前提——框架只是把「你写 Servlet 注册进容器」变成「你写 @RestController，框架替你注册」。

> 本阶段只用手写 Servlet 理解机制，**Filter/Listener 的完整体系与 Servlet 3.0 异步、非阻塞 IO 属于 ph20 高级 Java 阶段**（Netty 与高性能网络编程），这里只需理解「请求-响应-生命周期」三个最小认知。

### 3.3 REST API 与 JSON：资源设计与统一响应

REST 把「数据」建模为**资源**，URL 标识资源、方法表达操作：`GET /api/users` 读列表、`POST /api/users` 创建、`GET /api/users/{id}` 读单个、`PATCH /api/users/{id}` 局部更新、`DELETE /api/users/{id}` 删除。路径参数 `{id}` 与查询参数（`?limit=20`）分工：路径参数定位资源，查询参数筛选/分页。

**JSON 序列化**是 REST 的数据载体：Java 对象 ↔ JSON 文本。手写版（ex01 的 MiniJson）让你看清「对象怎么变成字符串」；生产用 **Jackson**（Spring Boot 内建，starter-web 自动注册）：`@RequestBody` 把 JSON 反序列化成 Java 对象、`@RestController` 把返回值序列化成 JSON——**序列化是 ph07 IO 阶段「字节↔字符」心知的框架化**。

```java
// examples/ex04-spring-boot-rest —— Spring Boot REST + 统一响应，实测
@RestController                          // = @Controller + @ResponseBody：返回值直接序列化为 JSON
@RequestMapping("/api")                  // 类级前缀
public class HelloController {
    @GetMapping("/ping")
    public ApiResponse<Object> ping() {  // 统一响应壳：code/message/data
        return ApiResponse.ok(Map.of("message", "pong"));
    }
    @GetMapping("/echo/{name}")          // 路径参数
    public ApiResponse<Object> echo(@PathVariable String name) {
        return ApiResponse.ok(Map.of("echo", name));
    }
}
```

**统一响应结构**（roadmap 必会概念「接口响应结构要统一」）：所有接口返回同一形状 `{code, message, data}`——`code` 是业务错误码（0 成功，4xxxx 客户端错，5xxxx 服务端错），`message` 给人看，`data` 给程序用。**业务码与 HTTP 状态码分工**：HTTP 状态码表达「传输层语义」（这次请求成没成），业务码表达「业务语义」（哪一步错了）——前端按 code 分支业务逻辑、按 HTTP 状态码分支网络/权限逻辑。

### 3.4 参数校验：手写 if 与声明式注解

「参数校验」是接口安全的底线——不校验的接口会被脏数据打穿（空串、超长、非法格式）。两条路：**手写 if**（ex01/ex03 的做法，逻辑直观但代码散）与**声明式注解**（`@Valid` + Bean Validation，规则和数据模型放一起，Spring Boot 用 Hibernate Validator 实现）。

```java
// examples/ex05-spring-boot-validation-error —— @Valid 声明式校验，实测
public record CreateUserRequest(
        @NotBlank(message = "name 不能为空")        // 空串也拒绝
        @Size(max = 20, message = "name 最长 20 字符")
        String name,
        @NotBlank(message = "email 不能为空")
        @Email(message = "email 格式不正确")
        String email) {}

@PostMapping("/api/users")
public ApiResponse<User> create(@Valid @RequestBody CreateUserRequest req) { ... }
// 校验失败抛 MethodArgumentNotValidException → 由 @RestControllerAdvice 统一转 400 + 业务码
```

**分层心智**：Controller 的 `@Valid` 拦「输入形状」（快速失败、报错友好），Service 手工校验兜底「业务规则」（跨字段约束、依赖数据的状态检查）——与 ph13 数据库阶段「Java 校验 + 数据库约束分层兜底」同一思想。实测（ex05）：`{"name":"  ","email":"bad"}` → 400 `{"code":40001,"message":"参数校验失败","data":{"email":"email 格式不正确","name":"name 不能为空"}}`。

### 3.5 JWT 认证：手写签名到 jjwt 库

**JWT**（JSON Web Token）是无状态认证的载体：服务端登录成功签发一个 token，客户端每次请求带上，服务端验签即可——**不查 session、不占服务端内存**（对比 Cookie-Session 方案）。结构是 `Header.Payload.Signature` 三段 base64url 以 `.` 连接：Header 声明算法（`{"alg":"HS256","typ":"JWT"}`）、Payload 放身份信息（`sub` 用户、`exp` 过期时间等 claim）、Signature 是签名（防篡改）。

```java
// examples/ex03-jwt-handmade —— 手写 HMAC-SHA256，实测；签名对象是完整 header.payload 字符串
String signingInput = header + "." + payload;
String signature = b64(hmacSha256(secret, signingInput));  // HmacSHA256
String token = signingInput + "." + signature;
// 验签 = 重算签名比对 + exp 过期检查；篡改 payload 后签名不匹配 → 拒绝
```

**为什么篡改会被识破**：签名覆盖完整的前两段字符串，任何一位改动都会导致重算的签名不一致；`exp` 让过期 token 失效。**常量时间比较**（`constantTimeEquals`）防止通过比较耗时侧信道泄露签名信息。生产用 jjwt 库（ex06 实测）：`Jwts.builder().subject(u).expiration(exp).signWith(key).compact()` 签发、`Jwts.parser().verifyWith(key).build().parseSignedClaims(token)` 验签，算法/密钥/过期由库管理。**认证与授权分清**（roadmap 必会概念）：JWT 验签只回答「你是谁」（认证），「你能干什么」（授权，如 admin 才能删）是 ph15 Spring 全家桶阶段的 Spring Security 内容。

### 3.6 CORS：跨域资源共享

浏览器**同源策略**：JS 只能读取同源（协议+域名+端口）响应，跨域请求默认被浏览器拦。**CORS**（Cross-Origin Resource Sharing）是服务器显式声明「我允许哪些源读我的响应」：响应头 `Access-Control-Allow-Origin: <源>`、`Access-Control-Allow-Methods`、`Access-Control-Allow-Headers`。复杂请求（自定义头、非简单方法）先发 **OPTIONS 预检**，服务器回应许后浏览器才发正式请求。

```java
// examples/ex06 —— 全局 CORS 配置（实测 OPTIONS 预检返回 Allow-Origin/Methods/Headers）
registry.addMapping("/api/**")
        .allowedOrigins("http://localhost:5173")   // 前端开发服务器
        .allowedMethods("GET", "POST", "OPTIONS")
        .allowedHeaders("*");
```

> ⚠️ **带凭证（cookie）时不能用 `*`**：`Access-Control-Allow-Origin: *` 表示任意源，浏览器规定带 `credentials` 时不允许通配源、必须显式列出。前端发凭证跨域是安全边界的重灾区——本阶段先掌握「无凭证 JSON API 的 CORS」，凭证态交给 ph15 的 Spring Security。

### 3.7 全局异常处理、日志与统一错误响应

没有全局异常处理时，校验失败返回 Spring 默认错误 JSON、未捕获异常直接 500 裸堆栈——响应结构不统一，前端没法写。**`@RestControllerAdvice`** 拦截所有 Controller 抛出的异常，按类型分发到 `@ExceptionHandler` 方法：

```java
// examples/ex05 —— @RestControllerAdvice 全局异常处理，实测
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(MethodArgumentNotValidException.class)  // 校验失败
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Map<String, String>> handleValidation(MethodArgumentNotValidException ex) {
        // 字段错误收集进 Map → 400 + 业务码 40001
    }
    @ExceptionHandler(Exception.class)                        // 兜底
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleUnexpected(Exception ex) {
        log.error("unhandled_exception", ex);                 // 兜底必须记 ERROR 日志
        return ApiResponse.error(50000, "服务器内部错误");
    }
}
```

**日志**用 SLF4J（Spring Boot 默认 Logback 实现）：`LoggerFactory.getLogger(Xxx.class)` 拿 logger，`log.info("create_user id={} name={}", id, name)` 占位符写法避免字符串拼接、生产可切换实现（Log4j2 等）。日志分级：INFO 记录业务事件、WARN 记录可恢复异常、ERROR 记录需要人工介入的错误——**兜底异常处理器必须记 ERROR，否则线上查不到根因**（roadmap 必会概念「全局异常处理提升一致性」的落点）。

### 3.8 API 文档：springdoc-openapi 与 Swagger UI

接口文档与代码同步是工程质量的硬指标。**springdoc-openapi** 扫描 `@RestController` 自动生成 OpenAPI 3 文档（`/v3/api-docs` 返回 JSON、`/swagger-ui/index.html` 提供可视化页面），注解可补充描述（`@Operation`/`@Parameter`）。实测（ex06）：`/v3/api-docs` 自动列出全部 paths，Swagger UI 可直接发请求调试——**文档不是手写的，是代码的投影**。

### 3.9 Spring MVC / Spring Boot：注解体系与自动配置

**Spring MVC** 的注解体系是「手写 Servlet」的框架化：`@RestController`（控制器 + JSON）、`@RequestMapping`（类级前缀）/`@GetMapping/@PostMapping/@PatchMapping/@DeleteMapping`（方法级）、`@PathVariable`（路径参数）、`@RequestParam`（查询参数）、`@RequestBody`（JSON 反序列化）、`@Valid`（触发校验）。**Spring Boot** 在此基础上加了自动配置：`@SpringBootApplication` 启动时按 classpath 推断（有 spring-webmvc 就配 DispatcherServlet、有 tomcat-embed 就内嵌 Tomcat、有 jackson 就注册序列化器），starter 依赖（`spring-boot-starter-web` 一个坐标带齐 web 全家）把「配几天」压成「一个注解」。

```java
// examples/ex04 —— Spring Boot 最小服务，实测 mvn test + spring-boot:run + curl
@SpringBootApplication          // = @Configuration + @EnableAutoConfiguration + @ComponentScan
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);   // 内嵌 Tomcat 起在 server.port（application.properties）
    }
}
```

**三层分工**（roadmap 必会概念「Controller 不应写复杂业务」）：Controller 只做 HTTP 语义（路径/参数/请求体/状态码），Service 做业务规则，Store/Repository 做数据访问——project/ 的 `VehicleController → VehicleService → VehicleStore` 是这条分工的完整落地。

## 4. 底层原理

### 4.1 一次 HTTP 请求的完整旅程：从 TCP 到响应

```text
浏览器 ──TCP 连接──▶ Tomcat Connector ──解析 HTTP 报文──▶ Engine/Host/Context 匹配
   ▲                                                            │
   │                                                            ▼
   └──────◀── HTTP 响应 ────── DispatcherServlet/Filter ──▶ Servlet(doGet/doPost)
```

连接器（Connector）把 TCP 字节流解析成 HTTP 请求对象（方法/URL/头/body），容器逐层匹配（Engine→Host→Context→Servlet）后调用 Servlet；Servlet 写响应对象，连接器序列化回客户端。**每个请求一个线程**是 Servlet 容器的传统模型——线程池由容器管理（对比 ph09 的 ExecutorService），这个「一请求一线程」模型正是虚拟线程（ph09 讲过）最受益的场景。理解这条链就明白：Spring Boot 的 `@RestController` 方法最终也是被容器线程调用的普通方法，框架只是替你完成了「URL 匹配 + 参数绑定 + 序列化」。

### 4.2 Spring MVC 的 DispatcherServlet 分发

Spring MVC 用**前端控制器模式**：所有请求先进 `DispatcherServlet`，它按 `HandlerMapping` 找到对应控制器方法（`@GetMapping("/ping")` → `HelloController.ping`），`HandlerAdapter` 负责调用并绑定参数（路径参数/查询参数/请求体反序列化），返回值经 `HttpMessageConverter`（Jackson）序列化写响应。**拦截器**（`HandlerInterceptor`，本阶段 ex06/project 用于 JWT 鉴权）在控制器执行前/后/完成后挂钩子，是「横切关注点」的 MVC 层实现——对比 ex01 手写 HttpServer 的 `Filter`，同一思想、不同实现层。

### 4.3 JWT 的签名机制：为什么篡改必被识破

HMAC-SHA256 是**带密钥的哈希**：`signature = HMAC-SHA256(header.payload, secret)`。验签方用同一密钥重算并比对——比对失败说明内容被改过（攻击者没有密钥改不出合法签名）。**重点：签名覆盖 header 和 payload 两个部分**，所以 header 里声称的算法也不能被换成 `none`（部分老库的经典漏洞——攻击者把 alg 改成 none 逃逸验签）。本阶段手写版把「签了什么」摊开给你看，jjwt 库（ex06）把「防止 alg=none、过期检查、密钥管理」都做掉了——**理解机制后敢用库，是安全主题的正确姿势**。

### 4.4 Spring Boot 自动配置：约定优于配置的引擎

`@EnableAutoConfiguration` 启动时扫描 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`，按「条件注解」决定配什么：classpath 有 `spring-webmvc` → 配 `DispatcherServlet`；有 `tomcat-embed-core` → 配内嵌 Tomcat；有 `jackson-databind` → 配 `MappingJackson2HttpMessageConverter`。**配置的默认值**（端口 8080、JSON 序列化规则）来自 `application.properties/yml`。这就是「为什么只引一个 starter 就能跑」的答案——自动配置按依赖推断并给默认值，你要改的才写配置（对比 ph11 构建工具的「依赖管理」心智：starter 是「依赖 + 默认配置」的聚合）。

## 5. 使用场景

- **对外数据服务**：把业务能力暴露为 HTTP API——本阶段 project/ 的车辆数据上报 API 是车联网方向的直接落地（roadmap 推荐项目），ph13 的存储层可平移进 `VehicleStore`。
- **前后端分离**：REST API + JSON 是前后端分离的事实标准——前端（React/Vue，本阶段用 CORS 允许其跨域调用）只认 `{code, message, data}` 一个形状，这正是「统一响应结构」为什么是必会概念。
- **什么时候不用 Spring Boot**：极简单的内部工具或单机演示（ex01 的 HttpServer 就够）、对启动体积/延迟极敏感的边缘场景（可换 Quarkus/Micronaut，ph15 对比）。本阶段学 Spring Boot 是为了生态（ph15 全家桶、ph16 微服务都建立在它上面）。
- **与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：Java 的 Servlet/Spring 是「容器托管生命周期」的经典模型（回调 + 注解）；Go 的标准库 `net/http` 是「函数式 Handler」、显式中间件链；Python 的 FastAPI 用装饰器 + 类型注解自动生成 OpenAPI——三种语言解决同一问题（路由/参数/文档）的不同风格：Java 注解声明式最重、Go 显式最小、Python 双注解。Rust 的 axum/actix 走「tower 中间件栈」，与 Go 更近。

## 6. 代码示例

> 完整可运行版在 [`examples/`](./examples/)（每个示例带验证命令与实测数字）。本阶段**Web 框架可用性策略**：本机离线缓存完整覆盖 Spring Boot 3.3.0 全链路（starter-web/validation/test、springdoc、jjwt、嵌入式 Tomcat），因此 **Spring Boot 示例全部实测**；ex01/ex03 纯 JDK 零依赖同样实测。

```java
// examples/ex04-spring-boot-rest/src/main/java/com/example/HelloController.java —— Spring Boot REST（已验证）
// 验证环境：OpenJDK 17.0.18 + Spring Boot 3.3.0，测试命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 实测：Tests run: 3；GET /api/ping → {"code":0,"message":"ok","data":{"message":"pong"}}
@RestController
@RequestMapping("/api")
public class HelloController {
    @GetMapping("/ping")
    public ApiResponse<Object> ping() {
        return ApiResponse.ok(java.util.Map.of("message", "pong"));
    }
}
```

### 示例 1：纯 JDK HttpServer 手写 REST（[`examples/ex01-jdk-httpserver/`](./examples/ex01-jdk-httpserver/)）

零依赖演示 HTTP 服务最小闭环：路由分发、JSON 手工解析、状态码（200/201/400/404/405）、CORS 头、日志中间件。**实测**：8 条 curl 用例全过（`GET /api/ping` → 200 pong、`POST /api/users` → 201、缺 name → 400、`GET /api/users/999` → 404、`PUT /api/users` → 405）。

### 示例 2：嵌入式 Tomcat + 手写 Servlet（[`examples/ex02-servlet-tomcat/`](./examples/ex02-servlet-tomcat/)）

`@WebServlet` 注解 + `doGet/doPost` + 路径/查询参数 + 嵌入式 `new Tomcat()` 启动（Spring Boot 内嵌 Tomcat 的底层机制）。**实测**：`GET /echo/hello?name=Alice` → 200、`POST` → 200 回显、`/echo/other` → 404。

### 示例 3：手写 JWT（HMAC-SHA256）（[`examples/ex03-jwt-handmade/`](./examples/ex03-jwt-handmade/)）

base64url + MAC 签名/验签/过期/篡改检测，零依赖。**实测**：合法 token 验签 true、篡改 false、过期 false、非法 false。

### 示例 4：Spring Boot REST + 统一响应（[`examples/ex04-spring-boot-rest/`](./examples/ex04-spring-boot-rest/)）

`@RestController` + `ApiResponse` 统一响应 + `@PathVariable` + MockMvc 测试。**实测**：`mvn test` → Tests run: 3；curl 三例（ping/echo/中文路径参数）全过。

### 示例 5：参数校验 + 全局异常 + 日志（[`examples/ex05-spring-boot-validation-error/`](./examples/ex05-spring-boot-validation-error/)）

`@Valid` 声明式校验 + `@RestControllerAdvice` 全局异常 + SLF4J 日志 + 统一响应。**实测**：`mvn test` → Tests run: 4；curl 校验失败 → 400 `{"code":40001,...}`。

### 示例 6：JWT + CORS + OpenAPI（[`examples/ex06-spring-boot-jwt-cors-openapi/`](./examples/ex06-spring-boot-jwt-cors-openapi/)）

jjwt 登录鉴权 + HandlerInterceptor + 全局 CORS + springdoc OpenAPI 文档。**实测**：`mvn test` → Tests run: 5；curl 7 项全过（登录发 token、无 token 401、带 token 200、CORS 预检、`/v3/api-docs`、`/swagger-ui`）。

## 7. 总结

### 关键要点

- **请求旅程**：TCP → Connector 解析 → 容器匹配 → Servlet/Controller → 响应；Spring Boot 只是把「手写 Servlet 注册」变成「写 @RestController 注解」
- **REST 语义**：URL 标识资源、方法表达操作、状态码表达结果——201 创建 / 204 删除 / 400 参数错 / 404 不存在 / 405 方法不支持；统一响应 `{code, message, data}` 是接口契约
- **参数校验双层**：`@Valid` 声明式拦「输入形状」（快速失败），Service 校验兜底「业务规则」；`@RestControllerAdvice` 统一转错误响应
- **JWT 机制**：Signature = HMAC-SHA256(header.payload, secret)，覆盖完整前两段所以篡改必被识破；`exp` 管过期；手写理解机制、库管生产
- **CORS**：同源策略是浏览器的，CORS 头是服务器开的门；预检 OPTIONS、带凭证不能用 `*`
- **全局异常 + 日志 + 文档**：异常处理一致性靠 `@RestControllerAdvice` 收口、兜底必须记 ERROR 日志、springdoc 让文档是代码的投影
- **Controller 不写业务**：Controller（HTTP 语义）→ Service（业务规则）→ Store（数据访问）三层分工，是 roadmap 必会概念的直接落地

### 阶段验收清单

- [ ] 能说清一次 HTTP 请求从 TCP 到 Controller 方法的完整旅程（Servlet 容器在其中的角色）
- [ ] 能用手写 HttpServer 或 Spring Boot 写一个 REST API，并用语义化状态码（201/204/400/404/405）表达结果
- [ ] 能用 `@Valid` 声明式校验 + `@RestControllerAdvice` 全局异常，让所有接口返回统一响应结构
- [ ] 能解释 JWT 的签名机制（为什么篡改必被识破）、用 jjwt 实现登录鉴权（签发 + 拦截器验签）
- [ ] 能配置 CORS 并解释预检流程；能说清「认证（JWT 验签）和授权（ph15 Spring Security）的区别」
- [ ] 能起 Spring Boot 服务、看 SLF4J 日志、用 springdoc 自动生成 API 文档
- [ ] 能说出「Controller 不应写复杂业务」，并按 Controller/Service/Store 三层组织接口代码

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：纯 JDK Todo API（练习 1）→ 手写校验器（练习 2）→ 手写 JWT（练习 3）→ Spring Boot Todo + 文件上传 + MockMvc（练习 4）→ 登录注册 + JWT + 全局异常（练习 5，把前四题串成闭环）。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**车辆数据上报 API**（roadmap 推荐项目）——REST 上报/查询 + JWT 鉴权 + 声明式校验双层 + 全局异常 + CORS + springdoc 文档，`mvn test` 实测 13 用例全过。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`mvn test` 13 用例 + curl 验收标准）

### 下一阶段

**ph15+（roadmap 第 15 节，目录待建）——本阶段是当前已建目录的最后一个阶段**：后续可深入 **Spring 全家桶** 方向——本阶段的 `@RestController` 只是 Spring 的冰山一角，ph15 将讲透 Spring 的核心机制：IOC/DI 容器与 Bean 生命周期（为什么 `@Autowired`/构造器注入能把 `VehicleService` 塞进 `VehicleController`）、AOP 与事务管理、Spring Security 授权（把本阶段的「认证」升级为「认证 + 授权」）、Spring Boot 自动配置原理与 Actuator 监控。该阶段目录尚未创建，届时以 roadmap 第 15 节为准，本阶段不再向前引用不存在的文件。
