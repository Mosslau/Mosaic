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

这个阶段只涉及 **Web 层本身**（HTTP 协议、Servlet 容器、REST 设计、框架注解），**不涉及 Spring 的 IOC/DI、Bean 生命周期、AOP、事务管理等容器机制**（那是 [ph15 Spring 全家桶阶段](../ph15-spring-family/15-spring-family.md)的内容，roadmap 第 15 节）、**不涉及微服务架构、服务注册发现、网关与熔断**（ph16 微服务与分布式阶段，roadmap 第 16 节，目录待建）、**不涉及消息队列与搜索中间件**（[ph17 消息队列与搜索阶段](../ph17-mq-search/17-mq-search.md)，roadmap 第 17 节）、**不涉及缓存穿透/击穿/雪崩、限流等高并发架构**（[ph18 缓存与高并发阶段](../ph18-cache-concurrency/18-cache-concurrency.md)，roadmap 第 18 节）、**不涉及服务的部署运维**（Docker/CI/CD，[ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)）、**不涉及网络编程深入与 Netty**（[ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)）。本阶段承接 [ph13 数据库阶段](../ph13-database/13-database.md)——那里讲透了「数据层怎么写得对」，本阶段把它们包成「别人能调的接口」，`VehicleStore` 之类的数据层接口形状保持不变、实现可平移。

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

**报文结构**：HTTP/1.1 报文是纯文本，分「起始行 + 头 + 空行 + body」四段——空行（CRLF）是头与 body 的唯一分界，Content-Length 告诉对方 body 读到哪为止：

```text
POST /api/users HTTP/1.1              ← 请求行：方法 + 路径 + 协议版本
Host: localhost:18080                 ← 请求头（Host 是 HTTP/1.1 唯一必需头）
Content-Type: application/json        ← body 的格式声明
Content-Length: 30                    ← body 的字节数（读 body 的终止依据）
Authorization: Bearer eyJhbGciOi...   ← 认证凭证（本阶段 3.5 的 JWT）
                                      ← 空行：头与 body 的分界
{"name":"Alice","email":"a@b.cn"}     ← 请求体（可选，GET/DELETE 一般没有）

HTTP/1.1 201 Created                  ← 状态行：协议版本 + 状态码 + 原因短语
Content-Type: application/json; charset=UTF-8
Content-Length: 41
Location: /api/users/42               ← 201 时指回新资源的 URL
                                      ← 空行
{"code":0,"message":"ok","data":{}}   ← 响应体
```

常见请求头/响应头对照（抓包或 curl -v 时逐项都能对上）：

| 常见请求头 | 作用 |
|-----------|------|
| Host | 目标主机与端口，HTTP/1.1 必需——同一 IP 上多个站点靠它分流（虚拟主机） |
| Content-Type | 请求体格式（application/json / application/x-www-form-urlencoded 等） |
| Content-Length | 请求体字节数，服务端据此知道 body 读到哪结束 |
| Authorization | 认证凭证（`Bearer <token>`，本阶段 JWT 的载体，见 3.5） |
| Accept | 客户端期望的响应格式——内容协商的输入（见 4.3） |
| User-Agent | 客户端标识（浏览器 / curl / 车端 SDK），排查兼容问题时先看它 |
| Cookie | 携带服务端此前种下的会话标识（有状态方案，与 3.5 的 JWT 对照理解） |

| 常见响应头 | 作用 |
|-----------|------|
| Content-Type | 响应体格式与字符集（application/json; charset=UTF-8） |
| Content-Length | 响应体字节数 |
| Location | 201 创建成功时新资源的 URL（如 `/api/users/42`） |
| Access-Control-Allow-* | CORS 许可声明（见 3.6） |
| WWW-Authenticate | 401 时告诉客户端该用什么方案认证（如 `Bearer`） |

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

**关键概念：无状态与幂等**。HTTP 每个请求独立（服务端不记「上次是谁」），所以「谁在调」要靠每次请求带上的凭证（Cookie/Token，本阶段讲 JWT）——这是 REST 与有状态 RPC 的本质区别。

