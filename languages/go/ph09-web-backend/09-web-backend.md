# Go Web 后端开发阶段

> 面向后端服务、云原生和车联网数据平台方向，本阶段把"会写接口"升级为"能交付 API 服务"——用 Gin 生态搭建可维护、可测试、可上生产的后端 API。

## 1. 概述

Go Web 后端开发阶段的目标是：**能用 Go 写后端 API 服务**——掌握 REST 接口设计、路由与 handler、middleware 中间件、JSON 请求响应与参数校验、JWT/Cookie 认证、文件上传、日志与错误码、API 文档与限流，熟悉 Gin/Echo/Fiber/Chi 生态并能选型。ph07 用标准库 net/http 写了第一个 API，ph08 学会了验证接口的测试方法，本阶段把这些能力升级为"可以交付给前端、车机端对接的生产级 API 服务"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| HTTP 与 REST | 方法语义、状态码、资源路径设计、net/http 与 Gin 路由 |
| 路由与 handler | Gin 为主（:param、分组路由），对比标准库 Go 1.22 方法路由 |
| JSON 请求响应 | ShouldBindJSON 绑定、JSON tag、统一响应与错误结构 |
| 参数校验 | binding tag + validator（required/oneof/min/max） |
| 认证与会话 | JWT 无状态认证、Cookie/Session、CORS |
| 文件与静态资源 | multipart 上传、r.Static 静态文件服务 |
| 稳定性与工程 | 日志（log/slog）、错误码、OpenAPI 文档、超时与限流 |

本阶段的核心信念是"**接口即产品**"：API 的字段命名、错误结构、状态码、认证方式都是对外契约，一旦上线就难以修改——设计在前、实现在后，handler 只做编排、业务抽离成 service。

范围边界：承接 ph08 测试与工程质量（httptest 验证接口、依赖注入、质量工具链）；**不涉及**数据库（MySQL/Redis 接入属 ph10）、微服务与 RPC（gRPC、服务注册发现属 ph11）、云原生部署（容器与 Kubernetes 属 ph12）、消息队列（ph19）——本阶段数据全部存内存 map、接口全部是单体 HTTP。

## 2. 来源与演变

2009 年 Go 发布时 **net/http** 就内置了生产级 HTTP 服务器，早期 Go 后端生态围绕标准库展开。2014 年 **Gin** 发布——它针对当时流行的 martini 框架"依赖反射、性能差"的缺点重写，采用 **radix tree 路由** + 原生 net/http，迅速成为 Go 最流行的 Web 框架；2015 年 **Echo** 发布，同样基于 net/http 与 radix tree、自带参数校验；2018 年 **Fiber** 出现，受 Node.js Express 启发、基于 **fasthttp**（不走 net/http 标准栈），主打极致性能；**Chi** 则坚持"标准库兼容、极简可组合"，中间件直接复用 net/http 生态。

REST 风格方面，2000 年 Roy Fielding 博士论文提出 **REST（Representational State Transfer）**，2000 年代中期 **JSON** 取代 XML 成为 API 主流报文，"名词资源 + HTTP 方法 + 状态码"成为事实标准；2010 年代 **OpenAPI**（前身 Swagger）让 API 文档可以机器生成与校验。认证方面，**JWT**（RFC 7519，2015 年）把"无状态认证"变成前后端分离与微服务的标配，Cookie/Session 则延续浏览器时代的有状态会话模型。

Go 的**中间件模式**是标准库天然长出来的：`func(http.Handler) http.Handler` 一层层包装 handler，所有框架都沿用这个"洋葱模型"。标准库自身也在演进：**Go 1.22 给 ServeMux 加入方法匹配与通配符路由**（`GET /devices/{id}`、`r.PathValue`），"纯标准库写 REST API"成为现实——这也是 ph07 示例 3 在 Go 1.22 后如此简洁的原因。选型原则：**需求简单用标准库，需求复杂（校验、中间件生态、分组路由）用 Gin**。

| 框架 | 诞生 | 路由实现 | 底层 | 特点 | 适用场景 |
|------|------|---------|------|------|---------|
| Gin | 2014 | radix tree | net/http | 生态最大、中间件丰富、事实标准 | 通用后端 API（本阶段主选） |
| Echo | 2015 | radix tree | net/http | 自带参数校验、API 精简 | 偏好内置能力的团队 |
| Fiber | 2018 | 类 Express | fasthttp | 极致性能、非标准栈 | 高吞吐低延迟场景 |
| Chi | 2015 | 兼容 ServeMux | net/http | 极简、与标准库生态互通 | 标准库风格小服务 |
| net/http | 2009 | Go 1.22 方法路由 | — | 零依赖、官方演进 | 简单接口、学习原理 |

## 3. 语法与参数

### 3.1 HTTP 与 REST 基础（方法/状态码/资源）

