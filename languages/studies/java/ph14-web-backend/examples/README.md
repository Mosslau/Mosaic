# ph14 Web 后端开发 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，覆盖「纯 JDK HttpServer → 嵌入式 Tomcat/Servlet → 手写 JWT → Spring Boot REST → 校验+全局异常+日志 → JWT+CORS+OpenAPI」的完整链路。验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ Spring Boot 3.3.0 + Tomcat 10.1.31 + jjwt 0.12.5 + springdoc-openapi 2.3.0**。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：本环境沙箱禁止写默认本地仓库 `~/.m2`，所需构件取自本地仓库缓存，构建用 `mvn -o -Dmaven.repo.local=/tmp/m2clone`。**在正常联网环境直接执行 `mvn test` 即可**（首次运行会从 Maven Central 下载）。

Spring Boot 工程的 pom 带了「离线版本仲裁」注释的依赖/插件（junit-platform-launcher、surefire 插件版本、spring-boot-maven-plugin、jakarta.xml.bind-api、jackson-dataformat-yaml、jakarta.activation）：本机缓存缺这些构件的默认版本，用缓存内相近版本压过（机制见 ph11 主文档依赖仲裁）。**正常联网环境可删除这些项**，让依赖自行拉取声明版本。

ex01/ex03 是零依赖的独立 java 文件（`javac` + `java` 即可）；ex02 是嵌入式 Tomcat 的 Maven 工程；ex04~ex06 是 Spring Boot 工程。

## 示例列表

| 目录 | 验证状态 | 说明 | 运行/测试命令（目录内） | 实测结果 |
|------|---------|------|----------------------|---------|
| ex01-jdk-httpserver/ | ✅ 已验证 | 纯 JDK `HttpServer` 手写 REST：路由/JSON 手工解析/状态码(200/201/400/404/405)/CORS 头/日志中间件 | `javac -d out src/com/example/*.java && java -cp out com.example.RestServer 18080`（另开终端 curl） | 8 条 curl 用例全过（见下） |
| ex02-servlet-tomcat/ | ✅ 已验证 | 嵌入式 Tomcat 10.1.31 + 手写 Servlet：`@WebServlet` 注解 / GET/POST / 路径与查询参数 / 404 | `mvn -o -Dmaven.repo.local=/tmp/m2clone -q package`，再按下方「ex02 运行命令」的 java -cp 启动 | GET 200、POST 200、404 实测 |
| ex03-jwt-handmade/ | ✅ 已验证 | 手写 JWT（HMAC-SHA256）：base64url + MAC 签名/验签/过期/篡改检测 | `javac -d out src/com/example/JwtDemo.java && java -cp out com.example.JwtDemo` | 合法 true、篡改 false、过期 false、非法 false |
| ex04-spring-boot-rest/ | ✅ 已验证 | Spring Boot REST：`@RestController` / 统一响应 `ApiResponse` / `@PathVariable` / MockMvc | `mvn -o -Dmaven.repo.local=/tmp/m2clone test`；`mvn ... spring-boot:run` 后 curl 端口 18084 | Tests run: **3**；curl 三例全过 |
| ex05-spring-boot-validation-error/ | ✅ 已验证 | `@Valid` 参数校验 + `@RestControllerAdvice` 全局异常 + SLF4J 日志 + 统一响应 | `mvn -o -Dmaven.repo.local=/tmp/m2clone test`；`mvn ... spring-boot:run` 后 curl 端口 18085 | Tests run: **4**；curl 校验失败 400 实测 |
| ex06-spring-boot-jwt-cors-openapi/ | ✅ 已验证 | jjwt 登录鉴权 + HandlerInterceptor + CORS 配置 + springdoc OpenAPI 文档 | `mvn -o -Dmaven.repo.local=/tmp/m2clone test`；`mvn ... spring-boot:run` 后 curl 端口 18086 | Tests run: **5**；curl 7 项全过（含 /v3/api-docs、/swagger-ui） |

## 验证记录（实测输出要点）

### ex01：纯 JDK HttpServer

- `javac -d out src/com/example/RestServer.java src/com/example/MiniJson.java && java -cp out com.example.RestServer 18080`
- `GET /api/ping` → `{"message":"pong"}`，响应头含 `Access-Control-Allow-Origin: *`
- `POST /api/users`（`Content-Type: application/json` + `{"name":"Alice"}`）→ `{"id":1,"name":"Alice"}`；缺 name / 空白 name → 400
- `GET /api/users` → `[{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}]`；`GET /api/users/999` → 404 `{"error":"not_found","id":999}`
- `PUT /api/users` → 405 `{"error":"method_not_allowed",...}`（语义化状态码）
- 日志中间件：`[log] GET /api/ping -> 200 (20 ms)` 每请求一行