> ⚠️ **「无状态」与「持久连接」不矛盾，别混淆**：无状态说的是**应用层**——服务端不从连接里推断「你是谁」，每个请求自带凭证；HTTP/1.1 的持久连接（Keep-Alive）说的是**传输层**——同一条 TCP 连接可以连续收发多个请求/响应，省掉反复握手的开销。两者正交：连接复用是性能优化，不改变「请求之间互不认识」的协议语义。反过来，短连接 + Cookie 照样能做出「有状态会话」——状态是服务端拿 session id 查出来的，不是连接记住的。

**幂等性对照表**（幂等 = 同一请求重复执行 N 次，效果与执行 1 次相同）：

| 方法 | 幂等 | 工程含义 |
|------|------|---------|
| GET | ✅ | 读操作天然幂等，可安全重试、可被缓存 |
| PUT | ✅ | 整体替换——重复执行结果一致，适合「可重放的更新」 |
| DELETE | ✅ | 删一次与删 N 次结果相同（第二次通常返回 404/204） |
| POST | ❌ | 重复提交会创建多条——支付/下单类接口必须防重（幂等键、数据库唯一约束） |
| PATCH | 一般不保证 | 若语义是「基于当前值增量修改」（如库存 +1），重复执行结果漂移；「设为某值」的 PATCH 则幂等 |

幂等是接口设计的重要约束：网络重试（超时后客户端不知道服务端到底收没收到）只有对幂等操作才是安全的——ph16 微服务阶段的远程调用重试机制正是建立在这张表上（本阶段只需建立「哪些方法可以放心重试」的直觉，重试框架本身属于 ph16）。

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

**两种映射方式：web.xml 与注解**。上面用的 `@WebServlet` 是 Servlet 3.0（2009）才引入的写法；此前的唯一方式是 `web.xml` 集中配置，两者语义一一对应：

```xml
<!-- web.xml 写法（Servlet 2.5 及以前的唯一方式，语义示意）——与 @WebServlet("/echo/*") 等效 -->
<servlet>
    <servlet-name>echo</servlet-name>
    <servlet-class>com.example.EchoServlet</servlet-class>
</servlet>
<servlet-mapping>
    <servlet-name>echo</servlet-name>
    <url-pattern>/echo/*</url-pattern>
</servlet-mapping>
```

| 维度 | web.xml | `@WebServlet` 注解 |
|------|---------|-------------------|
| 时代 | Servlet 2.5 及以前的唯一方式 | Servlet 3.0（2009）起可用 |
| 配置位置 | 集中在 `WEB-INF/web.xml` 一个文件 | 写在类上，挨着代码 |
| 维护成本 | 加删映射要改 XML，与代码分离易腐化 | 改类即改映射，内聚 |
| 冲突规则 | 两者同时存在时 web.xml 优先，可覆盖注解 | — |

URL 匹配的优先级规则（Tomcat 按序尝试）：**精确匹配**（`/users/list`）→ **前缀匹配**（`/api/*`，最长前缀优先）→ **扩展名匹配**（`*.do`）→ **默认 Servlet**（`/`）。理解这个顺序才能解释「为什么我的 `/api/*` 没生效却被 `/*` 截胡」这类问题。

> ⚠️ **Servlet 是单实例多线程的**：容器对同一个 Servlet 只创建**一个实例**，所有请求线程共享它（线程池模型见 4.1）——**实例字段是跨请求共享状态**，存请求级数据就是经典竞态坑：

```java
// 反例（经典坑的教学示意，不在 examples/ 中，勿复制到生产）
public final class BadServlet extends HttpServlet {
    private String lastUser;   // ❌ 实例字段被所有请求线程共享
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        lastUser = req.getParameter("name");   // 线程 A 写入后线程 B 覆盖，读到的是谁的请求全凭运气
    }
}
```

规则：请求级数据只放**方法局部变量**（或 `HttpServletRequest` 属性）；确需跨请求共享的状态用并发容器（ph09 的 ConcurrentHashMap）。Spring 的 `@RestController` 默认同样是单例——这条规则在框架时代依然成立，字段里只能放无状态依赖（Service 引用），不能放请求数据。

> 本阶段只用手写 Servlet 理解机制，**Filter/Listener 的完整体系与 Servlet 3.0 异步、非阻塞 IO 属于 ph20 高级 Java 阶段**（Netty 与高性能网络编程），这里只需理解「请求-响应-生命周期」三个最小认知。

