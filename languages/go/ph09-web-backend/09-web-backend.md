# Go Web 后端开发阶段

> 面向后端服务、云原生和车联网数据平台方向，本阶段把"会写接口"升级为"能交付 API 服务"——用标准库 net/http 搭起可维护、可测试、可上生产的后端 API。

## 1. 概述

Go Web 后端开发阶段的目标是：**能用 Go 写后端 API 服务**——掌握 REST 接口设计、路由与 handler、中间件、JSON 请求响应与参数校验、JWT/Cookie 认证、文件上传与模板渲染、日志与错误码、超时与限流。ph07 用标准库 net/http 写了第一个 API（HandleFunc + 前缀路由），ph08 学会了验证接口的测试方法（httptest + 依赖注入），本阶段把这些能力升级为"可以交付给前端、车机端对接的生产级 API 服务"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| HTTP 与 REST | 方法语义、状态码、资源路径设计 |
| 路由与 handler | Go 1.22 ServeMux 方法路由、通配符 `{id}`、PathValue、子 mux 分组 |
| JSON 请求响应 | encoding/json 解码编码、JSON tag、统一响应与错误结构 |
| 参数校验 | 手写校验（必填/范围/枚举/类型）+ 校验辅助函数 |
| 认证与会话 | JWT 无状态认证（HS256 原理与手写实现）、Cookie/Session、CORS |
| 文件与静态资源 | multipart 上传（防穿越 + 大小限制）、http.FileServer |
| 模板渲染 | html/template（自动转义防 XSS）、表单 POST |
| 稳定性与工程 | log/slog 结构化日志、错误码、超时（context）、限流、优雅关闭 |

本阶段的核心信念是"**接口即产品**"：API 的字段命名、错误结构、状态码、认证方式都是对外契约，一旦上线就难以修改——设计在前、实现在后，handler 只做编排、业务抽离成独立函数或 service 层。

这个阶段只涉及单体 HTTP 服务的完整闭环（承接 ph07 标准库阶段的 net/http 入门、ph08 测试与工程质量阶段的 httptest 与依赖注入），**不涉及数据库（MySQL/Redis 接入、ORM、事务属 ph10）、微服务与 RPC（gRPC、服务注册发现属 ph11）、云原生部署（容器与 Kubernetes 属 ph12）、消息队列（Kafka/MQTT 属 ph19）** — 本阶段数据全部存内存 map、接口全部是单体 HTTP。

## 2. 来源与演变

2009 年 Go 发布时 **net/http** 就内置了生产级 HTTP 服务器，Go 1.0（2012）起 `http.Handler` 接口与 `http.ServeMux` 成为标准库最稳定的部分之一。**中间件模式是标准库天然长出来的**：`func(http.Handler) http.Handler` 一层层包装 handler，所有后续框架都沿用这个"洋葱模型"。标准库自身持续演进：Go 1.8（2017）加入 `http.Server.Shutdown` 优雅关闭；Go 1.21（2023）加入 **log/slog** 结构化日志；**Go 1.22（2024）给 ServeMux 加入方法匹配与通配符路由**（`GET /devices/{id}`、`r.PathValue`），"纯标准库写 REST API"成为现实——这也是本阶段示例如此简洁的原因。

框架生态方面：2014 年 **Gin** 发布——针对当时流行的 martini 框架"依赖反射、性能差"的缺点重写，采用 radix tree 路由 + 原生 net/http，迅速成为 Go 最流行的 Web 框架；2015 年 **Echo**（radix tree + 自带参数校验）、**Chi**（标准库兼容、极简可组合）先后出现；2018 年 **Fiber** 受 Node.js Express 启发、基于 **fasthttp**（不走 net/http 标准栈）主打极致性能。REST 风格方面，2000 年 Roy Fielding 博士论文提出 REST，2000 年代中期 JSON 取代 XML 成为 API 主流报文；认证方面，**JWT**（RFC 7519，2015 年）把"无状态认证"变成前后端分离与微服务的标配。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Go 1.0 | 2012 | net/http、encoding/json、html/template 随语言发布，Handler 接口定型 |
| Go 1.7 | 2016 | context 移入标准库，http.Request 携带 Context |
| Go 1.8 | 2017 | http.Server.Shutdown / RegisterOnShutdown 优雅关闭进入标准库 |
| Go 1.21 | 2023 | log/slog 结构化日志进入标准库 |
| Go 1.22 | 2024 | ServeMux 方法匹配与通配符路由（`GET /devices/{id}`、PathValue） |
| 框架生态 | 2014~2018 | Gin（radix tree）、Echo、Chi、Fiber 出现（本阶段仅作选型背景） |

