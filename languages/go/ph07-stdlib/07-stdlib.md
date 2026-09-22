# Go 标准库阶段

> 面向后端服务、云原生和通用数据平台方向，本阶段熟悉 Go 标准库——优先用标准库完成常见任务，为后续框架与生态阶段打下地基。

## 1. 概述

Go 标准库阶段的目标是：**熟悉 fmt、os、io、bufio、strings、strconv、time、context、sync、net、net/http、encoding/json、errors、log、flag、testing 等标准库包，能够优先用标准库完成常见任务**。ph06 解决了"代码怎么并发跑"，本阶段回答"常见任务用什么现成工具做"——文件读写、JSON 序列化、HTTP 服务、命令行参数、单元测试，全部由标准库直接覆盖。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 格式化与字符串 | fmt、strings、strconv |
| 文件与流 | os、io、bufio、path/filepath |
| 时间与定时 | time（时间、时区、定时器） |
| 错误·日志·命令行 | errors、log、flag |
| JSON 序列化 | encoding/json（结构体 tag） |
| 网络与 HTTP | net、net/http（服务端与客户端） |
| 并发补充 | context、sync（Once/Map） |
| 单元测试 | testing（go test） |

本阶段的核心理念是"**标准库优先**"：标准库覆盖了后端基础能力的绝大部分，第三方库只在不够用时才引入；其 API 风格（显式 error 返回、io.Reader/io.Writer 抽象、结构体 tag 配置）会在后续框架阶段反复出现。

范围边界：承接 ph06 的并发能力（context/sync 进入文件处理与 HTTP 服务实战）；不涉及测试深入（benchmark、mock、覆盖率属 ph08）、Web 框架（gin/echo 属 ph09）、数据库驱动（database/sql 属 ph10）、微服务与消息中间件（ph11/ph19）。

## 2. 来源与演变

Go 标准库的设计哲学是"**batteries included，但不臃肿**"：语言内置并发（sync/atomic）、网络（net/http 是可直接上生产的 HTTP 服务器）、测试（testing）三大件，不装任何第三方依赖就能搭建完整后端服务。与 Java 的"标准库庞大 + 框架生态"、Python 的"自带电池"、C++ 的"库分散于生态"相比，Go 选择**把关键能力放进标准库，而不是交给社区约定**。

**Go 1 兼容性承诺（Go 1 Compatibility Promise）**：自 2012 年 Go 1.0 起，官方承诺标准库已发布 API 只增不删、不改语义——"今天的代码十年后仍能编译"，学习它不会过时。标准库还通过 **golang.org/x 孵化机制**演进：新能力先在 x 仓库实验，成熟后移入标准库（context、slices 都是这条路）。

| 时间 | 事件 |
|------|------|
| 2009 | Go 发布即自带 fmt、net/http、testing、encoding/json 等核心包 |
| 2012 | Go 1.0：确立"Go 1 兼容性承诺"，标准库 API 永不破坏 |
| 2013 | Go 1.1：bufio.Scanner 加入，逐行读取成为标准做法 |
| 2016 | Go 1.7：context 从 golang.org/x/net 移入标准库 |
| 2019 | Go 1.13：errors.Is/errors.As 与 `%w` 错误包装进入标准库 |
| 2021 | Go 1.16：os.ReadFile/os.WriteFile、io/fs 加入，文件读写一步到位 |
| 2022 | Go 1.18：标准库启用泛型（slices、maps 包） |
| 2023 | Go 1.21：log/slog 结构化日志进入标准库 |
| 2024 | Go 1.22：net/http 路由增强（方法匹配、通配符模式） |

**设计哲学**：标准库是"默认优先"的答案——遇到需求先问"标准库能不能做"，再考虑第三方依赖。

本文示例以 **Go 1.21+** 为基线（`net/http`、`encoding/json`、`flag`、`log` 稳定，context 超时可用），验证工具链 Go 1.22.2 darwin/arm64。