```go
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
	log.Fatal(http.ListenAndServe("127.0.0.1:8080", mux))
}
```

| 方法 | 语义 | 典型状态码 |
|------|------|-----------|
| GET | 查询（幂等） | 200 / 404 |
| POST | 创建 | 201 / 400 / 409 |
| PUT / PATCH | 整体 / 部分更新 | 200 / 204 / 404 |
| DELETE | 删除 | 204 / 404 |

要点：REST 把动作语义交给 HTTP 方法——**GET 读、POST 建、PUT/PATCH 改、DELETE 删**，资源用**复数名词 + id** 表达（`/devices/{id}`）；**状态码是响应语义的一半**（200/201/204 成功族、400/401/403/404/409 客户端族、429 限流、5xx 服务端族）。**坑：不要用 200 表达一切**——"查询不存在返回 200 + error 字段"是常见坏味道，正确做法是 404 + 统一错误结构（3.4）。

### 3.2 路由与 handler（Gin 为主，对比标准库）

```go
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	r.GET("/ping", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"message": "pong"}) })
	r.GET("/devices/:id", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"id": c.Param("id")}) })
	r.GET("/devices", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": c.Query("status"), "page": c.DefaultQuery("page", "1")})
	})
	api := r.Group("/api") // 分组路由：统一前缀与中间件
	api.GET("/health", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"ok": true}) })
	r.Run("127.0.0.1:8080")
}
```

要点：Gin handler 签名固定 `func(c *gin.Context)`；**c.Param 取路径参数、c.Query / c.DefaultQuery 取查询参数、r.Group 分组**；对比标准库——Go 1.22 的 `GET /devices/{id}` + `r.PathValue`（ph07 示例 3）。**坑：`:id`（Gin）与 `{id}`（标准库）通配符语法不同**，混用会匹配失败；Gin 默认方法不匹配返回 404，严格 REST 应返回 405，可设 `r.HandleMethodNotAllowed = true`。

### 3.3 请求解析与 JSON 绑定（ShouldBindJSON 与校验）

```go
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

type ReportReq struct {
	DeviceID string  `json:"device_id" binding:"required"`
	Speed    float64 `json:"speed" binding:"required,gt=0"`
}

func main() {
	r := gin.Default()
	r.POST("/report", func(c *gin.Context) {
		var req ReportReq
		if err := c.ShouldBindJSON(&req); err != nil { // 解码 + 校验一步完成
			c.JSON(http.StatusBadRequest, gin.H{"error": "参数不合法: " + err.Error()})
			return
		}
		c.JSON(http.StatusOK, gin.H{"device_id": req.DeviceID, "speed": req.Speed})
	})
	r.Run("127.0.0.1:8080")
}
```

要点：**ShouldBindJSON 把"JSON 解码 + 参数校验"合为一步**——解码失败、required 缺失、gt=0 不满足都走 err；JSON tag 决定字段名（ph07 已学）。**坑：字段名与 tag 不一致时绑定静默失败**——前端传 `DeviceID` 而 tag 是 `device_id`，绑定得到零值且不报错；**handler 要清晰分离解析、校验、业务和响应**（必会概念），业务逻辑应抽到 service 层再返回。

### 3.4 响应与统一错误结构

```go
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

type ErrorBody struct {
	Code    string `json:"code"`    // 机器可读，稳定不变
	Message string `json:"message"` // 人可读
}

func fail(c *gin.Context, status int, code, msg string) {
	c.JSON(status, ErrorBody{Code: code, Message: msg})
}

func main() {
	r := gin.Default()
	r.GET("/devices/:id", func(c *gin.Context) {
		id := c.Param("id")
		if id == "" {
			fail(c, http.StatusBadRequest, "INVALID_PARAM", "缺少设备 ID")
			return
		}
		fail(c, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
	})
	r.Run("127.0.0.1:8080")
}
```

要点：**API 错误结构要统一**（必会概念）——固定 `{code, message}`（可扩展 details），code 给程序分支判断、message 给人读，所有错误只走 `fail` 一个入口。**坑：错误结构不统一**——这个接口 `{"error":"..."}`、那个接口 `{"msg":...}`，前端与文档无法收敛；**坑：code 别用中文或自由文本**——用稳定枚举（INVALID_PARAM / NOT_FOUND / UNAUTHORIZED），跨版本不变。

### 3.5 middleware 中间件（日志·恢复·CORS·限流）

```go
package main

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next() // 放行，执行后续 handler
		log.Printf("%s %s → %d (%s)", c.Request.Method, c.Request.URL.Path, c.Writer.Status(), time.Since(start))
	}
}

func main() {
	r := gin.New()                  // 空引擎，手动挂载演示组合
	r.Use(logger(), gin.Recovery()) // ① 请求日志 ② panic 恢复
	r.GET("/ping", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"message": "pong"}) })
	r.Run("127.0.0.1:8080")
}
```