| 框架 | 诞生 | 路由实现 | 底层 | 特点 | 适用场景 |
|------|------|---------|------|------|---------|
| Gin | 2014 | radix tree | net/http | 生态最大、中间件丰富、事实标准 | 通用后端 API |
| Echo | 2015 | radix tree | net/http | 自带参数校验、API 精简 | 偏好内置能力的团队 |
| Chi | 2015 | 兼容 ServeMux | net/http | 极简、与标准库生态互通 | 标准库风格小服务 |
| Fiber | 2018 | 类 Express | fasthttp | 极致性能、非标准栈 | 高吞吐低延迟场景 |
| net/http | 2009 | Go 1.22 方法路由 | — | 零依赖、官方演进 | 简单接口、学习原理（本阶段示例主线） |

本文示例以 **Go 1.22** 为基线（本阶段核心是 ServeMux 方法路由与通配符，需 Go 1.22+），验证工具链 go1.25.6（darwin/arm64），**仅使用标准库**（受示例验证环境约束，不引入第三方框架；框架只是选型背景）。net/http 的 Handler 接口与中间件模式从 Go 1.0 至今保持向后兼容，是本阶段最稳定的部分——把标准库原理学透后，切到 Gin/Chi 只是换一层 API 壳。

## 3. 语法与参数

### 3.1 HTTP 与 REST 基础（方法/状态码/资源）

```go
// 最小可运行示例（完整版见 examples/ex01-routing/main.go）
// 验证环境：go1.25.6，仅标准库，命令：go run .
package main

import (
	"log"
	"net/http"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices/{id}", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("查询设备: " + r.PathValue("id"))) // 200 OK
	})
	mux.HandleFunc("POST /devices", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated) // 201 创建成功
	})
	log.Fatal(http.ListenAndServe("127.0.0.1:18080", mux))
}
```

| 方法 | 语义 | 典型状态码 |
|------|------|-----------|
| GET | 查询（幂等） | 200 / 404 |
| POST | 创建 | 201 / 400 / 409 |
| PUT / PATCH | 整体 / 部分更新 | 200 / 204 / 404 |
| DELETE | 删除 | 204 / 404 |

要点：REST 把动作语义交给 HTTP 方法——**GET 读、POST 建、PUT/PATCH 改、DELETE 删**，资源用复数名词 + id 表达（`/devices/{id}`）；**状态码是响应语义的一半**（200/201/204 成功族、400/401/403/404/409 客户端族、429 限流、5xx 服务端族）。**坑：不要用 200 表达一切**——"查询不存在返回 200 + error 字段"是常见坏味道，正确做法是 404 + 统一错误结构（3.4）。

### 3.2 路由与 handler（Go 1.22 ServeMux 方法路由）

```go
// 路由注册（完整版见 examples/ex01-routing/main.go 的 newMux）
// 验证环境：go1.25.6，仅标准库
func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices", listDevices(s))         // 方法 + 精确路径
	mux.HandleFunc("GET /devices/{id}", getDevice(s))      // 方法 + 通配符
	mux.HandleFunc("POST /devices", createDevice(s))
	mux.HandleFunc("DELETE /devices/{id}", deleteDevice(s))
	return mux
}

// 分组写法：子 mux + http.StripPrefix（完整版见 examples/ex04-jwt-auth/main.go）
api := http.NewServeMux()
api.HandleFunc("GET /profile", handleProfile)
mux.Handle("/api/", requireAuth(http.StripPrefix("/api", api))) // 只有 /api 下需要鉴权
```

要点：Go 1.22 起 ServeMux 支持 `METHOD /pattern` 写法——**方法 + 路径模式一次声明**，`{id}` 匹配单个路径段，`r.PathValue("id")` 取值；`{path...}` 匹配含斜杠的剩余路径（如 `/files/{path...}`）。**方法不匹配时 ServeMux 自动返回 405 并带 Allow 头**（ex01 测试里有断言）。**坑：`{id}`（标准库）与 `:id`（Gin）通配符语法不同**，混用会匹配失败；`{id}` 不匹配空段，`GET /api/devices/` 会 404 而非命中 `{id}`。优先级规则：字面量 > 通配符，方法限定 > 无方法限定（详见 4.2）。

### 3.3 JSON 请求响应与参数校验（Decode + 手写校验 + 四段式）