## 3. 语法与参数

### 3.1 fmt 格式化与字符串处理（strings/strconv）

```go
package main

import (
	"fmt"
	"strconv"
	"strings"
)

func main() {
	name := "vehicle_001"
	fmt.Printf("名称: %s, 长度: %d\n", name, len(name))
	fmt.Println("大写:", strings.ToUpper(name), "含前缀:", strings.HasPrefix(name, "vehicle"))
	parts := strings.Split("a,b,c", ",")
	fmt.Println("拆分:", parts, "→ 拼接:", strings.Join(parts, "-"))
	n, err := strconv.Atoi("8080") // 字符串 → 整数
	if err != nil {
		fmt.Println("转换失败:", err)
		return
	}
	fmt.Println("端口:", n, "| 整数转字符串:", strconv.Itoa(n))
	f, _ := strconv.ParseFloat("3.14", 64)
	fmt.Printf("浮点: %.2f\n", f)
}
```

要点：fmt 常用动词 `%s`/`%d`/`%t`/`%.2f`/`%v`——**`%v` 打印任意类型默认格式、`%+v` 打印结构体字段名**；strings 包全是纯函数、字符串不可变；strconv 返回 `(值, error)`，呼应 ph02 的显式错误处理。

### 3.2 os·io·bufio 文件与流

```go
package main

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	// 小文件：os.WriteFile / os.ReadFile 一步完成
	if err := os.WriteFile("/tmp/ph07_demo.txt", []byte("第一行\n第二行\n"), 0644); err != nil {
		fmt.Println("写入失败:", err)
		return
	}
	data, err := os.ReadFile("/tmp/ph07_demo.txt")
	if err != nil {
		fmt.Println("读取失败:", err)
		return
	}
	fmt.Print(string(data))
	// 大文件：bufio.Scanner 逐行扫描，内存占用与文件大小无关
	f, err := os.Open("/tmp/ph07_demo.txt")
	if err != nil {
		fmt.Println("打开失败:", err)
		return
	}
	defer f.Close() // 打开后立即 defer 关闭（ph02 习惯）
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		fmt.Println("行:", scanner.Text())
	} // 结束后用 scanner.Err() 检查扫描错误，完整版见示例 1
}
```

要点：**小文件用 ReadFile 一步读完，大文件用 bufio.Scanner 流式逐行**（GB 级日志也不怕）；**坑：Scanner 默认单行上限 64KB**，超长行需 `scanner.Buffer(buf, max)` 调大；**坑：bufio.Writer 是缓冲写入，必须 `Flush()` 才真正落盘**，只 Close 会丢数据。

### 3.3 io.Reader / io.Writer 核心抽象

```go
package main

import (
	"io"
	"os"
	"strings"
)

func main() {
	r := strings.NewReader("hello, stdlib\n") // 字符串 → io.Reader
	io.Copy(os.Stdout, r)                    // Reader → Writer 流式搬运
	// Read 循环与 EOF 约定见 4.1
}
```

要点：**io.Reader 是"会读取的东西"、io.Writer 是"会写入的东西"**——文件、网络连接、内存缓冲、标准输出都实现这两个接口，所以 io.Copy 能搬运一切来源；约定细节见 4.1。

### 3.4 time 时间与定时

```go
package main

import (
	"fmt"
	"time"
)

func main() {
	now := time.Now()
	fmt.Println("当前:", now.Format("2006-01-02 15:04:05")) // 参考时间模板
	t, _ := time.Parse("2006-01-02", "2024-06-01")
	fmt.Println("解析:", t.Format("2006/01/02"))
	<-time.After(50 * time.Millisecond) // 一次性定时
	fmt.Println("50ms 已过")
	fmt.Println("耗时:", time.Since(now).Round(time.Millisecond))
}
```