要点：**中间件适合横切逻辑**（必会概念）——日志、恢复、CORS、限流、鉴权与业务无关，全部放中间件，业务规则绝不进中间件；**c.Next() 放行、c.Abort() 终止链**；`gin.Default()` = `gin.New()` + Logger + Recovery。**坑：panic 恢复缺失**——不挂 Recovery 时 handler panic 会中断响应且不留日志，生产必挂；**坑：中间件执行顺序 = 挂载顺序**（洋葱模型外层先执行，见示例 5）。

### 3.6 参数校验（binding tag 与 validator）

```go
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

type DeviceQuery struct {
	Status string `form:"status" binding:"omitempty,oneof=online offline"` // 枚举
	Page   int    `form:"page" binding:"omitempty,min=1"`                  // 最小 1
	Size   int    `form:"size" binding:"omitempty,min=1,max=100"`          // 范围 1..100
}

func main() {
	r := gin.Default()
	r.GET("/api/devices", func(c *gin.Context) {
		var q DeviceQuery
		if err := c.ShouldBindQuery(&q); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "参数不合法: " + err.Error()})
			return
		}
		c.JSON(http.StatusOK, q)
	})
	r.Run("127.0.0.1:8080")
}
```

要点：Gin 内置 **go-playground/validator**——binding tag 是声明式校验规则（`required` / `oneof` / `min` / `max` / `email` / `len` 等）；JSON 用 `json` tag + ShouldBindJSON，query 用 `form` tag + **ShouldBindQuery**，路径参数手动校验（`strconv.Atoi` + 范围判断）。**坑：required 把零值当缺失**——int 传 0、string 传 "" 都判为"缺失"，需默认值语义时改用 `omitempty`；validator 错误信息默认英文且啰嗦，生产要包装成 3.4 的统一结构。

### 3.7 JWT 认证与 Cookie/Session

```go
package main

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5" // go get github.com/golang-jwt/jwt/v5
)

func main() {
	r := gin.Default()
	r.GET("/login", func(c *gin.Context) {
		token, _ := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
			"username": "admin",
			"exp":      time.Now().Add(2 * time.Hour).Unix(),
		}).SignedString([]byte("secret"))
		c.SetCookie("session", token, 7200, "/", "", false, true) // HttpOnly 防 XSS 读取
		c.JSON(http.StatusOK, gin.H{"token": token})
	})
	r.GET("/me", func(c *gin.Context) {
		token, err := c.Cookie("session") // 浏览器自动携带 Cookie
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "未登录"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"session": token})
	})
	r.Run("127.0.0.1:8080")
}
```

要点：**JWT 是无状态认证**——token 自带 claims（用户、过期时间），服务端验签即可、不存会话，适合前后端分离与水平扩展（结构详解见 4.4）；**Cookie/Session 是有状态会话**——Set-Cookie 后浏览器自动携带。**坑：payload 只是 base64 不是加密**——不能放密码等敏感信息；Cookie 必须设 HttpOnly / Secure / SameSite，否则 XSS 可窃取、CSRF 可冒用；密钥泄露 = 可伪造任意用户——HS256 对称密钥放环境变量并定期轮换；完整"注册/登录 + 中间件鉴权"见示例 2。

### 3.8 文件上传与静态文件

```go
package main

import (
	"net/http"
	"os"
	"path/filepath"

	"github.com/gin-gonic/gin"
)

func main() {
	os.MkdirAll("./uploads", 0o755)
	r := gin.Default()
	r.POST("/upload", func(c *gin.Context) {
		f, err := c.FormFile("file")
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "缺少 file 字段"})
			return
		}
		name := filepath.Base(f.Filename) // 坑：必须清洗，防路径穿越
		if err := c.SaveUploadedFile(f, filepath.Join("./uploads", name)); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "保存失败"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"name": name, "size": f.Size})
	})
	r.Static("/files", "./uploads") // 一行挂静态文件目录
	r.Run("127.0.0.1:8080")
}
```

要点：`c.FormFile` 取 multipart 文件、`c.SaveUploadedFile` 保存；**默认单文件上限 32MB**（`r.MaxMultipartMemory` 可调）。**坑：文件名必须 `filepath.Base` 清洗**——否则 `../../etc/passwd` 路径穿越可覆盖任意文件；验证：`curl -F "file=@readme.txt" http://127.0.0.1:8080/upload`；大文件上传要流式 + 分片（本阶段掌握基础即可，示例 3 是完整版）。

### 3.9 日志与错误码设计

```go
package main

import (
	"log/slog"
	"os"

	"github.com/gin-gonic/gin"
)

var logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

func main() {
	r := gin.Default()
	r.GET("/devices/:id", func(c *gin.Context) {
		logger.Info("查询设备", "id", c.Param("id"), "ip", c.ClientIP()) // key-value
		c.JSON(200, gin.H{"id": c.Param("id")})
	})
	r.Run("127.0.0.1:8080")
}
```