```go
// 创建接口（完整版见 examples/ex03-todo-api/main.go 的 handleCreate）
// 验证环境：go1.25.6，仅标准库
func handleCreate(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct { // 解析：JSON tag 决定字段名（ph07 已学）
			Text string `json:"text"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil { // 解析失败
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if req.Text == "" { // 校验：必填（标准库无声明式 validator，手写）
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能为空")
			return
		}
		if len([]rune(req.Text)) > 100 { // 校验：长度上限（[]rune 数中文按 1 字符）
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "text 不能超过 100 个字符")
			return
		}
		t, err := s.create(req.Text) // 业务
		if err != nil {
			writeError(w, http.StatusInternalServerError, "INTERNAL", "创建失败")
			return
		}
		writeJSON(w, http.StatusCreated, t) // 响应：201
	}
}
```

要点：**json.NewDecoder(r.Body).Decode 一步把请求体变成结构体**；query 参数用 `r.URL.Query().Get("status")`，路径参数用 `r.PathValue` + `strconv.Atoi`（整数解析 + 范围判断）；枚举用白名单判断（如 status 只能是 online/offline）。**handler 四段式**（必会概念）：解析 → 校验 → 业务 → 响应，业务逻辑抽到独立函数或 service 层，handler 只做编排。**坑：字段名与 tag 不一致时绑定静默失败**——前端传 `name` 而结构体只有 tag 为 `text` 的字段，绑定得到零值且不报错，必填校验必须显式写；**注意 encoding/json 的键匹配是大小写不敏感的**——传 `Text` 会命中 `json:"text"`（误绑本身也是坑），要严格区分字段名需在反序列化后显式校验；**坑：Decode 不会报"缺字段"**——缺 `text` 字段时结构体为零值，靠 3.3 的手写必填校验兜底；**坑：json 编码默认做 HTML 转义**——`<`、`>`、`&` 会输出为 `\u003c`、`\u003e`、`\u0026`（防注入的默认行为），API 返回含 HTML 的文本时前端拿到的是转义序列，业务确实信任输出时才用 `json.Encoder.SetEscapeHTML(false)` 关闭。

### 3.4 响应与统一错误结构

```go
// 统一错误结构（完整版见 examples/ex01-routing/main.go 的 writeError）
// 验证环境：go1.25.6，仅标准库
func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}
```

要点：**API 错误结构要统一**（必会概念）——固定 `{code, message}`，code 给程序分支判断（稳定枚举，如 INVALID_PARAM / NOT_FOUND / UNAUTHORIZED）、message 给人读，所有错误只走 `writeError` 一个入口。**坑：错误结构不统一**——这个接口 `{"error":"..."}`、那个接口 `{"msg":...}`，前端与文档无法收敛；**坑：code 别用中文或自由文本**——用稳定枚举，跨版本不变。

### 3.5 middleware 中间件（日志·恢复·CORS·限流）

```go
// 中间件本质（完整版见 examples/ex02-middleware/main.go）
// 验证环境：go1.25.6，仅标准库
func withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r) // 放行：执行后续中间件与最终 handler
		// 结构化日志（3.9）：key-value 对输出，配采集系统可检索
		logger.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", rec.status,
			"duration", time.Since(start),
		)
	})
}

// 洋葱模型组装器：先挂的先执行（外层）
func chain(h http.Handler, middlewares ...func(http.Handler) http.Handler) http.Handler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		h = middlewares[i](h)
	}
	return h
}
```

要点：**中间件本质是 `func(http.Handler) http.Handler` 的包装**——在 ServeHTTP 前后注入逻辑再调用内层，这就是洋葱模型：请求从外到内、响应从内到外；**执行顺序 = 挂载顺序**（先挂的在最外层先执行）。**中间件适合横切逻辑**（必会概念）——日志、恢复、CORS、限流、鉴权与业务无关，全部放中间件，业务规则绝不进中间件。`statusRecorder` 包装 ResponseWriter 是为了捕获状态码（net/http 不直接暴露）。**坑：panic 恢复缺失**——不挂恢复中间件时 handler panic 会掐断连接、客户端收不到响应；net/http 内建 recover 虽会向 server 日志写一行 `http: panic serving` + 堆栈，但没有请求上下文，生产必挂恢复中间件；**坑：CORS 的 `Allow-Origin: *` 不能与 `Allow-Credentials: true` 并用**——带 Cookie 的跨域要按域名白名单回显 Origin。

### 3.6 认证：JWT（手写 HS256）与 Cookie/Session

```go
// 手写 HS256 JWT 签发/验签（完整版见 examples/ex04-jwt-auth/jwt.go）
// 验证环境：go1.25.6，仅标准库（crypto/hmac + crypto/sha256 + encoding/base64 + encoding/json）
func signJWT(claims map[string]any, secret []byte, ttl time.Duration) (string, error) {
	withExp := make(map[string]any, len(claims)+1)
	for k, v := range claims {
		withExp[k] = v
	}
	withExp["exp"] = time.Now().Add(ttl).Unix()

	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	payload, err := json.Marshal(withExp)
	if err != nil {
		return "", err
	}
	enc := base64.RawURLEncoding
	signing := enc.EncodeToString(header) + "." + enc.EncodeToString(payload)

	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(signing))
	return signing + "." + enc.EncodeToString(mac.Sum(nil)), nil
}