要点：**坑：2006-01-02 15:04:05 是 Go 的参考时间模板**（2006 年 1 月 2 日 15 点 04 分 05 秒），不是随便写的格式串，用错则解析全错；time.Time 是值类型，内部存时间戳；time.After/NewTimer/Tick 配合 select 做超时——ph06 已用，本阶段在 HTTP 客户端与日志场景复用。

### 3.5 errors·log·flag

```go
package main

import (
	"errors"
	"flag"
	"fmt"
	"log"
)

func main() {
	host := flag.String("host", "127.0.0.1", "监听地址") // flag：命令行参数
	port := flag.Int("port", 8080, "监听端口")
	flag.Parse()
	fmt.Printf("配置: %s:%d\n", *host, *port)
	base := errors.New("disk full") // errors：构造 + 包装 + 判定
	wrapped := fmt.Errorf("write failed: %w", base)
	fmt.Println("Is 判定:", errors.Is(wrapped, base)) // true
	log.Println("服务启动") // log：默认带时间戳，输出到 stderr
}
```

要点：flag 包的命令行约定——**`-host` 与 `--host` 等价，短选项 `-h` 保留给帮助**，`flag.Parse()` 后用指针取值；errors/log/flag 三个"小包"在 CLI 工具里配套出现：flag 收参数、errors 判错误、log 记运行日志。

### 3.6 encoding/json 序列化（tag）

```go
package main

import (
	"encoding/json"
	"fmt"
)

// JSON tag：决定字段在 JSON 中的名字，是接口协议的一部分
type Vehicle struct {
	ID     string  `json:"id"`
	Speed  float64 `json:"speed"`
	Status string  `json:"status,omitempty"` // 空值不输出
	secret string  // 未导出字段：不参与序列化
}

func main() {
	v := Vehicle{ID: "car-001", Speed: 88.5, secret: "看不见"}
	data, _ := json.Marshal(v) // struct → JSON 字节
	fmt.Println(string(data))  // {"id":"car-001","speed":88.5}
	var decoded Vehicle
	json.Unmarshal(data, &decoded) // JSON 字节 → struct（完整错误处理见示例 2）
	fmt.Printf("解码: %+v\n", decoded)
}
```

要点：**坑：JSON 只能序列化导出字段**（首字母大写），未导出字段被静默忽略——这是最常见的"JSON 缺字段"问题；tag 语法 `json:"名字,选项"`，常用选项 **omitempty（空值不输出）** 与 **"-"（忽略）**；tag 名与字段名不一致时以 tag 为准；反序列化未知字段默认忽略，可用 `json.Decoder.DisallowUnknownFields()` 严格校验。

### 3.7 net·net/http HTTP 服务

```go
package main

import (
	"fmt"
	"net/http"
)

func main() {
	http.HandleFunc("/hello", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "hello, stdlib")
	})
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "path=%s method=%s\n", r.URL.Path, r.Method)
	})
	fmt.Println("服务启动: http://127.0.0.1:8080")
	if err := http.ListenAndServe("127.0.0.1:8080", nil); err != nil {
		fmt.Println("服务退出:", err)
	}
}
```

要点：注册路由用 `http.HandleFunc`（模式 + 函数），处理函数签名固定 `func(w http.ResponseWriter, r *http.Request)`；**net/http 内置生产级服务器**（HTTP/2、连接池、超时控制全支持），是"能直接构建生产级基础服务"的底气；**坑：服务器必须显式设置 ReadTimeout/WriteTimeout**，否则慢客户端可长期占用连接——见示例 3；客户端用 `http.Get`/`http.NewRequest` 发请求。

### 3.8 sync 与 context 补充

```go
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

func main() {
	var once sync.Once // sync.Once：全局只执行一次的初始化
	for i := 0; i < 3; i++ {
		once.Do(func() { fmt.Println("只打印一次") })
	}
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond) // context 超时
	defer cancel()
	select {
	case <-time.After(100 * time.Millisecond):
		fmt.Println("任务完成")
	case <-ctx.Done():
		fmt.Println("超时:", ctx.Err())
	}
}
```

