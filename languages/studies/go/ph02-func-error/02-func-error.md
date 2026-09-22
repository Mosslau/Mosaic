# Go 函数与错误处理阶段

> 面向后端服务、云原生和通用数据平台方向，掌握 Go 的函数设计与显式错误处理习惯。

## 1. 概述

Go 函数与错误处理阶段的目标是：**掌握 Go 的函数设计、显式错误返回和 `defer` 资源管理**。Go 用多返回值替代异常机制，把错误当作普通值来处理，这是 Go 工程风格的核心。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 函数基础 | 函数声明、多返回值、命名返回值、可变参数 |
| 函数进阶 | 匿名函数、闭包、函数作为参数 |
| 资源管理 | `defer` 的 LIFO 执行顺序与参数求值时机 |
| 错误处理 | `error` 接口、`errors.New`、`fmt.Errorf`（含 `%w`）、`errors.Is`/`errors.As` |
| 异常机制 | `panic`/`recover` 的定位与使用边界 |

这个阶段的核心不是语法本身，而是**错误处理习惯**：普通错误必须返回 `error` 值，`panic` 只用于不可恢复场景，`defer` 负责释放资源，错误信息要携带足够上下文。

这个阶段只涉及函数、闭包、`defer`/`panic`/`recover` 与错误值处理，**不涉及方法（Method）与接口（Interface）、包与模块组织、goroutine 并发** — 那些是 **ph04 方法与接口**、**ph05 包管理与工程结构**、**ph06 并发编程**阶段的内容。

## 2. 来源与演变

Go 设计者 Rob Pike 在 2014 年演讲《Errors are values》中提出：错误是值，不是控制流。

| 范式 | 代表语言 | 机制 | 特点 |
|------|---------|------|------|
| 返回码 | C | 整数返回值 + `errno` | 简单但易被忽略 |
| 异常 | C++、Java | `try`/`catch`/`throw` | 隐式控制流、栈展开开销大 |
| 错误值 | Go | 多返回值 `error` | 显式、可组合、无栈展开开销 |
| Result 类型 | Rust | `Result<T, E>` | 类型安全、强制处理 |

**Go 1.13（2019）** 增强了错误处理能力：引入 `fmt.Errorf` 的 `%w` 动词和 `errors.Is`/`errors.As`。

本文示例以 **Go 1.21+** 为基线（`errors.Is`/`As`、`%w` 均可直接使用），本环境验证工具链为 Go 1.22.2。错误处理范式自 Go 1.13 起稳定，1.21+ 默认支持全部本文特性。

## 3. 语法与参数

### 3.1 函数声明与多返回值

```go
package main

import (
    "errors"
    "fmt"
)

func add(a, b int) int { return a + b }

func divide(a, b int) (int, error) {
    if b == 0 {
        return 0, errors.New("divide by zero")
    }
    return a / b, nil
}

func main() {
    fmt.Println(add(3, 4))
    if result, err := divide(10, 2); err != nil {
        fmt.Println("错误:", err)
    } else {
        fmt.Println("结果:", result)
    }
}
```

相邻同类型参数可合并为 `a, b int`；参数默认**值传递**，错误传播路径完全可见。

### 3.2 命名返回值

命名返回值使签名自文档化，也允许裸 `return`：

```go
package main

import "fmt"

func rectangle(width, height float64) (area float64, err error) {
    if width <= 0 || height <= 0 {
        err = fmt.Errorf("invalid dimension: width=%.2f height=%.2f", width, height)
        return
    }
    area = width * height
    return
}

func main() {
    if a, err := rectangle(3, 4); err != nil {
        fmt.Println(err)
    } else {
        fmt.Println("面积:", a)
    }
}
```

### 3.3 可变参数与闭包

可变参数在内部被当作切片处理；闭包捕获外部变量本身：

```go
package main

import "fmt"

func sum(nums ...int) int {
    total := 0
    for _, n := range nums { total += n }
    return total
}

func main() {
    fmt.Println(sum(1, 2, 3)) // 6
    values := []int{4, 5, 6}
    fmt.Println(sum(values...)) // 15

    base := 10
    adder := func(x int) int { return base + x }
    fmt.Println(adder(5)) // 15
    base = 20
    fmt.Println(adder(5)) // 25
}
```

### 3.4 defer

`defer` 在函数返回前按**后进先出**顺序执行，参数在注册时立即求值：

```go
package main

import "fmt"

func main() {
    i := 0
    defer fmt.Println("defer:", i) // 注册时 i 为 0
    i = 100
    fmt.Println("main:", i)        // 100
}
```

### 3.5 panic 与 recover

`panic` 会停止当前函数执行并开始**栈展开**，直到被 `recover` 捕获或程序崩溃：

```go
package main

import "fmt"

func mayPanic() { panic("something went wrong") }

func main() {
    defer func() {
        if r := recover(); r != nil {
            fmt.Println("捕获 panic:", r)
        }
    }()
    mayPanic()
}
```