要点：**日志建议结构化**（JSON / key-value）——`log/slog`（Go 1.21+ 标准库）替代 ph07 的 log 包做业务日志，配合日志采集系统（ELK/Loki，ph12）才能检索。**错误码与 HTTP 状态码分层**——HTTP 状态码表达语义大类（4xx/5xx），业务错误码表达具体原因（10001 参数缺失、10002 设备不存在），code 进响应体与日志；**坑：错误码随手写**（一律 -1）会无法定位——集中定义常量并写进 API 文档。

### 3.10 API 文档（OpenAPI/Swagger 提示）

```go
// 依赖: go get github.com/swaggo/gin-swagger github.com/swaggo/files github.com/swaggo/swag
// 先运行 swag init 生成 docs 包，再 go run .
package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

// PingHandler 健康检查
// @Summary 健康检查
// @Produce json
// @Success 200 {object} map[string]string
// @Router /ping [get]
func PingHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"message": "pong"})
}

func main() {
	r := gin.Default()
	r.GET("/ping", PingHandler)
	r.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerFiles.Handler)) // 在线文档页
	r.Run("127.0.0.1:8080")
}
```

要点：**API 文档推荐 OpenAPI/Swagger 生态**——注释注解 + `swag init` 生成 openapi.json，gin-swagger 提供可调试的在线文档页；**文档与代码同源**（注释驱动），改接口必须同步改注解。**坑：注解与实现不一致 = "文档撒谎"**——把 `swag init` / `swag fmt` 纳入 ph12 的 CI；轻量接口也可手写 openapi.yaml 用 go-swagger 校验。

### 3.11 超时与限流（context + 中间件）

```go
package main

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

func withTimeout(d time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), d)
		defer cancel()
		c.Request = c.Request.WithContext(ctx) // 下游调用（DB/HTTP）自动感知
		c.Next()
	}
}

func main() {
	r := gin.Default()
	r.Use(withTimeout(2 * time.Second))
	r.GET("/slow", func(c *gin.Context) {
		select {
		case <-time.After(5 * time.Second):
			c.JSON(http.StatusOK, gin.H{"ok": true})
		case <-c.Request.Context().Done():
			c.JSON(http.StatusGatewayTimeout, gin.H{"error": "处理超时"})
		}
	})
	r.Run("127.0.0.1:8080")
}
```

要点：**超时和限流是服务稳定性的基础**（必会概念）——超时分两层：HTTP server 的 Read/Write/IdleTimeout（ph07）+ 每请求 context 超时；**context 必须一路传给数据库、外部 HTTP 调用**，否则慢依赖拖死 goroutine（呼应 ph06 泄漏）；限流用**固定窗口 / 滑动窗口 / 令牌桶**（`golang.org/x/time/rate`）放中间件。**坑：只设 server 超时不设 context**——handler 内部调用不感知超时；客户端断开后业务继续算——select 监听 `c.Request.Context().Done()`（示例 5 有限流完整实现）。

## 4. 底层原理

### 4.1 net/http 的 Handler 与中间件链

- 核心接口：`type Handler interface { ServeHTTP(w ResponseWriter, r *Request) }`；**HandlerFunc 把普通函数适配成 Handler**；ServeMux 本身也是一个 Handler——"路由"就是"按模式把请求分发到子 Handler"
- **中间件本质是 `func(http.Handler) http.Handler` 的包装**：在 ServeHTTP 前后注入逻辑再调用内层——洋葱模型，请求从外到内、响应从内到外；Gin 的 `c.Next()` 是同一思想的栈式实现（gin.Context 内部维护 handler 索引，Next 推进索引）
- 连接模型：**net/http 为每个连接起一个 goroutine**，handler 在 goroutine 中执行——这正是 ph06"goroutine 廉价"的落地，高并发靠 goroutine 而非线程池

### 4.2 Gin 的路由树（radix tree）与 context 复用

- Gin 用 **radix tree（基数树 / 压缩前缀树）** 组织路由：公共前缀合并成同一节点（如 `/devices/` 共享路径段），`:param` 与 `*wildcard` 作为通配节点——**匹配复杂度 O(路径长度)、与路由总数无关**，这是 Gin 快的根基（标准库 ServeMux 在 Go 1.22 前是线性遍历）
- 标准库 Go 1.22 的 ServeMux 也改成了类似 trie 的树结构，支持**方法限定 + 通配符 + 优先级规则**（精确匹配 > 通配 > 最长前缀）
- **gin.Context 用 sync.Pool 池化复用**：请求结束归还池中、下次请求复用，避免每个请求分配 Context；**坑：不能把 c 存进 goroutine / 全局**——请求结束后 c 会被复用，异步任务只提取所需值