// 鉴权中间件（完整版见 examples/ex04-jwt-auth/main.go 的 requireAuth）
func requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "缺少 Bearer token")
			return
		}
		claims, err := verifyJWT(token, secret)
		if err != nil {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", err.Error())
			return
		}
		ctx := context.WithValue(r.Context(), ctxKey{}, claims["username"]) // 用户写入 context
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
```

要点：**JWT 是无状态认证**——token 自带 claims（用户、过期时间），服务端验签即可、不存会话，适合前后端分离与水平扩展（结构详解见 4.4）；**Cookie/Session 是有状态会话**——`SetCookie` 后浏览器自动携带。**坑：payload 只是 base64 不是加密**——不能放密码等敏感信息；Cookie 必须设 HttpOnly / Secure / SameSite，否则 XSS 可窃取、CSRF 可冒用；密钥泄露 = 可伪造任意用户——HS256 对称密钥放环境变量并定期轮换；验签必须重算签名比对（防篡改），生产建议用 `github.com/golang-jwt/jwt/v5`（第三方模块，本阶段不引入，教学用手写实现完整可运行）。

### 3.7 文件上传与静态文件（multipart + 防穿越 + FileServer）

```go
// 上传接口（完整版见 exercises/sol-03-file-upload/main.go 的 handleUpload）
// 验证环境：go1.25.6，仅标准库
const maxUploadSize = 10 << 20 // 10MB

func handleUpload(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize) // 1. 大小限制：超限 413
	file, header, err := r.FormFile("file")                // 2. 取 multipart 文件
	if err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			writeError(w, http.StatusRequestEntityTooLarge, "FILE_TOO_LARGE", "文件超过 10MB 限制")
			return
		}
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "缺少 file 字段")
		return
	}
	defer file.Close()
	name := fmt.Sprintf("%d-%s", time.Now().UnixNano(), filepath.Base(header.Filename)) // 3. 命名
	dst, err := os.Create(filepath.Join(uploadDir, name))                                // 4. 落盘
	...
}

// 静态文件一行挂载（完整版见 examples/ex05-template-static/main.go）
mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))
```

要点：`r.FormFile` 取 multipart 文件、`io.Copy` 落盘；**坑：文件名必须 `filepath.Base` 清洗**——否则 `../../etc/passwd` 路径穿越可覆盖任意文件，时间戳前缀防重名覆盖；**坑：大文件必须设大小限制**（`http.MaxBytesReader` 挂在 FormFile 之前），否则恶意大文件打满内存或磁盘；`http.FileServer` + `http.StripPrefix` 一行提供静态目录，`http.ServeFile` 按名回看单个文件。

### 3.8 模板渲染（html/template）

```go
// 模板解析与渲染（完整版见 examples/ex05-template-static/main.go）
// 验证环境：go1.25.6，仅标准库
var tmpl = template.Must(template.ParseFiles("templates/devices.html"))

func handleList(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		...
		if err := tmpl.Execute(w, list); err != nil { // 渲染错误也要处理
			log.Printf("模板渲染失败: %v", err)
			http.Error(w, "模板渲染失败", http.StatusInternalServerError)
		}
	}
}
```

要点：**html/template 自动 HTML 转义防 XSS**——设备名含 `<script>` 时输出 `&lt;script&gt;`，不会原样进 HTML（ex05 测试有断言）；**模板负责"给人看的页面"、JSON 负责"给程序看的"**——两者分工明确，API 返回 JSON、页面渲染走模板；`template.Must` 让解析失败在启动期暴露而非运行时才发现；表单 POST 用 `r.ParseForm` + `r.FormValue`，成功后 `http.Redirect`（303）回列表页实现 PRG（Post/Redirect/Get）防重复提交。

### 3.9 日志与错误码设计（log/slog）

```go
// 结构化日志（Go 1.21+ 标准库；请求日志的完整落地见 examples/ex02-middleware/main.go 的 withLogging）
// 验证环境：go1.25.6，仅标准库
var logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