### 3.3 REST API 与 JSON：资源设计与统一响应

REST 把「数据」建模为**资源**，URL 标识资源、方法表达操作：`GET /api/users` 读列表、`POST /api/users` 创建、`GET /api/users/{id}` 读单个、`PATCH /api/users/{id}` 局部更新、`DELETE /api/users/{id}` 删除。路径参数 `{id}` 与查询参数（`?limit=20`）分工：路径参数定位资源，查询参数筛选/分页。

**资源命名约定**（业界通行约定，非协议强制，但团队内必须一致）：

| 约定 | 推荐 | 反例 |
|------|------|------|
| 资源用名词复数 | `/api/users` | `/api/getUser`（动词塞进了 URL，动作用方法表达） |
| 层级表达从属关系 | `/api/vehicles/{vin}/reports` | `/api/getReportsByVin?vin=...` |
| 查询参数做筛选与分页 | `GET /api/users?status=active&page=2` | 每种筛选各开一个端点 |
| 小写 + 连字符分词 | `/api/vehicle-reports` | `/api/VehicleReports`（大小写敏感的坑） |

**JSON 序列化**是 REST 的数据载体：Java 对象 ↔ JSON 文本。手写版（ex01 的 MiniJson）让你看清「对象怎么变成字符串」；生产用 **Jackson**（Spring Boot 内建，starter-web 自动注册）：`@RequestBody` 把 JSON 反序列化成 Java 对象、`@RestController` 把返回值序列化成 JSON——**序列化是 ph07 IO 阶段「字节↔字符」心智的框架化**。

字段与 JSON key 的映射大多靠默认约定（字段名原样输出），不一致时用 Jackson 注解微调（点到为止，完整注解体系查 Jackson 官方文档）：

| Jackson 注解 | 作用 |
|-------------|------|
| `@JsonProperty("user_name")` | 字段名与 JSON key 不一致时显式指定映射 |
| `@JsonInclude(NON_NULL)` | null 字段不出现在响应里（响应更干净，前端少判空） |
| `@JsonIgnore` | 字段不参与序列化——密码等敏感字段**绝不返回**的兜底 |
| `@JsonFormat(pattern = "yyyy-MM-dd")` | 日期时间字段的格式定制 |

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

| 维度 | 手写 if | 声明式 `@Valid` |
|------|--------|----------------|
| 规则位置 | 散落在 Controller/Service 方法体 | 与字段声明在一起（record/类字段上） |
| 可读性 | 校验与业务混杂，字段多了成「箭塔」 | 一眼看全一个模型的全部约束 |
| 复用 | 每个接口各写一份，容易漏 | 同一模型所有入口自动生效 |
| 失败响应 | 手写 return，形状容易不统一 | 统一抛 `MethodArgumentNotValidException`，交给 3.7 的全局异常处理转 400 |
| 适用 | 学习机制、极简服务（ex01 零依赖场景） | 生产接口的默认选择 |

> **注意**：声明式不是万能的——跨字段约束（如「开始时间 < 结束时间」）、依赖数据库状态的规则（如「用户名未被注册」）注解表达不了，仍由 Service 手工校验兜底，即下文的「分层心智」。

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

```text
eyJhbGciOiJIUzI1NiJ9  .  eyJzdWIiOiJhbGljZSIsImV4cCI6MTczNTY4OTYwMH0  .  SflKxwRJSMeKKF2QT4...
└── base64url(Header) ─┘  └── base64url(Payload)：谁都能解开看（不是加密！）──┘  └── 签名 ──┘
```

> ⚠️ **JWT 是签名不是加密**：前两段只是 base64url 编码，任何人都能解开看内容——**敏感信息（密码、身份证）绝不放进 Payload**；`secret` 只保证「改不了」，不保证「看不了」。需要机密性要用 HTTPS 管传输（部署侧，ph19 的内容），Payload 本身仍按「公开可读」对待。

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

**异常分类处理**是这张表的落地——每类异常对应固定的状态码、业务码段与日志级别，接口行为才可预期：