`panic` 只用于真正不可恢复的错误；`recover` 通常只在顶层或框架层使用。

### 3.6 error 接口与错误处理

`error` 是内置接口：

```go
type error interface {
    Error() string
}
```

```go
package main

import (
    "errors"
    "fmt"
    "os"
)

func main() {
    err1 := errors.New("connection refused")
    err2 := fmt.Errorf("load config failed: %w", err1)
    if _, err := os.Open("/tmp/not_exist.txt"); errors.Is(err, os.ErrNotExist) {
        fmt.Println("文件不存在")
    }
    fmt.Println(err2)
}
```

`fmt.Errorf` 的 `%w` 和 `errors.Is`/`errors.As` 都是 **Go 1.13** 引入的。

## 4. 底层原理

### 4.1 error 不是异常机制

`error` 本质上是一个值，返回 `error` 只是多返回值中的一个返回值，编译器不会做栈展开。优势：零运行时开销、强制显式处理、错误可自由包装与判定。

### 4.2 defer 与命名返回值的配合

`defer` 可以在函数返回前修改命名返回值：

```go
package main

import "fmt"

func counter() (count int) {
    defer func() { count++ }()
    return 10
}

func main() {
    fmt.Println(counter()) // 11
}
```

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 安全除法 | 多返回值、`errors.New` |
| 文件读取 | `defer` 关闭文件、`fmt.Errorf` 包装错误 |
| 配置加载 | 自定义错误类型、`errors.Is`/`errors.As` |
| 命令行参数校验 | 可变参数、闭包、错误聚合 |
| 资源释放保障 | `defer` LIFO 顺序 |
| 框架级容错 | `panic`/`recover` 顶层捕获 |

**不适合用 panic 的场景**：用户输入不合法、文件不存在、网络超时、业务规则校验失败——全部返回 `error`。

**适合用 panic 的场景**：程序启动必要依赖缺失、内部不变量严重破坏、开发期暴露不可能分支。

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.go`（各自独立的 package main，逐文件 `go run` 运行），已在本环境用 Go 1.22.2 验证（`gofmt -l` 无差异、`go vet` 通过）。

### 示例 1：安全除法

完整文件：`examples/ex01-safe-divide.go`

```go
package main

import (
    "errors"
    "fmt"
)

func divide(a, b int) (int, error) {
    if b == 0 {
        return 0, errors.New("divide by zero")
    }
    return a / b, nil
}

func main() {
    if result, err := divide(10, 3); err != nil {
        fmt.Println("错误:", err)
    } else {
        fmt.Println("10 / 3 =", result)
    }
    if _, err := divide(5, 0); err != nil {
        fmt.Println("错误:", err)
    }
}
```

### 示例 2：文件读取与 defer

完整文件：`examples/ex02-read-file-defer.go`

```go
package main

import (
    "fmt"
    "os"
)

func readConfig(path string) (string, error) {
    f, err := os.Open(path)
    if err != nil {
        return "", fmt.Errorf("open config %s: %w", path, err)
    }
    defer f.Close()

    buf := make([]byte, 1024)
    n, err := f.Read(buf)
    if err != nil {
        return "", fmt.Errorf("read config %s: %w", path, err)
    }
    return string(buf[:n]), nil
}

func main() {
    tmpFile := "/tmp/ph02_sample_config.txt"
    if err := os.WriteFile(tmpFile, []byte("timeout=30\nmax_conn=100"), 0644); err != nil {
        fmt.Println("创建临时文件失败:", err)
        return
    }
    if content, err := readConfig(tmpFile); err != nil {
        fmt.Println("读取失败:", err)
    } else {
        fmt.Println("配置内容:")
        fmt.Println(content)
    }
}
```

### 示例 3：配置加载器（自定义错误 + errors.Is）

完整文件：`examples/ex03-config-errors-is.go`

```go
package main

import (
    "errors"
    "fmt"
    "strconv"
    "strings"
)

var ErrInvalidConfig = errors.New("invalid config")

type Config struct {
    Timeout int
    MaxConn int
}

func parseConfig(input string) (Config, error) {
    var cfg Config
    for _, line := range strings.Split(strings.TrimSpace(input), "\n") {
        line = strings.TrimSpace(line)
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }
        parts := strings.SplitN(line, "=", 2)
        if len(parts) != 2 {
            return Config{}, fmt.Errorf("%w: malformed line %q", ErrInvalidConfig, line)
        }
        key, value := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
        var err error
        switch key {
        case "timeout":
            cfg.Timeout, err = strconv.Atoi(value)
        case "max_conn":
            cfg.MaxConn, err = strconv.Atoi(value)
        default:
            return Config{}, fmt.Errorf("%w: unknown key %q", ErrInvalidConfig, key)
        }
        if err != nil {
            return Config{}, fmt.Errorf("%w: %s must be integer: %w", ErrInvalidConfig, key, err)
        }
    }
    if cfg.Timeout <= 0 || cfg.MaxConn <= 0 {
        return Config{}, fmt.Errorf("%w: timeout and max_conn must be positive", ErrInvalidConfig)
    }
    return cfg, nil
}