要点：ph06 已学 context/sync 的机制，本阶段掌握**标准库实战用法**：sync.Once 做懒初始化、sync.Mutex/RWMutex 保护共享状态、sync.Map 用于并发读多写少的 map（如示例 3 的设备表）、context 贯穿所有 I/O 调用（http 请求、文件操作都可挂 ctx 超时取消）。

### 3.9 testing 单元测试入门

```go
// main.go —— 被测代码
package main

import "fmt"

func add(a, b int) int { return a + b }

func main() { fmt.Println("add(2,3) =", add(2, 3)) }
```

```go
// main_test.go —— 测试文件，文件名必须以 _test.go 结尾
package main

import "testing"

func TestAdd(t *testing.T) {
	got := add(1, 2)
	if got != 3 {
		t.Fatalf("add(1,2) = %d, 期望 3", got)
	}
}
```

要点：运行 `go test`（当前包）或 `go test ./...`（全部包）；测试函数命名 `TestXxx`、签名固定 `func TestXxx(t *testing.T)`；**t.Errorf 标记失败继续跑，t.Fatalf 立即终止当前测试**；测试文件与业务代码同包，可直接访问未导出函数；表格驱动、子测试、benchmark 的深入见 ph08。

## 4. 底层原理

### 4.1 io.Reader / io.Writer 约定

- **短读合法**：`Read(p []byte) (n int, err error)` 一次只承诺返回 1..len(p) 字节，不承诺填满缓冲区——调用方必须循环读，直到 `err == io.EOF`
- **EOF 是正常状态不是错误**：`n > 0` 且 `err == io.EOF` 时先处理数据再退出；一开始就 EOF 时 `n == 0`
- **其他错误**（网络断开等）：`n` 可能大于 0（部分数据），先处理 `n` 字节再检查 `err`；Writer 的 `Write` 返回 `n < len(p)` 时必须伴随非 nil err
- **流式处理的本质**：io.Copy、bufio.Scanner 都是"边读边处理"，内存占用与数据总量无关——GB 级日志也能处理（呼应示例 1 与推荐项目"日志分析小工具"）

### 4.2 net/http 的 ServeMux 与 Handler 模型

- 核心接口：`type Handler interface { ServeHTTP(w ResponseWriter, r *Request) }`——一切 HTTP 处理都是实现这个接口
- **ServeMux 是路由表**：把 URL 模式映射到 Handler；`http.HandleFunc` 只是 `mux.Handle(pattern, HandlerFunc(f))` 的语法糖；**HandlerFunc 是"把函数变成 Handler"的适配器类型**
- 匹配规则：精确匹配优先于前缀匹配，`"/"` 是兜底路由（Go 1.22 前）；Go 1.22+ 支持方法限定与通配符（如 `GET /devices/{id}`）
- 生产级要点：服务器超时、请求体大小限制、panic 恢复——示例 3 用 `http.Server` 显式设置三档超时

### 4.3 encoding/json 的反射机制

- Marshal/Unmarshal 基于 **reflect（反射）**：运行时读取结构体字段的 tag、导出状态与类型
- **Marshal 流程**：遍历结构体导出字段 → 读 json tag 决定输出名 → 按类型选编码器（string/int/bool/嵌套 struct/slice）
- **Unmarshal 流程**：解析 JSON token 流 → 按 tag 名匹配字段（大小写不敏感）→ 类型转换后写入指针；未知字段默认忽略
- **代价与取舍**：反射慢于手写序列化，压测发现热点可换 jsoniter 等第三方库（ph13 再做）；日常正确性优先，坚持标准库

### 4.4 testing 的并行与子测试机制