| 异常类型 | 典型来源 | HTTP 状态码 | 业务码段 | 日志级别 |
|---------|---------|------------|---------|---------|
| 参数校验失败 | `@Valid` / Bean Validation | 400 | 400xx | WARN（用户输入问题，不是系统错） |
| 未认证 / 凭证无效 | JWT 验签失败、token 过期 | 401 | 401xx | WARN |
| 无权限 | 认证通过但角色不够（本阶段只到认证，授权见 ph15） | 403 | 403xx | WARN |
| 资源不存在 | 按 id 查询不存在 | 404 | 404xx | INFO 或 WARN |
| 业务规则冲突 | 重复创建、状态不允许的流转 | 409 | 409xx | WARN |
| 兜底未知异常 | NPE、下游调用超时等 | 500 | 500xx | **ERROR（必须，否则线上查不到根因）** |

分类的价值在于**客户端可以编程化处理**：400 提示用户改输入、401 跳登录、500 报「请稍后重试」——如果全部揉成一个 500 或一个 200，调用方只能猜。

**日志**用 SLF4J（Spring Boot 默认 Logback 实现）：`LoggerFactory.getLogger(Xxx.class)` 拿 logger，`log.info("create_user id={} name={}", id, name)` 占位符写法避免字符串拼接、生产可切换实现（Log4j2 等）。日志分级的使用决策：

| 级别 | 用于 | 例子 |
|------|------|------|
| ERROR | 需要人工介入的错误（兜底异常、外部依赖不可用） | `log.error("unhandled_exception", ex)` |
| WARN | 预期内/可恢复异常（校验失败、认证失败、限流命中） | `log.warn("login_failed user={}", u)` |
| INFO | 关键业务事件（启动完成、创建、状态变更） | `log.info("create_user id={}", id)` |
| DEBUG | 开发期细节（参数值、中间状态）——生产默认关闭 | `log.debug("payload={}", body)` |

**兜底异常处理器必须记 ERROR**（roadmap 必会概念「全局异常处理提升一致性」的落点）：被 `@RestControllerAdvice` 拦下的异常不会自己进日志，不记就永远查不到；而 WARN 级别记校验失败，是为了让 ERROR 通道保持「只有真问题才响」的信噪比。

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

**手写 Servlet 到 Spring MVC 注解的对照**——框架化的本质是「同样的概念换声明方式」：

| 手写 Servlet（3.2） | Spring MVC（本节） | 职责 |
|--------------------|-------------------|------|
| 继承 `HttpServlet` + 覆写 `doGet` | `@RestController` + `@GetMapping` 方法 | 请求处理入口 |
| `@WebServlet("/echo/*")` / web.xml | `@RequestMapping("/api")` 类级前缀 + 方法级路径 | URL 映射 |
| `req.getPathInfo()` 手工切字符串 | `@PathVariable` | 路径参数绑定 |
| `req.getParameter("name")` | `@RequestParam` | 查询参数绑定 |
| `req.getReader()` 手工读 body 再解析 | `@RequestBody`（Jackson 反序列化，见 4.3） | 请求体绑定 |
| `resp.setStatus()` + `getWriter().write(json)` | 方法返回值 + `@ResponseStatus`（converter 链序列化） | 响应构造 |

对照着看就能发现：Spring MVC 没有引入新概念，只是把 3.2 里每个手写动作收编成了一个注解——所以先手写 Servlet 再学框架，心智是无缝平移的。

## 4. 底层原理

### 4.1 一次 HTTP 请求的完整旅程：从 TCP 到响应

```text
浏览器 ──TCP 连接──▶ Tomcat Connector ──解析 HTTP 报文──▶ Engine/Host/Context 匹配
   ▲                                                            │
   │                                                            ▼
   └──────◀── HTTP 响应 ────── DispatcherServlet/Filter ──▶ Servlet(doGet/doPost)
```

连接器（Connector）把 TCP 字节流解析成 HTTP 请求对象（方法/URL/头/body），容器逐层匹配（Engine→Host→Context→Servlet）后调用 Servlet；Servlet 写响应对象，连接器序列化回客户端。理解这条链就明白：Spring Boot 的 `@RestController` 方法最终也是被容器线程调用的普通方法，框架只是替你完成了「URL 匹配 + 参数绑定 + 序列化」。

