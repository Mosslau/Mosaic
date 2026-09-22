# ph14 阶段项目：车辆数据上报 API

> 对应 Roadmap「ph14 Web 后端开发阶段」推荐项目之「车辆数据上报 API」；「后台管理系统」未落地（选 1 个即可）。把 ph13 的「学生管理数据库版」的数据层心智接进 HTTP 服务：上报/查询走 REST，JWT 管「谁在报」，声明式校验 + 业务校验双层兜底，全局异常处理统一响应——本项目的存储层接口形状（`VehicleStore`）与真实数据层一致，可无缝换成 ph13 的 HikariCP+JDBC 实现。

## 需求

实现一个车辆数据上报服务：车辆端定时上报位置/车速/电量（带 token 鉴权），平台端查询车辆最新状态与上报历史。核心是本阶段学的全部 Web 手段把它做对、做统一：**REST 资源设计**（车辆是资源、状态/历史是子资源）、**统一响应结构**（code/message/data）、**JWT 认证**（登录签发、拦截器验签）、**声明式校验 + 业务校验双层**、**全局异常处理**（业务码 → HTTP 状态映射）、**SLF4J 日志**、**springdoc OpenAPI 文档**。

工程结构（标准 Maven 布局，Spring Boot 3.3.0）：

```text
src/main/java/com/example/vehicle/
├── VehicleReportApplication.java   # @SpringBootApplication 启动类
├── ApiResponse.java                # 统一响应 {code, message, data}
├── VehicleReport.java              # 不可变 record：一次上报快照
├── VehicleStore.java               # 线程安全内存存储（数据层接口的最小实现，可换 ph13 实现）
├── VehicleService.java             # 业务层：VIN/坐标/车速/电量校验 + 编排（Controller 不写业务）
├── VehicleController.java          # REST 层：上报 / 状态 / 历史（@Valid 声明式校验）
├── GlobalExceptionHandler.java     # @RestControllerAdvice：业务异常/校验失败/兜底 统一转响应
└── AuthConfig.java                 # JWT 登录 + 拦截器（/api/vehicles/** 需 token）+ CORS
src/main/resources/application.properties   # server.port=18090
src/test/java/com/example/vehicle/
├── VehicleServiceTest.java         # Service 单元测试：业务规则 6 用例
└── VehicleApiTest.java             # REST 集成测试：登录/上报/查询/鉴权/校验 7 用例
```

## 功能清单

- [x] 登录 `POST /api/auth/login`：`demo/demo123` 签发 JWT（1 小时有效），密码错返回 401 + 业务码 40100
- [x] 上报 `POST /api/vehicles/report`：需 `Authorization: Bearer <token>`；VIN/经纬度/车速/电量校验（声明式 `@Pattern/@Min/@Max` 拦「输入形状」，Service 拦「业务规则」双层兜底）
- [x] 最新状态 `GET /api/vehicles/{vin}/status`：该车无上报返回 404 + 业务码 40401
- [x] 上报历史 `GET /api/vehicles/{vin}/reports?limit=N`：默认 20 条、上限 100，按时间升序
- [x] 全局异常处理：业务码 40001~40004/40101/40401/50000 映射到 400/401/404/500 + 统一响应壳
- [x] CORS：允许 `http://localhost:5173` 跨域（预检 OPTIONS 放行）
- [x] API 文档：springdoc 自动生成 `/v3/api-docs` + `/swagger-ui/index.html`

## 验收标准

- `mvn test` 全部通过：**Tests run: 13**（实测：VehicleServiceTest 6 + VehicleApiTest 7），Failures 0 / Errors 0
- **鉴权实测**：无 token 上报 → 401 `{"code":40101,"message":"未登录或 token 无效","data":null}`；带 token → 200
- **校验双层实测**：`vin="SHORT"`（声明式 `@Pattern` 拦截）→ 400 + 40000 带字段错误；`batteryPct=150`（`@Max(100)` 拦截）→ 400 + 40000；Service 层 40004 业务规则由单元测试覆盖——两层各司其职
- **404 实测**：查询未上报的 VIN → 404 `{"code":40401,"message":"该车辆暂无上报数据","data":null}`
- **文档实测**：`GET /v3/api-docs` → 200，paths 含 `/api/auth/login`、`/api/vehicles/report`、`/api/vehicles/{vin}/status`、`/api/vehicles/{vin}/reports`；`/swagger-ui/index.html` → 200