func handleGetDevice(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	logger.Info("查询设备", "id", id, "ip", r.RemoteAddr) // key-value 对
	...
}
```

要点：**日志建议结构化**（JSON / key-value）——`log/slog`（Go 1.21+ 标准库）替代 ph07 的 log 包做业务日志，配合日志采集系统（ELK/Loki，ph12）才能检索。**错误码与 HTTP 状态码分层**——HTTP 状态码表达语义大类（4xx/5xx），业务错误码表达具体原因（INVALID_PARAM / NOT_FOUND），code 进响应体与日志；**坑：错误码随手写**（一律 -1）会无法定位——集中定义常量并写进 API 文档。

### 3.10 稳定性：超时、限流与优雅关闭

```go
// server 显式超时（完整版见 examples/ex06-graceful-shutdown/main.go 的 buildServer）
// 验证环境：go1.25.6，仅标准库
srv := &http.Server{
	Addr:              "127.0.0.1:18081",
	Handler:           mux,
	ReadHeaderTimeout: 5 * time.Second,  // 读请求头超时（必设，防 Slowloris）
	ReadTimeout:       10 * time.Second, // 读完整请求体超时
	WriteTimeout:      10 * time.Second, // 写响应超时
	IdleTimeout:       60 * time.Second, // keep-alive 空闲连接超时
}

// 优雅关闭：等信号 → 停止接收新连接 → 给存量请求 10 秒
quit := make(chan os.Signal, 1)
signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
<-quit
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
if err := srv.Shutdown(ctx); err != nil {
	log.Fatalf("优雅关闭超时，强制退出: %v", err)
}
```

要点：**超时和限流是服务稳定性的基础**（必会概念）——超时分两层：HTTP server 的 Read/Write/IdleTimeout（防慢客户端拖死连接）+ 每请求 context 超时（`context.WithTimeout(r.Context(), d)` 中间件，下游调用自动感知）；**context 必须一路传给下游调用**，否则慢依赖拖死 goroutine（呼应 ph06 泄漏）；限流用**窗口限流**（ex02 的每 IP 实现是滑动时间窗日志：按时间戳剪枝计数，窗口内次数到上限即 429）或**令牌桶**（生产用 `golang.org/x/time/rate`，第三方，本阶段不引入）。**优雅关闭让存量请求处理完再退出**——`srv.Shutdown(ctx)` 停止接收新连接、等待在途请求完成、超时强制退出，实测退出码 0（见 ex06 冒烟测试）。**坑：只设 server 超时不设 context**——handler 内部调用不感知超时；客户端断开后业务继续算——select 监听 `r.Context().Done()`。

### 3.11 API 文档（OpenAPI 提示）

要点：**API 文档推荐 OpenAPI/Swagger 生态**——Go 侧常用 `swaggo/swag` 注释注解 + `swag init` 生成 openapi.json，gin-swagger / swaggo 提供在线文档页；**文档与代码同源**（注释驱动），改接口必须同步改注解，否则"文档撒谎"。本阶段不引入第三方文档工具（未在本环境验证），轻量接口可手写 openapi.yaml 描述。属于工程化进阶，深入在 ph12 云原生与部署阶段配合 CI 落地。

## 4. 底层原理

### 4.1 net/http 的 Handler 与中间件链

- 核心接口：`type Handler interface { ServeHTTP(w ResponseWriter, r *Request) }`；**HandlerFunc 把普通函数适配成 Handler**；ServeMux 本身也是一个 Handler——"路由"就是"按模式把请求分发到子 Handler"
- **中间件本质是 `func(http.Handler) http.Handler` 的包装**：在 ServeHTTP 前后注入逻辑再调用内层——洋葱模型，请求从外到内、响应从内到外；Gin 的 `c.Next()` 是同一思想的另一种实现
- 连接模型：**net/http 为每个连接起一个 goroutine**，handler 在 goroutine 中执行——这正是 ph06"goroutine 廉价"的落地，高并发靠 goroutine 而非线程池

### 4.2 ServeMux 的路由匹配（Go 1.22 树结构与优先级）

- Go 1.22 起 ServeMux 用 **trie 树**组织模式：公共前缀合并成同一节点，`{id}` 是通配节点——**匹配复杂度 O(路径长度)、与注册路由数无关**（Go 1.22 之前是线性遍历，这也是 Go 1.22 路由增强的动机）
- 优先级规则（**更具体者优先**）：**字面量段 > 通配符段**；**有方法限定 > 无方法限定**（`GET /devices` 比 `/devices` 更具体）；**精确模式 > 子树模式**（`GET /api/devices` 优先于 `/api/`）。注：旧版 ServeMux 的「最长前缀匹配」概念在 Go 1.22 已废弃——两个模式都匹配时按"匹配更少请求者胜出"（集合包含）判定，无法比较时注册直接 panic
- 方法不匹配但路径匹配时返回 **405 + Allow 头**（列出允许的方法）——这是标准库行为，ex01 测试有断言

### 4.3 请求生命周期（连接·超时·context 取消）

```text
accept 连接 ──▶ 读请求头/体 ──▶ 路由 ──▶ 中间件链（依次 Next）──▶ handler ──▶ 写响应 ──▶ keep-alive 回池
                          ▲                                │
                          └──── 每请求一棵 context 树（超时/取消派生子 context）────┘