- `go test` 默认**并行运行多个测试包**（`-p`），包内测试默认串行
- **t.Parallel()**：标记可并行的测试，配合 `-parallel` 并发跑同包测试——共享全局状态时要加锁或隔离
- **t.Run 子测试**：一个测试内拆多个子用例，可单独运行/筛选（`go test -run TestXxx/用例名`），子测试也可单独 t.Parallel()
- 表格驱动测试把"数据"与"断言逻辑"分离，是 Go 测试的惯用风格（示例 5）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 读取/写入配置文件 | os.ReadFile/os.WriteFile、encoding/json |
| 大日志逐行处理（GB 级） | bufio.Scanner、strings、strconv |
| 数据上报 HTTP 接口 | net/http、encoding/json |
| 服务健康检查 / 探活 | net/http 客户端、time 超时 |
| 定时任务 / 轮询 | time.Timer / time.Tick |
| 命令行工具 | flag、os.Args |
| 服务启动日志与错误记录 | log（结构化日志见 ph08） |
| 核心函数回归保障 | testing、go test |

**不适合**此阶段的事项：

- **Web 框架与中间件生态**（gin/echo/fiber/chi、JWT、CORS 库）：属 ph09，本阶段只用 net/http 手写路由
- **数据库驱动与 ORM**（database/sql、gorm）：属 ph10
- **微服务与 RPC**（gRPC、服务发现、配置中心）：属 ph11
- **通用第三方库的大规模引入**（viper、cobra、zap）：本阶段先吃透标准库，后续按需替换

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录。每个示例一个子目录，进入对应目录后 `go run .` 即可运行；示例 5 用 `go test -v` 运行。全部示例验证环境：Go 1.22.2（darwin/arm64），仅标准库。

### 示例 1：文件统计工具（bufio 逐行统计单词/行数）

```go
package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"strings"
)

func main() {
	if len(os.Args) < 2 {
		log.Fatal("用法: go run wc.go <文件路径>")
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()
	lines, words := 0, 0
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		lines++
		words += len(strings.Fields(scanner.Text())) // 按空白切分统计单词
	}
	fmt.Printf("行数: %d\n单词数: %d\n", lines, words)
}
```

要点：运行 `cd examples/ex01-file-stats && go run . <文件路径>`；bufio.Scanner 逐行 + strings.Fields 统计单词，全程不把整个文件载入内存——roadmap 练习"文件统计工具"的标准答案。

完整文件：`examples/ex01-file-stats/`（go.mod + main.go）

### 示例 2：JSON 配置解析器（结构体 tag + os.ReadFile + json.Unmarshal）

```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
)

// Config 配置结构：JSON tag 与配置文件字段一一对应
type Config struct {
	Server struct {
		Host string `json:"host"`
		Port int    `json:"port"`
	} `json:"server"`
	LogLevel string `json:"log_level"`
	Timeout  int    `json:"timeout"`
}

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读取配置 %s: %w", path, err)
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("解析配置 %s: %w", path, err)
	}
	if cfg.Server.Port <= 0 {
		return nil, fmt.Errorf("配置错误: server.port 必须为正数")
	}
	return &cfg, nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatal("用法: go run config.go <配置文件路径>")
	}
	cfg, err := loadConfig(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("服务地址: %s:%d, 日志级别: %s, 超时: %d 秒\n", cfg.Server.Host, cfg.Server.Port, cfg.LogLevel, cfg.Timeout)
}
```

要点：先准备 JSON 文件再运行 `cd examples/ex02-json-config && go run . demo.json`；嵌套结构体对应嵌套 JSON；错误逐层 `%w` 包装（ph02 习惯）；解析后做**业务校验**（端口必须为正）——"解析成功"不等于"配置合法"。

完整文件：`examples/ex02-json-config/`（go.mod + main.go + demo.json）

### 示例 3：HTTP API server（net/http + json 响应 + 路由）