### 4.3 请求生命周期（连接·超时·上下文取消）

- 完整链路：**accept 连接 → 读请求头/体 → 路由 → 中间件链（依次 Next）→ handler → 写响应 → 连接回池（keep-alive）**
- **每个请求都有一棵 context 树**：根是 `r.Context()`，超时 / 取消派生子 context；客户端断开、server 超时、主动 cancel 都会触发 `ctx.Done()`——所有阻塞 I/O 都要监听它（ph10 大量使用）
- 泄漏场景：handler 里 `go func()` 起的 goroutine 若不接收 ctx，客户端断开后仍继续跑——**超时与 context 传播是防 goroutine 泄漏的钥匙**（呼应 ph06）

### 4.4 JWT 的结构（header/payload/signature）与无状态认证

- 结构：`header.payload.signature` 三段 base64url——header 声明算法（`{"alg":"HS256"}`）、payload 放 claims（`sub` / `exp` / `iat` / 自定义字段）、**signature = HMAC-SHA256(header.payload, secret)**
- 验签流程：服务端用同一 secret 重算签名比对——**能验签 = 未被篡改 = 可信**；`exp` 过期即失效；全程不查数据库、不存会话，这就是"**无状态**"：任意实例都能独立验证，天然适合水平扩展（ph11 微服务友好）
- **代价**：无法主动吊销（token 被盗只能等过期，除非维护黑名单）；payload 不加密（base64 可读，不能放敏感信息）；密钥管理决定安全性（对称密钥泄露 = 可伪造一切 token）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 前后端分离的 REST API | 路由、JSON 请求响应、CORS、统一错误 |
| 车机 / 移动端数据上报接口 | 参数校验、限流、日志、错误码 |
| 后台管理系统接口 | 登录、JWT/Cookie 认证、中间件鉴权 |
| 图片 / 日志 / 固件上传 | multipart、静态文件服务 |
| 面向第三方的开放 API | API 文档（OpenAPI）、错误码、限流 |
| 服务健康检查与探活 | 路由、JSON、日志 |
| 内部服务的简单 HTTP 接口 | 超时、context、恢复中间件 |
| 网关 / 负载均衡之后的业务层 | 中间件组合、恢复、限流 |

**不适合**此阶段的事项：

- **数据库接入与 ORM**（MySQL/Redis、事务、连接池、迁移）：属 ph10——本阶段数据一律内存 map
- **gRPC 与微服务**（服务注册发现、配置中心、负载均衡、契约测试）：属 ph11——本阶段只做单体 HTTP
- **云原生部署**（容器化、Kubernetes、Helm、可观测性平台）：属 ph12
- **消息队列与异步解耦**（Kafka / RabbitMQ / MQTT）：属 ph19
- **前端工程化与全栈**（React/Vue 构建、SSR）：不属于本 roadmap 的 Go 主线

## 6. 代码示例

### 示例 1：Todo API（Gin 路由 + JSON + 内存存储）

```go
// 运行: go mod init todo-api && go get github.com/gin-gonic/gin && go run .
package main

import (
	"net/http"
	"strconv"
	"sync"

	"github.com/gin-gonic/gin"
)

type Todo struct {
	ID   int    `json:"id"`
	Text string `json:"text"`
	Done bool   `json:"done"`
}

var (
	mu    sync.Mutex // 内存存储的并发保护（ph06 必会概念落地）
	next  = 1
	todos = []Todo{}
)

func main() {
	r := gin.Default()
	r.GET("/todos", listTodos)
	r.POST("/todos", createTodo)
	r.PATCH("/todos/:id/done", markDone)
	r.Run("127.0.0.1:8080")
}

func listTodos(c *gin.Context) {
	mu.Lock()
	defer mu.Unlock()
	c.JSON(http.StatusOK, todos)
}

func createTodo(c *gin.Context) {
	var req struct {
		Text string `json:"text" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "text 不能为空"})
		return
	}
	mu.Lock()
	t := Todo{ID: next, Text: req.Text}
	next++
	todos = append(todos, t)
	mu.Unlock()
	c.JSON(http.StatusCreated, t)
}

func markDone(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "id 必须是整数"})
		return
	}
	mu.Lock()
	defer mu.Unlock()
	for i := range todos {
		if todos[i].ID == id {
			todos[i].Done = true
			c.JSON(http.StatusOK, todos[i])
			return
		}
	}
	c.JSON(http.StatusNotFound, gin.H{"error": "todo not found"})
}
```

要点：roadmap 练习 **Todo API** 的完整答案——GET/POST/PATCH 三种方法 + 201/400/404 三种状态码；**内存切片存储必须加 Mutex**（ph06 并发安全落地）；handler 保持"解析 → 校验 → 业务 → 响应"四段清晰（必会概念）。扩展：`curl http://127.0.0.1:8080/todos` 验证列表，补 PUT 编辑与 DELETE，并把 ph08 的 httptest 测试套到三个 handler 上。