## 验证环境与命令

- 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + jjwt 0.12.5 + springdoc-openapi 2.3.0 + JUnit Jupiter 5.10.2
- 本机实测（沙箱特例）：`mvn -o -Dmaven.repo.local=/tmp/m2clone clean test`（离线模式，依赖取自本地仓库缓存；沙箱禁止写 `~/.m2`）
- **正常联网环境**：`mvn clean test` 即可
- 运行：`mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run`（端口 18090），另开终端跑 README 上方验收标准里的 curl；退出后进程即结束
- 说明：pom 中「离线版本仲裁」注释标记的依赖/插件（junit-platform-launcher、spring-boot-maven-plugin、jakarta.xml.bind-api、jackson-dataformat-yaml、jakarta.activation）仅为本机离线缓存所需，正常联网环境可删除

## 构建脚本（可选）

```bash
#!/usr/bin/env bash
# project/build.sh —— 构建 + 测试 + 打包（离线模式；联网环境可去掉 -o 与 -Dmaven.repo.local）
set -euo pipefail
mvn -o -Dmaven.repo.local=/tmp/m2clone clean test
mvn -o -Dmaven.repo.local=/tmp/m2clone package -DskipTests
java -jar target/vehicle-report-api-1.0.0.jar &   # 启动后 curl http://127.0.0.1:18090/api/auth/login
```

## 测试设计要点（本项目的教学增量）

- **REST 集成测试不占端口**：`@SpringBootTest` + MockMvc 在应用内模拟 HTTP，Controller/Service/Store/拦截器/全局异常全部生效，比 `@WebMvcTest` 更接近真实——登录拿 token → 带 token 上报 → 查状态/历史的完整用户旅程就是一条测试
- **正常路径与错误路径同样覆盖**：`reportRequiresToken`（401）、`invalidVinRejectedByValidation`（400）、`unknownVehicleStatus404`（404）、`wrongPasswordRejected`（40100）与成功流程并列，这正是 ph12 阶段「测试应覆盖正常路径和错误路径」在 REST 层的落地
- **Controller 不写业务**：`VehicleController` 只做 HTTP 语义（路径/参数/请求体 + `@Valid`），业务规则全部在 `VehicleService`——roadmap 必会概念的直接体现；Service 单元测试（`new VehicleService(new VehicleStore())` 不启动 Spring）验证规则本身
- **校验双层各司其职**：声明式注解（`@Pattern/@Min/@Max`）拦「输入形状」快速失败、报错友好；Service 手工校验兜底「业务规则」（如 VIN 校验位、跨字段约束）——与 ph13 数据库阶段的「Java 校验 + 数据库约束分层」同一思想
- **统一响应贯穿**：`ApiResponse` 同时用于成功与失败；业务码分段（400xx 客户端错 / 401xx 未认证 / 404xx 未找到 / 500xx 服务端错），HTTP 状态码表达传输层语义、业务码表达业务语义，两者分工

## 扩展方向（可选）

- **数据层落地**：把 `VehicleStore` 换成 ph13 的 HikariCP + JDBC 实现（接口形状不变，直接替换；ph15 讲 Spring Data 的框架级替代）
- **授权**：区分「管理员查所有车」与「车辆只报自己的数据」——roadmap 必会概念「认证和授权要分清」，授权是 ph15 Spring Security 的内容
- **消息队列接入**：上报量大的话走 Kafka 削峰（ph17 消息队列与搜索阶段），本项目先同步落库
- **Redis 缓存最新状态**：`status` 接口高频读走 Cache-Aside（ph13 examples/ex05 的缓存心智），降低存储层压力
- **部署**：`mvn package` 打 fat jar 后 Docker 化（ph19 DevOps 与部署阶段）