```go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

type Device struct {
	ID     string  `json:"id"`
	Status string  `json:"status"`
	Speed  float64 `json:"speed"`
}

func main() {
	devices := map[string]Device{ // 内存数据（真实项目用数据库，见 ph10）
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
	}
	http.HandleFunc("/devices", func(w http.ResponseWriter, r *http.Request) { // 全部设备
		list := make([]Device, 0, len(devices))
		for _, d := range devices {
			list = append(list, d)
		}
		writeJSON(w, http.StatusOK, list)
	})
	http.HandleFunc("/devices/", func(w http.ResponseWriter, r *http.Request) { // 单个设备
		id := r.URL.Path[len("/devices/"):]
		if d, ok := devices[id]; ok {
			writeJSON(w, http.StatusOK, d)
			return
		}
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found"})
	})
	srv := &http.Server{Addr: "127.0.0.1:8080", ReadTimeout: 5 * time.Second, WriteTimeout: 10 * time.Second}
	log.Println("API 服务启动: http://127.0.0.1:8080")
	log.Fatal(srv.ListenAndServe())
}

// writeJSON 统一 JSON 响应：Content-Type 与状态码
func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
```

要点：`/devices` 精确路由 + `/devices/` 前缀路由取 id（Go 1.22+ 可用 `GET /devices/{id}` 通配符）；json.NewEncoder 流式写 JSON；**扩展练习：给 handler 加方法校验（非 GET 返回 405）与 IdleTimeout**；curl 验证：`curl http://127.0.0.1:8080/devices/car-001`。

完整文件：`examples/ex03-http-api/`（go.mod + main.go）

### 示例 4：命令行 Todo 工具（flag 解析 + 文件持久化）

```go
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
)

type Todo struct {
	Text string `json:"text"`
	Done bool   `json:"done"`
}

const storePath = "/tmp/ph07_todo.json"

func load() []Todo {
	data, _ := os.ReadFile(storePath) // 文件不存在或损坏 → 空列表
	var todos []Todo
	json.Unmarshal(data, &todos)
	return todos
}

func save(todos []Todo) error {
	data, err := json.MarshalIndent(todos, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(storePath, data, 0644)
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "保存失败:", err)
		os.Exit(1)
	}
}

func main() {
	add := flag.String("add", "", "添加一条待办")
	list := flag.Bool("list", false, "列出全部待办")
	flag.Parse()
	todos := load()
	switch {
	case *add != "":
		todos = append(todos, Todo{Text: *add})
		must(save(todos))
		fmt.Println("已添加:", *add)
	case *list:
		for i, t := range todos {
			mark := " "
			if t.Done {
				mark = "x"
			}
			fmt.Printf("%d. [%s] %s\n", i+1, mark, t.Text)
		}
	default:
		fmt.Println("用法:")
		flag.PrintDefaults()
	}
}
```

要点：运行方式 `cd examples/ex04-todo-cli && go run . -add "写周报"`、`-list`；JSON 持久化到文件，重启不丢数据；**MarshalIndent 美化输出方便人读**；扩展练习：加 `-done N` 把第 N 条标记完成（修改 `Todo.Done` 后 `save` 回写）。

完整文件：`examples/ex04-todo-cli/`（go.mod + main.go）

### 示例 5：单元测试（testing + 表驱动测试 + t.Run 子测试）

```go
// main.go —— 被测代码（单词统计）
package main

import "fmt"

// WordCount 统计一段文本的单词数
func WordCount(s string) int {
	count := 0
	inWord := false
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' {
			inWord = false
		} else if !inWord {
			count++
			inWord = true
		}
	}
	return count
}

func main() { fmt.Println("单词数:", WordCount("hello go stdlib")) }
```

```go
// main_test.go —— 表驱动测试：数据与期望并列成表，t.Run 拆成子测试
package main

import "testing"

func TestWordCount(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want int
	}{
		{"空串", "", 0},
		{"单单词", "hello", 1},
		{"多空格", "  hello   go  ", 2},
		{"多行", "a b\nc", 3},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := WordCount(tc.in); got != tc.want {
				t.Errorf("WordCount(%q) = %d, 期望 %d", tc.in, got, tc.want)
			}
		})
	}
}
```

