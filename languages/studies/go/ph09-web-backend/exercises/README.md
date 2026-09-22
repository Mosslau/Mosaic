# ph09 Web 后端开发阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），四题与 roadmap 本阶段「练习」小节一一对应（Todo API / 登录注册 / 文件上传服务 / 设备状态查询 API）。若想按难度递进，建议顺序 4 → 1 → 3 → 2；按 roadmap 顺序 1 → 2 → 3 → 4 亦可。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-todo-api && go test -v`）。请勿在 exercises/ 根目录执行 `go test ./...`——根目录没有 go.mod。

**只允许使用标准库**（net/http、encoding/json、crypto/hmac 等），不引入第三方模块——JWT 要手写签发/验签，这也是理解其原理的最好方式。参考实现文件头都写了验证环境与命令（已验证：go1.25.6，darwin/arm64）。

## 练习 1：Todo API（★★）

**目标**：用 Go 1.22 方法路由写一个 Todo CRUD API，内存存储，可运行可测试。

**要求**：

- `GET /todos` 列出全部（支持 `?done=true` 只列出已完成）；`GET /todos/{id}` 查询单个
- `POST /todos` 创建（body `{"text":"..."}`，text 必填、不超过 100 个字符，成功返回 201）
- `PATCH /todos/{id}/done` 标记完成；`PUT /todos/{id}` 修改文本；`DELETE /todos/{id}` 删除（成功 204）
- 存储用内存 map + Mutex（并发安全）；不存在返回 404，参数非法返回 400
- 所有错误统一 `{code, message}` 结构，code 用稳定枚举（INVALID_PARAM / NOT_FOUND）
- handler 保持四段式：解析 → 校验 → 业务 → 响应

**验收**：`go test -v` 全部通过（覆盖 200/201/204/400/404/405 与 done 过滤）；`go vet ./...` 零报告；`go run .` 启动后 curl 冒烟可用。

> 提示：路由用 `mux.HandleFunc("GET /todos/{id}", ...)` + `r.PathValue`；JSON 解码 `json.NewDecoder(r.Body).Decode`；文本长度用 `[]rune` 数（中文按 1 个字符）。参考 examples/ex03-todo-api。

## 练习 2：登录注册 + JWT（★★★）

**目标**：注册/登录接口 + 手写 HS256 JWT 签发验签 + 鉴权中间件，理解"无状态认证"。

**要求**：

- `POST /register`：用户名密码注册，重复用户名返回 409；成功后直接签发 token 返回
- `POST /login`：校验用户名密码，错误返回 401，成功返回 `{"token": "..."}`
- JWT 用标准库手写：`header.payload.signature` 三段 base64url（RawURLEncoding），signature = HMAC-SHA256(header.payload, secret)，claims 含 username 与 exp
- 验签用 `hmac.Equal` 常数时间比较，并校验 exp 过期
- 鉴权中间件保护 `GET /api/profile`：解析 `Authorization: Bearer <token>`，失败 401，成功返回 `{"username": "..."}`

**验收**：`go test -v` 覆盖注册（201/409）、登录（200/401）、无 token / 坏 token / 篡改 token / 过期 token 均 401、带 token 访问 profile 200；`go vet ./...` 零报告。

> 提示：参考 examples/ex04-jwt-auth 的 jwt.go 与中间件写法；篡改测试可以把 payload 段换成别的 base64 后断言验签失败。

## 练习 3：文件上传服务（★★）

**目标**：multipart 文件上传 + 防路径穿越命名 + 大小限制 + 静态回看。

**要求**：

- `POST /upload`：接收 `file` 字段，保存到 `./uploads` 目录，响应 `{"name": "...", "size": N, "url": "/files/..."}`
- 文件名必须 `filepath.Base` 清洗（防 `../../etc/passwd` 路径穿越），并用时间戳前缀防重名
- 用 `http.MaxBytesReader` 限制单文件 10MB，超限返回 413
- `GET /files/{name}` 用 `http.ServeFile` 提供已上传文件的访问
- 缺 file 字段返回 400

**验收**：`go test -v` 覆盖：正常上传（httptest + multipart.Writer 构造请求体，断言响应 JSON 与落盘文件）、穿越文件名被清洗、超限 413、缺字段 400；`go vet ./...` 零报告。

> 提示：`r.FormFile("file")` 取文件；`os.Create` + `io.Copy` 落盘；测试里用 `t.TempDir()` 当上传目录，避免污染仓库（把上传目录做成可注入的变量）。

## 练习 4：设备状态查询 API（★）

**目标**：把 ph07 学过的 JSON 接口升级为"方法路由 + 统一错误 + 参数校验"的规范形态。

**要求**：

- `GET /api/devices`：列出全部设备，支持 `?status=online|offline` 过滤；status 是其他值时返回 400
- `GET /api/devices/{id}`：存在返回 200 + JSON，不存在返回 404
- 错误统一 `{code, message}`（NOT_FOUND / INVALID_PARAM）
- 用表格驱动测试（ph08 风格）覆盖 200 / 400 / 404 / 405

**验收**：`go test -v` 全部通过；`go vet ./...` 零报告；`go test -cover` 覆盖率 ≥ 80%。

> 提示：参考 examples/ex01-routing；query 参数 `r.URL.Query().Get("status")`，枚举校验用白名单判断。

---

四道练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