**一请求一线程的线程池模型**：Tomcat 内部的角色分工是——Acceptor 线程接连接、Poller 线程监听已接连接的可读事件（NIO）、**Worker 线程池**真正执行 Servlet/Controller 逻辑（默认上限 `server.tomcat.threads.max` = 200）。含义很直接：并发能力上限 ≈ worker 线程数，一个慢请求（查库 5 秒、调下游超时 30 秒）就占住一个 worker——慢请求堆积会耗尽线程池，后来的请求全部排队，这就是「线程池打满」的典型故障形态。这也是为什么超时要显式设置、慢 SQL 要治理。

> 这个「一请求一线程」模型正是 ph09 讲的虚拟线程最受益的场景：Spring Boot 3.2+ 配 `spring.threads.virtual.enabled=true` 后，worker 换成虚拟线程，慢请求占住的不再是昂贵的平台线程——心智不变、承载能力质变。虚拟线程的调度机制本身（挂起/恢复、载体线程）属于 ph09 多线程与并发阶段，这里只需记住「Tomcat 的吞吐瓶颈在 worker 线程数，虚拟线程把它解开了」。

### 4.2 Spring MVC 的 DispatcherServlet 分发

Spring MVC 用**前端控制器模式**：所有请求先进 `DispatcherServlet`，它按 `HandlerMapping` 找到对应控制器方法（`@GetMapping("/ping")` → `HelloController.ping`），`HandlerAdapter` 负责调用并绑定参数（路径参数/查询参数/请求体反序列化），返回值经 `HttpMessageConverter`（Jackson）序列化写响应。**拦截器**（`HandlerInterceptor`，本阶段 ex06/project 用于 JWT 鉴权）在控制器执行前/后/完成后挂钩子，是「横切关注点」的 MVC 层实现——对比 ex01 手写 HttpServer 的 `Filter`，同一思想、不同实现层。

### 4.3 内容协商与 HttpMessageConverter 链

`@RestController` 的方法返回一个 Java 对象，响应体却是 JSON 文本——中间这一步叫**内容协商（Content Negotiation）**：

1. 客户端用 `Accept` 头声明期望的响应格式（`application/json`、浏览器默认 `text/html` 等）；
2. Spring MVC 拿着返回值类型 + Accept，按序询问已注册的 `HttpMessageConverter` 链：「你能把这个对象写成这个格式吗？」；
3. 第一个说「能」的 converter 负责序列化——starter-web 默认注册 Jackson 的 `MappingJackson2HttpMessageConverter`（处理 `application/json`）、字符串/字节数组等基础 converter；
4. 请求方向同理：`@RequestBody` 的反序列化由 converter 按 `Content-Type` 选择——请求头说 `application/json`，Jackson converter 接手把文本变对象。

```text
返回值(Java 对象) ──▶ converter 链按 Accept 逐个询问 ──▶ Jackson converter ──▶ JSON 文本
请求体(JSON 文本) ──▶ converter 链按 Content-Type 选择 ──▶ Jackson converter ──▶ Java 对象
```

理解这条链的价值：想统一加 `Result` 包装、想支持 XML/CSV 响应、想定制日期格式——都是往这条链上插一个 converter 或配置 Jackson，而不是改 Controller。这也正是 3.3 说的「Jackson 注解微调映射」生效的位置：注解最终由 Jackson converter 读取执行。

### 4.4 JWT 的签名机制：为什么篡改必被识破

HMAC-SHA256 是**带密钥的哈希**：`signature = HMAC-SHA256(header.payload, secret)`。验签方用同一密钥重算并比对——比对失败说明内容被改过（攻击者没有密钥改不出合法签名）。**重点：签名覆盖 header 和 payload 两个部分**，所以 header 里声称的算法也不能被换成 `none`（部分老库的经典漏洞——攻击者把 alg 改成 none 逃逸验签）。本阶段手写版把「签了什么」摊开给你看，jjwt 库（ex06）把「防止 alg=none、过期检查、密钥管理」都做掉了——**理解机制后敢用库，是安全主题的正确姿势**。

### 4.5 Spring Boot 自动配置：约定优于配置的引擎