要点：运行 `cd examples/ex05-wordcount-test && go test -v` 可见每个子测试的通过/失败；**t.Run 子测试可单独筛选**：`go test -run 'TestWordCount/多行'`；表驱动是 Go 测试的标准风格——新增用例只加一行表数据；ph08 将深入 benchmark、mock 与覆盖率。

完整文件：`examples/ex05-wordcount-test/`（go.mod + main.go + main_test.go）

## 7. 总结

### 关键要点

1. **标准库优先**：文件、JSON、HTTP、命令行、测试五大类任务都有官方方案——先查标准库，再考虑第三方
2. **io.Reader/io.Writer 是核心抽象**：文件、网络、内存缓冲都实现它们，io.Copy 一次学会处处可用
3. **JSON tag 是接口协议的一部分**：字段名、omitempty、导出规则共同决定线上报文——改 tag 就是改协议
4. **bufio 的 Flush 不能忘**：Scanner 管读、Writer 的缓冲要显式 Flush 才落盘，否则丢数据
5. **HTTP 服务要显式设置超时**：ReadTimeout/WriteTimeout/IdleTimeout 是生产级基础服务的底线
6. **文件与资源用 defer 关闭**：打开后立即 defer Close，错误逐层用 `%w` 包装（ph02 习惯延续）
7. **flag 是标准命令行方案**：`-name`/`--name` 等价、`-h` 保留给帮助——简单工具无需 cobra
8. **time 的参考时间是 2006-01-02 15:04:05**：不是格式串里随便写的，用错则解析全错
9. **testing 入门门槛极低**：TestXxx + t.Errorf/t.Fatalf + go test 即可，表格驱动与子测试进 ph08
10. **标准库不会过时**：Go 1 兼容性承诺保证 API 只增不删，学到的知识长期有效

### 跨语言对比：标准库能力

| 维度 | Go | Java | Python | C++ | Rust |
|------|-----|------|--------|-----|------|
| 文件读写 | os/bufio（1.16 起 ReadFile 一步到位） | java.nio.file | open()/pathlib | fstream/文件系统库 | std::fs |
| JSON 序列化 | encoding/json（反射 + tag） | Jackson/Gson（第三方） | json（内置） | nlohmann/json（第三方） | serde_json（第三方） |
| HTTP 服务 | net/http（内置生产级） | Servlet/Spring（框架） | http.server（简易）/框架 | 无内置 | 无内置（axum/actix） |
| 命令行参数 | flag（内置） | picocli/args4j | argparse | 无内置 | clap（第三方） |
| 单元测试 | testing（内置） | JUnit（第三方） | unittest/pytest | GoogleTest（第三方） | cargo test（内置） |
| 并发与定时 | goroutine + time + context | java.util.concurrent | asyncio | std::thread | tokio（第三方） |

### 阶段验收清单

- [ ] 能用标准库读写文件和处理 JSON：os.ReadFile/WriteFile + json.Marshal/Unmarshal，全程零第三方依赖
- [ ] 能写基础 HTTP 服务：net/http 注册路由、返回 JSON、正确处理方法错误与状态码
- [ ] 能使用 testing 写单元测试：go test 通过，核心函数有测试覆盖
- [ ] 能理解 io.Reader/io.Writer 抽象，用 bufio 做流式处理（大文件不整载入内存）
- [ ] 能解释 JSON tag 与字段导出规则，说出 omitempty、"-" 等常用选项的含义

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：文件统计工具、JSON 配置解析器、HTTP API server、命令行 Todo 工具共 4 题，第 4 题含给工具补单元测试的要求。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**HTTP health check 工具**——给定一组 URL，周期性并发发起 GET 请求，统计状态码/延迟/失败率，超时可控，结果输出表格。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[测试与工程质量阶段](../ph08-testing/08-testing.md) ——单元测试深入（表格驱动、t.Run 子测试）、mock 依赖隔离、覆盖率、benchmark 与 benchmem、race detector 与 CI 集成。