func main() {
    input := `
# 服务配置
timeout=30
max_conn=100
`
    if cfg, err := parseConfig(input); err != nil {
        if errors.Is(err, ErrInvalidConfig) {
            fmt.Println("配置格式错误:", err)
        } else {
            fmt.Println("未知错误:", err)
        }
    } else {
        fmt.Printf("配置解析成功: timeout=%d, max_conn=%d\n", cfg.Timeout, cfg.MaxConn)
    }
}
```

### 示例 4：命令行参数校验工具

完整文件：`examples/ex04-cli-validator.go`

```go
package main

import (
    "fmt"
    "strconv"
)

type Validator func(value string) error

func required(field string) Validator {
    return func(value string) error {
        if value == "" {
            return fmt.Errorf("field %q is required", field)
        }
        return nil
    }
}

func intRange(field string, min, max int) Validator {
    return func(value string) error {
        n, err := strconv.Atoi(value)
        if err != nil {
            return fmt.Errorf("field %q must be integer: %w", field, err)
        }
        if n < min || n > max {
            return fmt.Errorf("field %q must be between %d and %d", field, min, max)
        }
        return nil
    }
}

func validate(value string, validators ...Validator) []error {
    var errs []error
    for _, v := range validators {
        if err := v(value); err != nil {
            errs = append(errs, err)
        }
    }
    return errs
}

func main() {
    params := map[string]string{"port": "8080", "timeout": "abc"}
    if errs := validate(params["port"], required("port"), intRange("port", 1, 65535)); len(errs) > 0 {
        fmt.Println("port 校验失败:")
        for _, err := range errs { fmt.Println("  -", err) }
    }
    if errs := validate(params["timeout"], required("timeout"), intRange("timeout", 1, 300)); len(errs) > 0 {
        fmt.Println("timeout 校验失败:")
        for _, err := range errs { fmt.Println("  -", err) }
    }
}
```

### 示例 5：panic 与 recover 的边界演示

完整文件：`examples/ex05-panic-recover.go`

```go
package main

import "fmt"

func riskyOperation() { panic("遇到不可恢复的内部错误") }

func safeRun() (err error) {
    defer func() {
        if r := recover(); r != nil {
            err = fmt.Errorf("recovered from panic: %v", r)
        }
    }()
    riskyOperation()
    return nil
}

func main() {
    if err := safeRun(); err != nil {
        fmt.Println("运行失败:", err)
    } else {
        fmt.Println("运行成功")
    }
}
```

## 7. 总结

### 关键要点

1. **错误是值**：Go 通过多返回值返回 `error`，没有异常机制，也没有隐式栈展开
2. **普通错误返回 error**：用户输入、文件不存在、网络超时等业务场景一律返回 `error`
3. **panic 只用于不可恢复错误**：继续运行会导致更大破坏时才使用
4. **defer 做资源释放**：打开文件后立即 `defer Close()`，保证退出路径上资源被释放
5. **错误信息要携带上下文**：用 `fmt.Errorf("...: %w", err)` 逐层包装，保留错误链
6. **用 errors.Is/errors.As 判定错误**：不要直接比较错误字符串
7. **命名返回值谨慎使用**：只在能提高可读性或需要 `defer` 修改返回值的场景使用

### 跨语言对比：错误处理范式

| 范式 | 机制 | 错误传播 | 典型开销 |
|------|------|---------|---------|
| C 返回码 | 整数返回值 + 全局状态 | 手动逐层检查 | 低 |
| C++/Java 异常 | `try`/`catch`/`throw` | 栈展开自动传播 | 栈展开开销较高 |
| Go error 值 | 多返回值 `error` 接口 | 显式返回与包装 | 低 |
| Rust Result | `Result<T, E>` | `?` 传播 + 类型约束 | 低 |

### 阶段验收清单

- [ ] 能写清晰错误返回路径，正确使用 `if err != nil` 处理错误
- [ ] 能正确使用 `defer` 释放资源，理解 LIFO 顺序和参数即时求值
- [ ] 能避免用 `panic` 控制业务流程
- [ ] 能使用 `fmt.Errorf` 的 `%w` 包装错误，并用 `errors.Is`/`errors.As` 判定
- [ ] 能设计简单的自定义错误类型

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：安全除法、文件读取错误处理、配置解析错误处理、自定义业务错误、defer 执行顺序，共 5 题。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：配置加载器——读取配置文件、解析 `key=value`、校验必填项、返回带上下文的错误链。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[Slice、Map、Struct 阶段](../ph03-slice-map-struct/03-slice-map-struct.md) — 深入切片底层、map 语义与结构体组合。
