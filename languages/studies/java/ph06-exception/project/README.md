# ph06 阶段项目：统一异常处理 demo

## 需求

对应 Roadmap「ph06 异常处理阶段」推荐项目第一个「统一异常处理 demo」（第二个「业务错误码体系」已并入本项目——错误码枚举 + 业务异常基类正是本项目的前置组件）。主文档第 4.3 节提出的「边界转换」模式在此完整落地：Controller/Service/DAO 三层各自抛出不同类型的异常，顶层通过统一的 `GlobalExceptionHandler.handle(Throwable)` 分类处理，把异常翻译成错误码 + 统一响应结构 `ApiResponse<T>`——业务异常返回对应业务码、参数异常返回 400、未知异常记录日志后返回兜底 500。

项目以「用户服务」为场景：查询用户、登录、转账、基础设施检查四个接口，覆盖异常处理全谱系。`handle` 返回的 `ApiResponse<T>` 已是 ph15 Spring 阶段 `@RestControllerAdvice` 的语义基础。

## 文件结构

| 文件 | 类 | 职责 |
|------|----|------|
| error-code.java | ErrorCode | 业务错误码枚举：集中管理错误语义（code + message） |
| business-exception.java | BusinessException 及子类 | 业务异常体系：unchecked 基类 + 错误码 + 上下文 + cause；子类 UserNotFoundException / LoginFailedException / InsufficientBalanceException |
| api-response.java | ApiResponse | 统一响应结构 record：success / code / message / data |
| exception-handler.java | GlobalExceptionHandler | 统一处理入口：分类处理业务异常 / 参数异常 / 未知异常 |
| exception-demo-app.java | ExceptionDemoApp | Controller/Service/DAO 三层模拟 + 自测 main |

## 功能清单

- [ ] 错误码枚举 `ErrorCode`：集中管理错误语义（400 参数、404 用户不存在、1001 登录失败、2001 余额不足、500 兜底）
- [ ] 业务异常基类 `BusinessException`（unchecked）：携带错误码 + 业务上下文 + 可选 cause，子类表达具体业务失败
- [ ] DAO 边界转换：底层受检异常在 DAO 边界包装为 unchecked 业务异常并保留 cause（主文档 4.3 节模式）
- [ ] 统一响应结构 `ApiResponse<T>`：所有接口返回同一形状
- [ ] 统一处理入口 `GlobalExceptionHandler.handle(Throwable)`：业务异常 -> 对应业务码；`IllegalArgumentException` -> 400；未知异常 -> 记录日志 + 兜底 500
- [ ] 三层模拟：DAO 抛受检异常、Service 抛业务/参数/基础设施异常、Controller 统一 try/catch 交 handler
- [ ] 自测 main：覆盖 6 条路径（正常查询、用户不存在、登录失败、余额不足、空参数、未知异常）并断言错误码

## 验收标准

- `javac *.java` 编译零错误（五个文件同一目录，通配符一次编译）
- `java ExceptionDemoApp` 全部自测通过，末尾打印「全部自测通过」
- 用户不存在返回 code=404；登录失败返回 code=1001；余额不足返回 code=2001（context 含 balance/amount）；空参数返回 code=400；未知异常（连接池耗尽）返回 code=500 且打印堆栈
- 业务异常一律 unchecked（继承 `RuntimeException`），接口签名不声明 `throws`
- 自测失败抛 `AssertionError` 并给出失败路径名（不静默）

## 扩展方向

- **HTTP 状态码映射**：把错误码映射为 HTTP 状态码（400/404/500），对接 ph14 Web 后端阶段——本项目用 `code` 字段先行，ph15 由 `@RestControllerAdvice` 接管后即为标准做法
- **校验工具类**：把练习 4 的 `Validator.requireXxx` 接入 Service 层，非法参数在入口统一转 400
- **日志框架**：`System.out` / `printStackTrace` 替换为 SLF4J，未知异常记录完整堆栈 + traceId（ph11 工程化 / ph15 Spring 阶段）
- **错误消息国际化**：错误码枚举按 locale 返回不同 message，`ApiResponse<T>` 形状不变
- **响应泛型化复用**：`ApiResponse<T>` 与 ph05 泛型阶段 `Result<T>` 同构，可为统一返回封装复用

## 验证环境

- 工具链：jenv OpenJDK 17.0.16
- 编译：`javac *.java`
- 运行：`java ExceptionDemoApp`

```bash
# 1. 编译
javac *.java
# 2. 运行自测
java ExceptionDemoApp
# 3. 验证后清理 .class
rm -f *.class
```

已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，自测全部通过）。