### 示例 2：登录注册（JWT 签发与中间件鉴权）

```go
// 运行: go mod init auth-api && go get github.com/gin-gonic/gin github.com/golang-jwt/jwt/v5 && go run .
package main

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

type cred struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

var (
	secret = []byte("please-change-me")           // 生产放环境变量，定期轮换
	users  = map[string]string{"admin": "123456"} // username → password（真实项目存哈希 + 数据库，ph10）
)

func main() {
	r := gin.Default()
	r.POST("/register", register)
	r.POST("/login", login)
	r.Group("/api", auth()).GET("/profile", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"username": c.GetString("username")})
	})
	r.Run("127.0.0.1:8080")
}

func register(c *gin.Context) {
	var u cred
	if err := c.ShouldBindJSON(&u); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "用户名和密码必填"})
		return
	}
	if _, ok := users[u.Username]; ok {
		c.JSON(http.StatusConflict, gin.H{"error": "用户名已存在"})
		return
	}
	users[u.Username] = u.Password
	c.JSON(http.StatusCreated, gin.H{"message": "注册成功"})
}

func login(c *gin.Context) {
	var u cred
	if err := c.ShouldBindJSON(&u); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "用户名和密码必填"})
		return
	}
	if users[u.Username] != u.Password {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "用户名或密码错误"})
		return
	}
	token, _ := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"username": u.Username,
		"exp":      time.Now().Add(2 * time.Hour).Unix(),
	}).SignedString(secret)
	c.JSON(http.StatusOK, gin.H{"token": token})
}

// auth 校验 Authorization: Bearer <token>，通过后把用户写进 context
func auth() gin.HandlerFunc {
	return func(c *gin.Context) {
		tokenStr, ok := strings.CutPrefix(c.GetHeader("Authorization"), "Bearer ")
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "缺少 token"})
			return
		}
		claims := jwt.MapClaims{}
		token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (any, error) {
			if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok { // 算法白名单，防 alg 混淆攻击
				return nil, fmt.Errorf("unexpected signing method")
			}
			return secret, nil
		})
		if err != nil || !token.Valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "token 无效或已过期"})
			return
		}
		c.Set("username", claims["username"])
		c.Next()
	}
}
```

要点：roadmap 练习 **登录注册** 的完整答案——注册查重（409）、登录校验（401）、**签发 JWT + 中间件鉴权**（Bearer 解析 → 验签 → c.Set 传递用户 → c.Next）。验证：先 register 再 login 拿 token，`curl .../api/profile -H "Authorization: Bearer <token>"`；**坑：验签必须做算法白名单**（防 alg=none 混淆）；**坑：密码不能明文存**——本示例为演示简化，ph10 用 bcrypt 哈希 + 数据库。

### 示例 3：文件上传服务（multipart + 保存 + 响应）

```go
// 运行: go mod init upload && go get github.com/gin-gonic/gin && go run .
package main

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/gin-gonic/gin"
)

const uploadDir = "./uploads"

func main() {
	os.MkdirAll(uploadDir, 0o755)
	r := gin.Default()
	r.MaxMultipartMemory = 8 << 20 // 8MB 以内进内存，超过落临时文件
	r.POST("/upload", upload)
	r.Static("/files", uploadDir) // 上传的文件可直接通过 URL 访问
	r.Run("127.0.0.1:8080")
}

func upload(c *gin.Context) {
	f, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "缺少 file 字段"})
		return
	}
	name := fmt.Sprintf("%d-%s", time.Now().UnixNano(), filepath.Base(f.Filename)) // 时间戳防重名 + Base 防穿越
	dst := filepath.Join(uploadDir, name)
	if err := c.SaveUploadedFile(f, dst); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "保存失败"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"filename": name, "size": f.Size, "url": "/files/" + name})
}
```

要点：roadmap 练习 **文件上传服务** 的完整答案——FormFile 接收、SaveUploadedFile 落盘、响应返回可访问 URL。验证：`curl -F "file=@photo.jpg" http://127.0.0.1:8080/upload`，浏览器打开返回的 url；**坑：重名覆盖与路径穿越**（时间戳 + filepath.Base 双保险）；**坑：大文件必须设 MaxMultipartMemory 并做大小 / 类型白名单**（扩展名 + MIME），否则恶意大文件打满内存或磁盘。

### 示例 4：设备状态查询 API（参数校验 + 统一错误结构）

```go
// 运行: go mod init devices && go get github.com/gin-gonic/gin && go run .
package main

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// Device 设备状态——roadmap 推荐项目"车辆数据上报 API"的最小形态
type Device struct {
	ID        string    `json:"id"`
	Status    string    `json:"status"`
	Speed     float64   `json:"speed"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ErrorBody 统一错误结构（3.4 的落地）
type ErrorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func fail(c *gin.Context, status int, code, msg string) {
	c.JSON(status, ErrorBody{Code: code, Message: msg})
}

var devices = map[string]Device{
	"car-001": {ID: "car-001", Status: "online", Speed: 60.5, UpdatedAt: time.Now()},
	"car-002": {ID: "car-002", Status: "offline", Speed: 0, UpdatedAt: time.Now()},
}

type listQuery struct {
	Status string `form:"status" binding:"omitempty,oneof=online offline"` // 枚举校验
}

func main() {
	r := gin.Default()
	r.GET("/api/devices", listDevices)
	r.GET("/api/devices/:id", getDevice)
	r.Run("127.0.0.1:8080")
}

func listDevices(c *gin.Context) {
	var q listQuery
	if err := c.ShouldBindQuery(&q); err != nil {
		fail(c, http.StatusBadRequest, "INVALID_PARAM", "status 只能是 online 或 offline")
		return
	}
	list := make([]Device, 0, len(devices))
	for _, d := range devices {
		if q.Status == "" || d.Status == q.Status {
			list = append(list, d)
		}
	}
	c.JSON(http.StatusOK, list)
}

func getDevice(c *gin.Context) {
	id := c.Param("id")
	d, ok := devices[id]
	if !ok {
		fail(c, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
		return
	}
	c.JSON(http.StatusOK, d)
}
```

要点：roadmap 练习 **设备状态查询 API** 的完整答案，同时覆盖阶段验收两条：**参数校验**（query 枚举用 binding oneof）+ **统一错误**（全部走 fail 返回 `{code, message}`）。验证：`curl "http://127.0.0.1:8080/api/devices?status=online"`、`curl http://127.0.0.1:8080/api/devices/nope`（404 NOT_FOUND）；**扩展：加"上报"接口 POST /api/devices/:id/report 把 Speed/Status 写回 map**——即推荐项目"车辆数据上报 API"的最小闭环；补 httptest 测试覆盖 200 / 400 / 404。

### 示例 5：中间件组合（日志 + 恢复 + CORS + 限流）

```go
// 运行: go mod init mid && go get github.com/gin-gonic/gin && go run .
package main

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

var (
	rlMu  sync.Mutex
	hits  = map[string][]time.Time{} // 每 IP 最近请求时间
	limit = 30                       // 每窗口最多 30 次
)

// rateLimit 固定窗口限流中间件（每 IP 每分钟 30 次）
func rateLimit() gin.HandlerFunc {
	return func(c *gin.Context) {
		key := c.ClientIP()
		now := time.Now()
		cutoff := now.Add(-time.Minute)
		rlMu.Lock()
		recent := make([]time.Time, 0, len(hits[key]))
		for _, t := range hits[key] {
			if t.After(cutoff) {
				recent = append(recent, t)
			}
		}
		hits[key] = recent
		if len(recent) >= limit {
			rlMu.Unlock()
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{"error": "请求过于频繁"})
			return
		}
		hits[key] = append(hits[key], now)
		rlMu.Unlock()
		c.Next()
	}
}

func cors() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*") // 生产按域名白名单
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == http.MethodOptions { // 预检请求直接放行
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

func main() {
	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery()) // ① 请求日志 ② panic 恢复（生产必挂）
	r.Use(cors())                       // ③ 跨域
	r.Use(rateLimit())                  // ④ 限流
	r.GET("/ping", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "pong"})
	})
	r.Run("127.0.0.1:8080")
}
```

要点：四个横切关注点组合成一个完整服务——**日志、恢复、CORS、限流全部与业务无关**（必会概念"中间件适合横切逻辑"的完整落地）；**执行顺序 = 挂载顺序**（洋葱模型外层先执行）。压测验证 429：`ab -n 100 -c 10 http://127.0.0.1:8080/ping`；**坑：CORS 的 `Allow-Origin: *` 不能与 `Allow-Credentials: true` 并用**——带 Cookie 的跨域要按域名白名单回显 Origin；**坑：单机 map 限流只够学习**——分布式限流（Redis 令牌桶）见 ph10。

## 7. 总结

### 关键要点

1. **handler 要清晰分离解析、校验、业务和响应**（必会概念）：四段式结构，业务抽 service，handler 只做编排
2. **中间件适合横切逻辑**（必会概念）：日志、恢复、CORS、限流、鉴权都放中间件，业务规则绝不进中间件
3. **API 错误结构要统一**（必会概念）：固定 `{code, message}`，code 给程序、message 给人，所有错误一个入口
4. **超时和限流是服务稳定性的基础**（必会概念）：server 超时 + context 超时双层防护，限流防单点被打爆
5. **REST 是"方法 + 资源 + 状态码"的三元组**：GET/POST/PUT/PATCH/DELETE 语义分明，状态码表达响应语义，别用 200 表达一切
6. **JSON 请求响应靠 tag 对齐协议**：字段名、required、omitempty 是接口契约的一部分（ph07 延续）
7. **JWT 无状态、Cookie 有状态**：token 验签即可信、不存会话；payload 不加密、密钥要保密、Cookie 要 HttpOnly
8. **Gin 用 radix tree 路由 + sync.Pool 复用 Context**：匹配与分配都高效，但别在 goroutine 里保存 c
9. **参数校验用 binding tag 声明式完成**：required/oneof/min/max 一行搞定，validator 错误信息需包装成统一结构
10. **API 文档与代码同源**：Swagger 注解驱动生成 OpenAPI，改接口必须同步改注解，防"文档撒谎"

### 跨语言对比：Web 框架与 API 设计

| 维度 | Go Gin | Java Spring Boot | Python FastAPI | Node Express | Rust Axum |
|------|--------|-----------------|---------------|-------------|-----------|
| 典型框架 | Gin（radix tree） | Spring MVC（Servlet） | FastAPI（ASGI） | Express（中间件栈） | Axum（tower） |
| 路由风格 | 方法 + `:param` | 注解 @GetMapping | 装饰器 + 路径参数 | app.get('/:id') | 宏 + 路径提取器 |
| 参数校验 | binding tag + validator | jakarta validation 注解 | Pydantic 类型注解 | 手写 / zod | 提取器 + validator |
| 中间件/横切 | gin.HandlerFunc 链 | Filter / Interceptor | 依赖注入中间件 | app.use 链 | tower Layer |
| 异步模型 | goroutine（同步写法） | 线程池 / 虚拟线程 | asyncio 协程 | 事件循环 | tokio 异步 |
| API 文档 | swag 注释生成 OpenAPI | springdoc | 自动 OpenAPI | swagger-jsdoc | utoipa 宏 |

### 阶段验收标准

- **能设计 REST 接口**：资源路径、方法语义、状态码选择合理，能讲清"为什么这样设计"
- **能处理参数校验和统一错误**：binding tag 覆盖必填 / 枚举 / 范围，所有错误走统一 `{code, message}` 结构
- **能写出基础认证流程**：注册 / 登录签发 JWT，中间件校验 Bearer token，未授权访问被拒绝（401）
- **能组合中间件**：日志、恢复、CORS、限流四件套组合成服务，能说清执行顺序与 Abort/Next 语义
- **能解释服务稳定性手段**：说出超时两层（server + context）与限流的作用，能复现 429 与超时场景
- **接口可测试**：ph08 的 httptest 直接套用（gin.Engine 实现 http.Handler，`r.ServeHTTP(rec, req)` 即可）

### 进入下一阶段前

确保能完成以下练习（均来自 roadmap，对应示例编号）：

- **Todo API**：GET/POST/PATCH 三接口 + 内存存储 + Mutex（提示：示例 1；扩展 PUT 编辑与 DELETE 删除）
- **登录注册**：注册查重、登录签发 JWT、中间件保护 /api 分组（提示：示例 2；密码哈希与用户落库是 ph10 的事）
- **文件上传服务**：multipart 接收 + 防穿越命名 + 返回 URL + 大小与类型白名单（提示：示例 3）
- **设备状态查询 API**：列表过滤 + 详情 + 统一错误 + query 枚举校验（提示：示例 4；扩展 POST 上报接口即"车辆数据上报 API"雏形）
- **中间件组合**：日志 + 恢复 + CORS + 限流挂成一个服务（提示：示例 5；用 curl/ab 验证 429）
- **给接口补测试**：用 httptest + `r.ServeHTTP(rec, req)` 覆盖 200/400/401/404（提示：ph08 方法直接复用）

### 推荐项目

- **车辆数据上报 API**：车机端定时上报位置 / 速度 / 状态，接口含鉴权（设备 token）、参数校验（速度范围、坐标合法）、限流（每设备每分钟 N 次）、统一错误码；数据暂存内存 map、ph10 换数据库——把示例 2（JWT）+ 示例 4（校验与错误）+ 示例 5（限流）拼成一个完整服务，正是 roadmap 推荐项目的形态
- **后台管理服务**：管理员登录（JWT + 中间件鉴权）、用户 / 设备管理 CRUD 接口（统一响应与错误）、操作日志（log/slog）、分页与过滤参数校验（binding）、Swagger 文档——覆盖本阶段全部知识点，且直接复用 ph08 的 httptest 测试保障质量

### 下一阶段

**数据库阶段**（`ph10-database`，文档规划中）——SQL 与 database/sql / sqlx / gorm、事务与连接池、MySQL/PostgreSQL、Redis 缓存与 go-redis、索引与慢查询、迁移；本阶段"内存 map 存数据"的全部接口将换成真实数据库，JWT 用户存储与设备状态写入也会落库。