### ex02：嵌入式 Tomcat + Servlet

- 运行命令（本机离线缓存路径；联网环境换成 `~/.m2` 里的 jar 路径）：
  ```bash
  mvn -o -Dmaven.repo.local=/tmp/m2clone -q package
  CP=$(find /tmp/m2clone/org/apache/tomcat/embed/tomcat-embed-core/10.1.31        /tmp/m2clone/org/apache/tomcat/embed/tomcat-embed-el/10.1.31        /tmp/m2clone/jakarta/annotation/jakarta.annotation-api/2.1.1 -name '*.jar' | tr '\n' ':')target/classes
  java -cp "$CP" com.example.Main 18081
  ```
- 启动后监听 18081
- `GET /echo/hello?name=Alice` → 200 `{"path":"/hello","method":"GET","name":"Alice","message":"Hello, Alice"}`
- `POST /echo/hello`（body `{"msg":"hi"}`）→ 200 回显 body；`GET /echo/other` → 404 `{"error":"not_found","path":"/other"}`
- 教学点：嵌入式 `new Tomcat()` + `addContext` + `addServlet` + `addServletMappingDecoded` 三件套 = Spring Boot 内嵌 Tomcat 的底层机制

### ex03：手写 JWT

- `javac -d out src/com/example/JwtDemo.java && java -cp out com.example.JwtDemo`
- 输出 token 三段以 `.` 分隔；header 解码 `{"alg":"HS256","typ":"JWT"}`；payload 解码 `{"sub":"alice","iat":<秒>,"exp":<秒>}`
- `verify(合法 token) = true`、`verify(篡改 sub) = false`（签名不匹配）、`verify(已过期) = false`（exp < now）、`verify(非法输入) = false`
- 教学点：Signature = HMAC-SHA256(header.payload, 密钥)——签名对象是完整的前两段字符串

### ex04：Spring Boot REST + 统一响应

- `mvn -o -Dmaven.repo.local=/tmp/m2clone test` → `Tests run: 3, Failures: 0, Errors: 0`
- `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run`（端口 18084）后：
  - `GET /api/ping` → `{"code":0,"message":"ok","data":{"message":"pong"}}`
  - `GET /api/echo/Alice` → `{"code":0,"message":"ok","data":{"echo":"Alice"}}`
  - `GET /api/echo/张三`（百分号编码）→ `{"code":0,"message":"ok","data":{"echo":"张三"}}`（中文路径参数实测）

### ex05：参数校验 + 全局异常 + 日志

- `mvn -o -Dmaven.repo.local=/tmp/m2clone test` → `Tests run: 4`（合法创建、name 空白、email 非法、name 超长）
- `mvn ... spring-boot:run`（端口 18085）后：
  - 合法 body → 200 `{"code":0,"message":"ok","data":{"id":1,"name":"Alice","email":"alice@example.com"}}`
  - `{"name":"  ","email":"bad"}` → 400 `{"code":40001,"message":"参数校验失败","data":{"email":"email 格式不正确","name":"name 不能为空"}}`
- 日志实测：`INFO ... UserController : create_user id=1 name=Alice`（SLF4J 结构化日志）

### ex06：JWT + CORS + OpenAPI

- `mvn -o -Dmaven.repo.local=/tmp/m2clone test` → `Tests run: 5`（登录发 token、密码错 401、带 token 访问 /api/me、无 token 401、CORS 预检）
- `mvn ... spring-boot:run`（端口 18086）后：
  - 登录成功 → 200 `{"code":0,...,"data":{"token":"<jwt>"}}`；密码错 → 401 `{"code":40100,"message":"用户名或密码错误","data":null}`
  - `GET /api/me` 带 `Authorization: Bearer <token>` → 200；无 token → 401 `{"code":40100,"message":"未登录或 token 无效","data":null}`
  - `OPTIONS /api/me`（`Origin: http://localhost:5173`）→ 200，响应头 `Access-Control-Allow-Origin: http://localhost:5173`、`Access-Control-Allow-Methods: GET,POST,OPTIONS`
  - `GET /v3/api-docs` → 200（OpenAPI 3 文档，paths 含 `/api/auth/login` 与 `/api/me`）；`GET /swagger-ui/index.html` → 200（Swagger UI 交互页）

## 端口说明

各 Spring Boot 示例通过 `src/main/resources/application.properties` 里的 `server.port` 固定端口（ex04=18084、ex05=18085、ex06=18086），避免本机多示例冲突；`spring-boot:run` 退出后进程即结束，无需手工清理。ex01/ex02 用命令行参数指定端口（18080/18081），测试完用 `lsof -ti tcp:<端口> | xargs kill` 清理。