```

- **每个请求都有一棵 context 树**：根是 `r.Context()`，超时 / 取消派生子 context；客户端断开、server 超时、主动 cancel 都会触发 `ctx.Done()`——所有阻塞 I/O 都要监听它（ph10 大量使用）
- 泄漏场景：handler 里 `go func()` 起的 goroutine 若不接收 ctx，客户端断开后仍继续跑——**超时与 context 传播是防 goroutine 泄漏的钥匙**（呼应 ph06）

### 4.4 JWT 的结构与 HMAC 验签（无状态认证）

- 结构：`header.payload.signature` 三段 base64url——header 声明算法（`{"alg":"HS256"}`）、payload 放 claims（`sub` / `exp` / `iat` / 自定义字段）、**signature = HMAC-SHA256(header.payload, secret)**
- 验签流程：服务端用同一 secret 重算签名，`hmac.Equal` 常数时间比对——**能验签 = 未被篡改 = 可信**；`exp` 过期即失效；全程不查数据库、不存会话，这就是"**无状态**"：任意实例都能独立验证，天然适合水平扩展（ph11 微服务友好）
- **代价**：无法主动吊销（token 被盗只能等过期，除非维护黑名单）；payload 不加密（base64 可读，不能放敏感信息）；密钥管理决定安全性（对称密钥泄露 = 可伪造一切 token）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 前后端分离的 REST API | 路由、JSON 请求响应、CORS、统一错误 |
| 车机 / 移动端数据上报接口 | 参数校验、限流、日志、错误码（见 project/） |
| 后台管理系统接口 | 登录、JWT/Cookie 认证、中间件鉴权 |
| 管理后台页面（服务端渲染） | html/template、表单 POST、静态文件 |
| 图片 / 日志 / 固件上传 | multipart、静态文件服务、防穿越 |
| 面向第三方的开放 API | API 文档（OpenAPI）、错误码、限流 |
| 服务健康检查与探活 | 路由、JSON、优雅关闭 |
| 内部服务的简单 HTTP 接口 | 超时、context、恢复中间件 |

**不适合**此阶段的事项：

- **数据库接入与 ORM**（MySQL/Redis、事务、连接池、迁移）：属 ph10——本阶段数据一律内存 map
- **gRPC 与微服务**（服务注册发现、配置中心、负载均衡、契约测试）：属 ph11——本阶段只做单体 HTTP
- **云原生部署**（容器化、Kubernetes、Helm、可观测性平台）：属 ph12
- **消息队列与异步解耦**（Kafka / RabbitMQ / MQTT）：属 ph19
- **前端工程化与全栈**（React/Vue 构建、SSR）：不属于本 roadmap 的 Go 主线

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64），仅标准库；全部示例已通过 `go vet ./...` 与 `go test ./...`（详见 examples/README.md 的实测数据表）。

### 示例 1：路由与 JSON API（ServeMux 方法路由 + PathValue）

```go
// examples/ex01-routing/main.go —— 设备 API：GET/POST/DELETE + {id} 通配符 + query 过滤
// 验证环境：go1.25.6，命令：go test -v ./...；go run . 后 curl http://127.0.0.1:18080/devices
func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices", listDevices(s))
	mux.HandleFunc("GET /devices/{id}", getDevice(s)) // r.PathValue("id") 取通配符值
	mux.HandleFunc("POST /devices", createDevice(s))
	mux.HandleFunc("DELETE /devices/{id}", deleteDevice(s))
	return mux
}
```

要点：完整示例含 14 个 httptest 用例（TestRoutes 12 个子用例 + 2 个专项断言，200/201/204/400/404/405/409 全覆盖），`go test -cover` 实测覆盖率 92.1%；405 时 ServeMux 自动带 Allow 头（有断言）。**完整文件**：`examples/ex01-routing/`（go.mod + main.go + main_test.go）。

### 示例 2：中间件组合（日志 + 恢复 + CORS + 限流）

```go
// examples/ex02-middleware/main.go —— 四个横切关注点合成一个服务
// 验证环境：go1.25.6，命令：go test -v ./...
handler := chain(newMux(), withLogging, withRecovery, withCORS, withRateLimit(30, time.Minute))
```

要点：洋葱模型完整落地——执行顺序 = 挂载顺序；`statusRecorder` 捕获状态码（日志中间件用 log/slog 结构化输出）、恢复中间件把 panic 转成 500、CORS 处理 OPTIONS 预检、窗口限流（滑动时间窗日志）每 IP 每窗口 30 次（超限 429，有断言）；`go test -cover` 实测 89.7%。**完整文件**：`examples/ex02-middleware/`（go.mod + main.go + main_test.go）。

### 示例 3：Todo API（JSON + 校验 + 统一错误 + Mutex）

```go
// examples/ex03-todo-api/main.go —— 五方法 CRUD，handler 四段式（解析→校验→业务→响应）
// 验证环境：go1.25.6，命令：go test -v ./...；go test -race（并发用例）
mux.HandleFunc("GET /todos", handleList(s))
mux.HandleFunc("POST /todos", handleCreate(s))
mux.HandleFunc("PATCH /todos/{id}/done", handleMarkDone(s))
mux.HandleFunc("PUT /todos/{id}", handleUpdate(s))
mux.HandleFunc("DELETE /todos/{id}", handleDelete(s))
```

要点：内存切片存储 + Mutex（并发创建 100 个 goroutine 不丢数据，`-race` 实测通过）；必填与长度校验手写；`go test -cover` 实测 84.1%。**完整文件**：`examples/ex03-todo-api/`（go.mod + main.go + main_test.go）。

### 示例 4：JWT 认证（手写 HS256 + 中间件鉴权）

```go
// examples/ex04-jwt-auth/jwt.go —— 标准库手写 HS256：header.payload.signature + HMAC 验签
// 验证环境：go1.25.6，命令：go test -v ./...；go test -bench=. -benchmem -run=^$
token, err := signJWT(map[string]any{"username": cred.Username}, secret, 2*time.Hour)
...
claims, err := verifyJWT(token, secret) // hmac.Equal 常数时间比对 + exp 校验
```

要点：登录签发 JWT、requireAuth 中间件验签鉴权（Bearer 解析 → 验签 → 用户名写入 context）、子 mux + StripPrefix 只保护 `/api` 分组；篡改 / 错误密钥 / 过期 / 坏格式 10 个用例全过，`go test -cover` 实测 82.4%；签发 benchmark 实测约 **1299 ns/op、2236 B/op、33 allocs/op**（同机多次运行 ns/op 有 ±10% 波动、allocs 稳定，仅量级参考；登录这种低频操作完全可忽略）。**完整文件**：`examples/ex04-jwt-auth/`（go.mod + jwt.go + main.go + jwt_test.go + main_test.go）。

### 示例 5：模板 + 静态文件（html/template + FileServer）

```go
// examples/ex05-template-static/main.go —— 设备状态页 + 表单 POST + /static 静态资源
// 验证环境：go1.25.6，命令：go test -v ./...
var tmpl = template.Must(template.ParseFiles("templates/devices.html"))
mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))
```

要点：html/template 自动转义（设备名 `<script>` 渲染为 `&lt;script&gt;`，有断言）；表单校验 + 303 重定向（PRG 模式）；`go test -cover` 实测 79.5%。**完整文件**：`examples/ex05-template-static/`（go.mod + main.go + main_test.go + templates/devices.html + static/style.css）。

### 示例 6：优雅关闭（http.Server + 信号）

```go
// examples/ex06-graceful-shutdown/main.go —— 显式超时 + SIGINT/SIGTERM + Shutdown(ctx)
// 验证环境：go1.25.6，冒烟测试：见文件头部注释的脚本
srv := &http.Server{Addr: "127.0.0.1:18081", Handler: mux,
	ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 60 * time.Second, ...}
