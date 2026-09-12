# ph15 阶段项目：权限管理系统（RBAC API）

## 需求

roadmap「ph15 Spring 全家桶阶段」推荐项目之一是**权限管理系统**——本项目的落地形态：一个带**用户管理**的 RBAC（Role-Based Access Control）起步 REST 服务，把 ph15 全家桶串成一条真实链路：**Spring Data JPA 管用户数据 → Spring Security 管认证（JWT 无状态）与授权（URL 级；方法级 `@PreAuthorize` 用法见 examples/ex06）→ Bean Validation 管参数 → 统一响应 + 全局异常管契约**。对比 [ph14 project](../../ph14-web-backend/project/README.md)（车辆数据上报 API，手写 VehicleStore + Controller 拦截器验 JWT）：数据层换成 JPA Repository（examples/ex05 的机制），鉴权换成 Security Filter 链原生认证（examples/ex06 + exercises/sol-05 的机制）——同一批需求用 ph15 的框架重写，代码里不再有手写数据访问与手写鉴权。

## 技术栈与验证环境

- OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + Spring Security 6.3.4 + jjwt 0.12.5 + Spring Data JPA（Hibernate 6.5.2）+ HSQLDB 2.5.0（内存库，Hibernate 对 2.5.0 打低于官方下限 2.6.1 的 WARN，实测正常；联网可升 2.7.x）
- 本机离线实测命令：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`（联网环境直接 `mvn test`）
- 运行：`mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run`（端口 18099，配置见 `src/main/resources/application.properties`）

## 功能清单

- [x] 登录认证：`POST /api/auth/login`（`@Valid` 校验 + AuthenticationManager 验 BCrypt + 签发 JWT，2 小时过期）
- [x] 当前用户：`GET /api/me`（带 token 返回用户名与角色）
- [x] 用户管理（仅 ADMIN）：`GET /api/users` 列表（不外泄 password）、`POST /api/users` 创建（查重 409 / 角色白名单 400）、`DELETE /api/users/{id}` 删除
- [x] URL 级授权：`/api/users/**` 要求 `ROLE_ADMIN`（SecurityConfig `hasRole`）
- [x] 统一响应与异常契约：成功 `{code:0,message:"ok",data}`；40001 参数校验（data 带字段错误）、40100 未认证/token 无效（Filter 层 entryPoint）、40101 登录失败（ControllerAdvice）、40300 无权限（URL 级拒绝由 Filter 层 accessDeniedHandler 写出；ControllerAdvice 仅预留方法级 `AccessDeniedException` 分支，本项目未使用方法级授权）、40901 用户名冲突、50000 兜底（记 ERROR 日志）。码义为本阶段重排：40100=未认证、40101=登录失败——与 ph14 相反（ph14 project/ex06 中 40100=密码错、40101=未登录），跨阶段对照代码勿混用
- [x] 启动种子：空库自动造 `admin/admin123`（BCrypt 哈希入库，AdminSeed）
- [x] JPA 实体映射：`app_user` 表（避免 user 保留字）、IDENTITY 主键、username 唯一约束

## 验收标准

- `mvn -o -Dmaven.repo.local=/tmp/m2clone test` → **Tests run: 10, Failures: 0**（10 个用例：种子 admin 登录 / 空参数 400 / 密码错 40101 / 无 token 40100 / admin 列用户无密码字段 / 新建 USER 可登录但访问 /api/users 403 / 重名 40901 / 非法角色 40002 / 删除后原用户登录 401 / /api/me）
- curl 验收流（运行实录，端口 18099）：
  - `POST /api/auth/login`（admin/admin123）→ 200 `{"code":0,...,"data":{"token":"<jwt>","username":"admin","role":"ADMIN"}}`
  - `GET /api/me` 带 Bearer → `{"code":0,...,"data":{"username":"admin","authorities":["ROLE_ADMIN"]}}`
  - `GET /api/users` 带 Bearer → 200，列表无 password 字段
  - `POST /api/users` 创建 bob → 200 `{"id":2,"username":"bob","role":"USER",...}`；重复创建 → **409**；无 token 访问 → **401**
- 能说清本项目与 ph14 project 的差异点（数据访问与鉴权两条主线的框架化替换）

## 扩展方向

- **权限细化**：单角色升级为用户 ↔ 角色 ↔ 权限（authority）多对多——练习与项目里的 `ROLE_` 前缀就是为此预留的；方法级 `@PreAuthorize` 已在 examples/ex06 演示，可按资源粒度下沉到 Service
- **持久化升级**：HSQLDB 内存库换文件库/PostgreSQL（`spring.datasource.url` + 驱动 + `spring.jpa.ddl-auto=validate` + Flyway 迁移，见 ph13 的迁移工具）
- **令牌升级**：token 黑名单/刷新令牌（JWT 无状态换 Refresh Token 双令牌）——过期吊销与账号禁用需要状态，属工程进阶方向（roadmap ph16 微服务与分布式阶段会继续讲分布式会话与网关鉴权）
- **可观测性**：接入 examples/ex02 的 actuator（health/info/metrics）为运维端点