`@EnableAutoConfiguration` 启动时扫描 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`，按「条件注解」决定配什么：classpath 有 `spring-webmvc` → 配 `DispatcherServlet`；有 `tomcat-embed-core` → 配内嵌 Tomcat；有 `jackson-databind` → 配 `MappingJackson2HttpMessageConverter`。**配置的默认值**（端口 8080、JSON 序列化规则）来自 `application.properties/yml`。这就是「为什么只引一个 starter 就能跑」的答案——自动配置按依赖推断并给默认值，你要改的才写配置（对比 ph11 构建工具的「依赖管理」心智：starter 是「依赖 + 默认配置」的聚合）。

## 5. 使用场景

- **对外数据服务**：把业务能力暴露为 HTTP API——本阶段 project/ 的车辆数据上报 API 是车联网方向的直接落地（roadmap 推荐项目），ph13 的存储层可平移进 `VehicleStore`。这类服务的共性需求本阶段全部覆盖过：语义化状态码让车端 SDK 能编程化分支、统一响应结构让前端/车端共用一套解析、JWT 让「哪辆车在上报」无状态可查、`@Valid` 在入口处挡住脏数据（脏遥测数据入库后再清洗的代价远大于入口拦截）。
- **前后端分离**：REST API + JSON 是前后端分离的事实标准——前端（React/Vue，本阶段用 CORS 允许其跨域调用）只认 `{code, message, data}` 一个形状，这正是「统一响应结构」为什么是必会概念。两个配套实践：springdoc 自动生成的 OpenAPI 文档直接当联调契约用（前端照着 Swagger UI 里的 schema 写类型）；异常分类处理表（3.7）让前端可以按状态码分支 UI——400 提示改输入、401 跳登录、500 显示「稍后重试」。
- **接口设计的长期维护**：幂等性对照表（3.1）决定客户端能不能安全重试——把「创建」设计成 POST 就要配幂等键，把「更新」设计成 PUT 就能直接重放；资源命名约定（3.3）决定 API 的可读性与可演进性——层级路径 `/api/vehicles/{vin}/reports` 在加「按时间范围查轨迹」这类新需求时只需追加查询参数，而动词式 URL 每加一个动作就多一个端点。
- **什么时候不用 Spring Boot**：极简单的内部工具或单机演示（ex01 的 HttpServer 就够）、对启动体积/延迟极敏感的边缘场景（可换 Quarkus/Micronaut，ph15 对比）。本阶段学 Spring Boot 是为了生态（ph15 全家桶、ph16 微服务都建立在它上面）。
- **与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：Java 的 Servlet/Spring 是「容器托管生命周期」的经典模型（回调 + 注解）；Go 的标准库 `net/http` 是「函数式 Handler」、显式中间件链；Python 的 FastAPI 用装饰器 + 类型注解自动生成 OpenAPI——三种语言解决同一问题（路由/参数/文档）的不同风格：Java 注解声明式最重、Go 显式最小、Python 双注解。Rust 的 axum/actix 走「tower 中间件栈」，与 Go 更近。线程模型上四者同源不同形：Java Servlet 的一请求一线程（4.1）与 Go 的 goroutine-per-conn、Python 的 async loop、Rust 的 tokio task 是同一个「并发处理连接」问题的四代答案。

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
- **报文结构与头**：HTTP/1.1 报文 = 起始行 + 头 + 空行 + body，Content-Length 是 body 的终止依据；Host/Content-Type/Authorization/Accept 等常用头各自承载虚拟主机、格式声明、凭证、内容协商职责
- **无状态 ≠ 短连接**：无状态是应用层语义（请求自带凭证），持久连接是传输层优化（TCP 复用），两者正交
- **幂等性**：GET/PUT/DELETE 幂等可安全重试，POST 不幂等必须防重（幂等键/唯一约束）——这张表是 ph16 远程调用重试的地基
- **Servlet 单实例多线程**：容器对同一 Servlet 只建一个实例，实例字段是共享状态——请求级数据只放方法局部变量，这条规则对单例 `@RestController` 同样成立
- **REST 语义**：URL 标识资源（名词复数、层级从属）、方法表达操作、状态码表达结果——201 创建 / 204 删除 / 400 参数错 / 404 不存在 / 405 方法不支持；统一响应 `{code, message, data}` 是接口契约
- **参数校验双层**：`@Valid` 声明式拦「输入形状」（快速失败），Service 校验兜底「业务规则」；`@RestControllerAdvice` 统一转错误响应
- **JWT 机制**：Signature = HMAC-SHA256(header.payload, secret)，覆盖完整前两段所以篡改必被识破；`exp` 管过期；手写理解机制、库管生产
- **CORS**：同源策略是浏览器的，CORS 头是服务器开的门；预检 OPTIONS、带凭证不能用 `*`
- **异常分类处理**：校验→400/WARN、认证→401/WARN、兜底→500/ERROR——状态码给客户端分支用，日志级别给运维降噪用；兜底必须记 ERROR
- **Tomcat 线程池模型**：Acceptor 接连接、Poller 监听事件、Worker 池（默认 200）执行业务——慢请求占住 worker，线程池打满是典型故障形态；虚拟线程（ph09）把这个瓶颈解开
- **内容协商**：Accept/Content-Type 头驱动 HttpMessageConverter 链选择序列化器——统一包装、换格式、调 Jackson 都是在这条链上做文章
- **Controller 不写业务**：Controller（HTTP 语义）→ Service（业务规则）→ Store（数据访问）三层分工，是 roadmap 必会概念的直接落地

### 阶段验收清单

- [ ] 能说清一次 HTTP 请求从 TCP 到 Controller 方法的完整旅程（Servlet 容器在其中的角色），并说清 Tomcat worker 线程池与「一请求一线程」的关系
- [ ] 能画出 HTTP 请求/响应报文的四段结构，说出 Host/Content-Type/Authorization/Accept 等常见头的职责
- [ ] 能区分「无状态」（应用层）与「持久连接」（传输层），并能默写幂等性对照表（GET/PUT/DELETE 幂等、POST 不幂等及工程含义）
- [ ] 能解释 Servlet 单实例多线程模型，并说明「实例字段存请求数据」为什么是竞态坑
- [ ] 能用手写 HttpServer 或 Spring Boot 写一个 REST API，并用语义化状态码（201/204/400/404/405）表达结果
- [ ] 能按资源命名约定（名词复数、层级从属）设计接口路径，并用 Jackson 注解微调序列化
- [ ] 能用 `@Valid` 声明式校验 + `@RestControllerAdvice` 全局异常，让所有接口返回统一响应结构，并按「异常分类处理表」选择状态码与日志级别
- [ ] 能解释 JWT 的签名机制（为什么篡改必被识破）、用 jjwt 实现登录鉴权（签发 + 拦截器验签）
- [ ] 能配置 CORS 并解释预检流程；能说清「认证（JWT 验签）和授权（ph15 Spring Security）的区别」
- [ ] 能起 Spring Boot 服务、看 SLF4J 日志（会按 ERROR/WARN/INFO/DEBUG 分级决策）、用 springdoc 自动生成 API 文档
- [ ] 能解释内容协商：Accept/Content-Type 头如何驱动 HttpMessageConverter 链完成序列化/反序列化
- [ ] 能说出「Controller 不应写复杂业务」，并按 Controller/Service/Store 三层组织接口代码

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：纯 JDK Todo API（练习 1）→ 手写校验器（练习 2）→ 手写 JWT（练习 3）→ Spring Boot Todo + 文件上传 + MockMvc（练习 4）→ 登录注册 + JWT + 全局异常（练习 5，把前四题串成闭环）。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**车辆数据上报 API**（roadmap 推荐项目）——REST 上报/查询 + JWT 鉴权 + 声明式校验双层 + 全局异常 + CORS + springdoc 文档，`mvn test` 实测 13 用例全过。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`mvn test` 13 用例 + curl 验收标准）

### 下一阶段

[Spring 全家桶阶段](../ph15-spring-family/15-spring-family.md) — 本阶段回答 ph14 留下的「框架替你做了 X」：`@RestController` 只是 Spring 的冰山一角，ph15 讲透容器机制（IOC/DI 与 Bean 生命周期——为什么 `@Autowired`/构造器注入能把 `VehicleService` 塞进 `VehicleController`）、AOP 与事务管理、Spring Security 授权（把本阶段的「认证」升级为「认证 + 授权」）、Spring Boot 自动配置原理（为什么引个 starter 就能跑）与 Actuator 监控、Spring Data 接口即实现（`VehicleStore` 换成 JPA Repository 的形状演进）。