```

要点：ReadHeaderTimeout 防 Slowloris、Read/Write/Idle 超时齐全；信号监听 → `srv.Shutdown(ctx)` 优雅关闭；本地端口冒烟实测：`curl /healthz` 返回 ok，SIGTERM 后日志依次输出"收到退出信号 → 所有连接已处理完毕"，退出码 0，无残留进程。**完整文件**：`examples/ex06-graceful-shutdown/`（go.mod + main.go + main_test.go）。

## 7. 总结

### 关键要点

1. **handler 要清晰分离解析、校验、业务和响应**（必会概念）：四段式结构，业务抽独立函数 / service，handler 只做编排
2. **中间件适合横切逻辑**（必会概念）：日志、恢复、CORS、限流、鉴权都放中间件，业务规则绝不进中间件
3. **API 错误结构要统一**（必会概念）：固定 `{code, message}`，code 给程序、message 给人，所有错误一个入口
4. **超时和限流是服务稳定性的基础**（必会概念）：server 超时 + context 超时双层防护，限流防单点被打爆，优雅关闭保在途请求
5. **REST 是"方法 + 资源 + 状态码"的三元组**：GET/POST/PUT/PATCH/DELETE 语义分明，状态码表达响应语义，别用 200 表达一切
6. **JSON 请求响应靠 tag 对齐协议**：字段名、required、omitempty 是接口契约的一部分（ph07 延续），必填校验手写兜底
7. **JWT 无状态、Cookie 有状态**：token 验签即可信、不存会话；payload 不加密、密钥要保密、Cookie 要 HttpOnly
8. **Go 1.22 ServeMux 是零依赖的 REST 底座**：方法路由 + 通配符 + 405 自动处理 + trie 树匹配，简单接口不需要框架
9. **模板与 JSON 分工**：html/template 给人看（自动转义防 XSS）、JSON 给程序看
10. **上传安全三件套**：filepath.Base 防穿越、大小限制防打爆、时间戳防重名

### 跨语言对比：Web 框架与 API 设计

| 维度 | Go net/http | Java Spring Boot | Python FastAPI | Node Express | Rust Axum |
|------|-------------|-----------------|---------------|-------------|-----------|
| 典型框架 | net/http / Gin | Spring MVC（Servlet） | FastAPI（ASGI） | Express（中间件栈） | Axum（tower） |
| 路由风格 | 方法 + `{id}` / `:param` | 注解 @GetMapping | 装饰器 + 路径参数 | app.get('/:id') | 宏 + 路径提取器 |
| 参数校验 | 手写（或第三方 validator） | jakarta validation 注解 | Pydantic 类型注解 | 手写 / zod | 提取器 + validator |
| 中间件/横切 | func(http.Handler) http.Handler | Filter / Interceptor | 依赖注入中间件 | app.use 链 | tower Layer |
| 异步模型 | goroutine（同步写法） | 线程池 / 虚拟线程 | asyncio 协程 | 事件循环 | tokio 异步 |
| API 文档 | swag 注释生成 OpenAPI | springdoc | 自动 OpenAPI | swagger-jsdoc | utoipa 宏 |

### 阶段验收清单

- [ ] **能设计 REST 接口**：资源路径、方法语义、状态码选择合理，能讲清"为什么这样设计"
- [ ] **能用 Go 1.22 ServeMux 写路由**：方法路由 + 通配符 + PathValue，能说清 405 / 404 的触发条件与优先级规则
- [ ] **能处理参数校验和统一错误**：手写必填 / 枚举 / 范围校验，所有错误走统一 `{code, message}` 结构
- [ ] **能写出基础认证流程**：手写 HS256 JWT 签发与验签（或讲清其原理），中间件校验 Bearer token，未授权访问被拒绝（401）
- [ ] **能组合中间件**：日志、恢复、CORS、限流四件套组合成服务，能说清执行顺序与洋葱模型
- [ ] **能解释服务稳定性手段**：说出超时两层（server + context）与限流的作用，能复现 429 与优雅关闭场景
- [ ] **接口可测试**：ph08 的 httptest 直接套用（handler 实现 http.Handler，`ServeHTTP(rec, req)` 即可）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap「练习」小节一一对应：

1. **Todo API**（★★）：五方法 CRUD + 内存存储 + 并发安全 + done 过滤（提示：示例 1/3）
2. **登录注册 + JWT**（★★★）：注册 409 查重、登录签发 JWT、中间件鉴权（提示：示例 4）
3. **文件上传服务**（★★）：multipart + 防穿越 + 10MB 限制 + 回看（提示：3.7 小节）
4. **设备状态查询 API**（★）：列表过滤 + 详情 + 统一错误 + 表格驱动测试（提示：示例 1）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**车辆数据上报 API**——车机端定时上报位置 / 速度 / 状态，接口含鉴权（设备 JWT token）、参数校验（速度范围、坐标合法）、限流（每设备每分钟 N 次）、统一错误码，数据暂存内存 map（ph10 换数据库）。它是本阶段全部知识点的合体：示例 4（JWT）+ 示例 3（校验与错误）+ 示例 2（限流）+ 示例 6（优雅关闭）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（go test / go vet / -race / 冒烟）

roadmap 第二个推荐项目「后台管理服务」（管理员登录 + 用户/设备 CRUD + 操作日志 + 分页过滤）可在完成后作为扩展：复用本项目的 JWT 与统一错误结构，加 log/slog 操作日志与分页校验即可。

### 下一阶段

[数据库阶段](../ph10-database/10-database.md) —— SQL 与 database/sql / sqlx / gorm、事务与连接池、MySQL/PostgreSQL、Redis 缓存与 go-redis、索引与慢查询、迁移；本阶段"内存 map 存数据"的全部接口将换成真实数据库，JWT 用户存储与设备状态写入也会落库。
