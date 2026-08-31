# Go 测试与工程质量阶段

> 面向后端服务、云原生和车联网数据平台方向，本阶段把"能跑"升级为"可维护、可测试"——用测试、基准与静态检查守住工程质量底线。

## 1. 概述

Go 测试与工程质量阶段的目标是：**能写可维护、可测试的 Go 代码**——掌握 testing 表格驱动测试、用 httptest 验证 HTTP handler、用 race detector 排查数据竞争、用 benchmark 结合 benchmem 量化性能，并把 go test / go fmt / go vet / golangci-lint 变成日常与 CI 的默认动作。ph07 只学了 testing 入门（TestXxx + go test），本阶段扩展成一套完整方法论：**测什么、怎么隔离依赖、怎么量化性能、怎么守住格式与静态检查**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 单元测试 | testing、TestXxx、t.Errorf/t.Fatalf、t.Run 子测试 |
| 表格驱动测试 | 用例表 + 循环 + 子测试（Go 惯用风格） |
| 测试辅助 | t.Helper、t.Cleanup、测试文件组织 |
| 依赖隔离 | 接口 + 手写 stub/mock（testify 提示） |
| 性能基准 | BenchmarkXxx、b.N、-benchmem 分配分析 |
| 并发与健壮性 | race detector（-race）、fuzz testing（FuzzXxx） |
| 覆盖率与静态检查 | -cover、go vet、golangci-lint、go fmt |

本阶段的核心信念是"**测试是工程底线，不是额外负担**"：测试先行让代码天然更容易被调用和重构，质量工具链（go test / go vet / go fmt / golangci-lint）全部内置或开源，零引入成本。

这个阶段只涉及单元测试、基准测试、race/fuzz 检测与静态检查工具链这一层（承接 ph07 标准库阶段的 testing 入门与 net/http handler），**不涉及 Web 框架与中间件（gin/echo、JWT）、真实数据库集成测试（MySQL/Redis）、微服务与契约测试、CI/CD 流水线搭建和 pprof 深入剖析** — 那些是 ph09/ph10/ph11/ph12/ph13 阶段的内容。

## 2. 来源与演变

testing 包是 Go 1.0 发布时内置的三大件之一（并发、网络、测试），设计上刻意极简：没有断言库、没有测试基类，只有 `*testing.T` 一个参数和 `Errorf/Fatalf` 几个方法。**表格驱动测试（table-driven tests）** 是 Go 社区沉淀出的惯用风格——把"输入 + 期望"组织成表、循环执行、数据与断言逻辑分离；2013 年 Dave Cheney 的《TableDrivenTests》一文将其推向主流，Go 1.7 加入 `t.Run` 子测试后有了官方组织单元。与 JUnit 的注解式参数化、pytest 的 parametrize 不同，Go 坚持"**表就是普通代码**"，不加语法糖、没有魔法。

go test 工具链沿"工程质量"方向持续演进：Go 1.1 集成 **ThreadSanitizer** 提供 -race 数据竞争检测；Go 1.2 加入 -cover 覆盖率；Go 1.18 把 **fuzz testing**（FuzzXxx）原生带进标准库（此前是 Google 的 go-fuzz 第三方工具）。生态方面，**golangci-lint**（2018 年起）把 go vet 与 errcheck、staticcheck、gosec 等数百个 linter 聚合为一个命令，成为事实标准的 CI 质量门禁；testify 提供更舒适的断言与 mock 工具。整体脉络是：**官方工具链负责"测与查"，社区工具负责"更好用与更严格"**。

| 时间 | 事件 |
|------|------|
| 2012 | Go 1.0：testing 包与 go test 随语言发布，测试零第三方依赖 |
| 2012 | Go 1.1：-race 集成 ThreadSanitizer，数据竞争检测进入官方工具链 |
| 2013 | Go 1.2：-cover 覆盖率支持；表格驱动测试风格被社区广泛推广 |
| 2016 | Go 1.6：-coverpkg 支持跨包覆盖率统计；Go 1.7：testing.T.Run 子测试、t.Parallel 加入 |
| 2018 | golangci-lint 发布：聚合 vet 与社区 linter 的常用入口 |
| 2020 | Go 1.14：t.Cleanup 注册清理函数 |
| 2022 | Go 1.18：testing.F 原生 fuzz testing 进入标准库 |
| 2024 | Go 1.22：循环变量语义修复，表格测试不再需要 `tc := tc` 拷贝 |

本文示例以 **Go 1.22** 为基线（本阶段用到 Go 1.22 的路由通配符 `r.PathValue` 与循环变量语义修复），验证工具链 **go1.25.6（darwin/arm64）**，仅使用标准库。testing 包的 API（TestXxx / BenchmarkXxx / FuzzXxx）是 Go 中最稳定的接口之一，从 Go 1.0 至今保持向后兼容，放心学。

## 3. 语法与参数

### 3.1 testing 基础：TestXxx + t.Errorf / t.Fatalf

```go
// calc.go —— 被测代码
package main

func Sum(nums []int) int { // 求切片之和，空切片返回 0
	total := 0
	for _, n := range nums {
		total += n
	}
	return total
}
```

```go
// calc_test.go —— 测试文件，文件名必须以 _test.go 结尾
package main

import "testing"

func TestSum(t *testing.T) {
	if got := Sum([]int{1, 2, 3}); got != 6 {
		t.Errorf("Sum = %d, 期望 6", got) // 记录失败，继续执行
	}
	if got := Sum(nil); got != 0 {
		t.Fatalf("Sum(nil) = %d, 期望 0", got) // 立即终止当前测试
	}
}
```

要点：测试文件与业务代码**同包**，可直接访问未导出函数；TestXxx 签名固定 `func TestXxx(t *testing.T)`；**t.Errorf 标记失败继续跑、t.Fatalf 立即终止当前测试**——后续断言依赖前置结果时用 Fatalf；`go test -v` 看逐用例输出，`-run` 支持正则筛选（`-run TestSum`）。

### 3.2 表格驱动测试（表 + 循环 + t.Run 子测试）

```go
// calc_test.go —— 表格驱动：表 + 循环 + 子测试
package main

import "testing"

func TestSumTable(t *testing.T) {
	cases := []struct { // 匿名结构体切片：一张"输入+期望"的表
		name string
		in   []int
		want int
	}{
		{"空切片", nil, 0},
		{"单元素", []int{5}, 5},
		{"正数", []int{1, 2, 3}, 6},
		{"负数", []int{-1, -2, -3}, -6},
		{"混合", []int{1, -2, 3}, 2},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) { // 每个用例一个子测试
			if got := Sum(tc.in); got != tc.want {
				t.Errorf("Sum(%v) = %d, 期望 %d", tc.in, got, tc.want)
			}
		})
	}
}
```

要点：**表格驱动测试是 Go 最常用的测试风格**（必会概念）——"数据与断言分离"，新增用例只加一行表数据；t.Run 子测试可**单独筛选**：`go test -run 'TestSumTable/负数'`，失败定位精确到用例名；**坑：Go 1.22 之前循环变量被闭包共享**，子测试里需 `tc := tc` 拷贝，Go 1.22+ 已修复。

### 3.3 测试辅助函数与 t.Helper

```go
// mathutil.go
package main

import "fmt"

func Abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func Div(a, b int) (int, error) {
	if b == 0 {
		return 0, fmt.Errorf("divide by zero")
	}
	return a / b, nil
}
```

```go
// mathutil_test.go —— t.Helper：失败信息指向调用处
package main

import "testing"

func assertEqual(t *testing.T, got, want any) {
	t.Helper() // 标记为辅助函数
	if got != want {
		t.Errorf("got %v, 期望 %v", got, want)
	}
}

func TestAbs(t *testing.T) {
	assertEqual(t, Abs(-5), 5)
	assertEqual(t, Abs(0), 0)
}

func TestDiv(t *testing.T) {
	got, err := Div(10, 2)
	if err != nil {
		t.Fatalf("意外错误: %v", err)
	}
	assertEqual(t, got, 5)
}
```

要点：**t.Helper() 让失败信息指向调用测试的位置而不是辅助函数内部**，自定义断言必加；辅助函数把 `t *testing.T` 作为第一参数是惯例；`any` 是 `interface{}` 的别名（Go 1.18+）；资源清理用 **t.Cleanup**（Go 1.14+）注册，函数结束时自动执行。

### 3.4 mock 与接口隔离

```go
// store.go —— 业务只依赖接口，不依赖具体实现
package main

import "fmt"

type Store interface {
	Get(key string) (string, error)
	Set(key, value string) error
}

type Service struct{ store Store }

func NewService(s Store) *Service { return &Service{store: s} }

func (s *Service) SaveConfig(key, value string) error {
	if key == "" {
		return fmt.Errorf("key 不能为空")
	}
	return s.store.Set(key, value)
}
```

```go
// store_test.go —— 手写 stub 隔离存储
package main

import (
	"errors"
	"testing"
)

type fakeStore struct {
	data map[string]string
	fail bool
}

func (f *fakeStore) Get(key string) (string, error) {
	if v, ok := f.data[key]; ok {
		return v, nil
	}
	return "", errors.New("not found")
}

func (f *fakeStore) Set(key, value string) error {
	if f.fail {
		return errors.New("store down")
	}
	f.data[key] = value
	return nil
}

func TestServiceSaveConfig(t *testing.T) {
	svc := NewService(&fakeStore{data: map[string]string{}})
	if err := svc.SaveConfig("timeout", "30"); err != nil {
		t.Fatalf("保存失败: %v", err)
	}
}

func TestServiceSaveConfigEmptyKey(t *testing.T) {
	svc := NewService(&fakeStore{data: map[string]string{}})
	if err := svc.SaveConfig("", "30"); err == nil {
		t.Fatal("空 key 应当报错")
	}
}
```

要点：**接口有助于隔离测试依赖**（必会概念，也是 ph04"接口由使用方定义"的落地）——业务依赖 Store 接口，测试注入手写 stub，用 map + 错误开关模拟成功/失败路径；stub 零第三方依赖；断言想要更舒适可引入 **testify**（`assert.Equal`、`require.NoError`），但 mock 本身永远可以手写。

### 3.5 benchmark：BenchmarkXxx + b.N + benchmem

```go
// calc_test.go —— b.N 自动校准，-benchmem 看分配
// 包级 sink：承接 benchmark 结果，防止编译器把循环整体优化掉（见下方"坑"）
package main

import (
	"strings"
	"testing"
)

var (
	sinkInt    int
	sinkString string
)

func BenchmarkSum(b *testing.B) {
	nums := []int{1, 2, 3, 4, 5}
	for i := 0; i < b.N; i++ {
		sinkInt = Sum(nums)
	}
}

func BenchmarkJoin(b *testing.B) {
	parts := []string{"a", "b", "c", "d", "e"}
	b.Run("strings.Join", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			sinkString = strings.Join(parts, ",")
		}
	})
	b.Run("手动拼接", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			s := ""
			for _, p := range parts {
				s += p
			}
			sinkString = s
		}
	})
}
```

运行 `go test -bench=. -benchmem -run=^$`，输出形如：

```text
BenchmarkSum-10              1000000000    0.97 ns/op   0 B/op   0 allocs/op
BenchmarkJoin/strings.Join-10   1000000    1200 ns/op  32 B/op   4 allocs/op
BenchmarkJoin/手动拼接-10         500000    2600 ns/op  80 B/op   5 allocs/op
```

要点：**b.N 由框架自动校准到稳定运行时间**（默认约 1 秒），不要手写固定循环次数；**benchmark 要结合 benchmem 看分配**（必会概念）——ns/op 看速度，B/op 与 allocs/op 看 GC 压力；`-run=^$` 跳过普通测试只跑基准，`-benchtime=5s`、`-count=3` 调时长与重复；**坑：结果可能被编译器优化消除**（dead code elimination）——把结果赋给包级变量，或用 b.ResetTimer/b.StopTimer 精确控制计时区间。

### 3.6 race detector（-race）

```go
// counter.go —— 有竞争的版本
package main

type Counter struct{ n int }

func (c *Counter) Inc()        { c.n++ }
func (c *Counter) Value() int { return c.n }
```

```go
// counter_test.go —— 制造并发交错，-race 才能抓到
package main

import (
	"sync"
	"testing"
)

func TestCounterConcurrent(t *testing.T) {
	var c Counter
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Inc()
		}()
	}
	wg.Wait()
	if c.Value() != 100 {
		t.Errorf("期望 100, 实际 %d", c.Value())
	}
}
```

运行 `go test -race -run TestCounterConcurrent` 会输出 `WARNING: DATA RACE` 及两处 goroutine 栈。要点：**race detector 可发现数据竞争**（必会概念）——-race 编译时插入检测代码，运行时发现"无同步关系的并发读写"立即报错；`go test -race ./...` 全仓检查是并发代码的必修动作（呼应 ph06 阶段验收）；**坑：race 是动态检测，只覆盖实际执行到的交错路径**——测试要真正制造并发才有效；-race 有约 5-10 倍开销，只用于测试、绝不用于生产构建。

### 3.7 覆盖率（-cover）

```bash
go test -cover ./...                        # 汇总百分比
go test -coverprofile=cover.out ./...       # 输出到文件
go tool cover -func=cover.out               # 函数级明细
go tool cover -html=cover.out               # 浏览器可视化（红色 = 未覆盖）
```

要点：**覆盖率回答"哪些代码被执行过"，不是"代码是否正确"**——100% 覆盖也可能有 bug，核心业务函数优先；标准工作流是 `-coverprofile` 产出 + `go tool cover` 分析，CI 可设阈值门槛（如 80%）；`-coverpkg=./...` 可跨包统计。

### 3.8 fuzz testing 基础（FuzzXxx）

```go
// examples/ex06-fuzz-test/wordcount.go —— 被测代码（与 strings.Fields 的空白定义一致）
package main

import "unicode"

func WordCount(s string) int {
	count := 0
	inWord := false
	for _, r := range s {
		if unicode.IsSpace(r) {
			inWord = false
		} else if !inWord {
			count++
			inWord = true
		}
	}
	return count
}
```

```go
// examples/ex06-fuzz-test/wordcount_test.go —— 不变量：与参考实现 strings.Fields 结果一致
package main

import (
	"strings"
	"testing"
)

func FuzzWordCount(f *testing.F) {
	f.Add("hello world") // 种子语料：从正常输入出发
	f.Add("  多空格  a\tb\n")
	f.Fuzz(func(t *testing.T, s string) {
		if got := WordCount(s); got != len(strings.Fields(s)) {
			t.Errorf("WordCount(%q) 结果不一致", s)
		}
	})
}
```

运行 `go test -fuzz=FuzzWordCount -fuzztime=10s`。要点：**fuzz 自动生成随机输入，寻找崩溃、panic 与断言失败**（必会概念）；断言的是**不变量（属性）**而非具体期望；失败输入自动写入 `testdata/fuzz/`，之后普通 `go test` 也复跑防回归；`-fuzztime` 限制时长（CI 必须传）；Go 1.18+ 原生支持。

### 3.9 go vet 与 golangci-lint

```bash
go vet ./...               # 官方静态检查：可疑构造、错误格式化串、拷贝锁等
golangci-lint run          # 聚合 linter：vet + errcheck + staticcheck + gosec ...
```

要点：**go vet 会随 go test 自动运行**（vet 不通过则测试不跑）；**golangci-lint 是事实标准的 linter 聚合入口**，一次配置几百个检查；建议 ph08 起就养成习惯，ph12 接入 CI 时零成本迁移。

### 3.10 go fmt 与代码风格

```go
// 未格式化的代码
package main
import "fmt"
func main(){
fmt.Println("hi")
}
```

```bash
go fmt ./...      # 一键格式化整个仓库（gofmt 风格）
gofmt -l .        # 列出需要格式化的文件（CI 里输出非空即失败）
```

要点：**Go 的代码格式只有一个标准——gofmt**（呼应 ph01 必会概念"代码格式由 gofmt 统一"），团队无需讨论风格；编辑器保存时自动格式化是标配；`gofmt -l .` 是 CI 检查格式的惯用命令。

## 4. 底层原理

### 4.1 go test 的编译与运行模型

- `go test` 为每个测试包**生成一个 test main**（`_testmain.go`）：注册包内全部 TestXxx / BenchmarkXxx / FuzzXxx，与被测代码一起编译成独立二进制再运行——这就是"测试能访问包内未导出符号"的原因
- 运行结果 PASS/FAIL + 总耗时；失败断言输出**源码位置**（文件:行号），`-v` 可见逐用例明细
- `-run` / `-bench` / `-fuzz` 都是**正则筛选**；`go test ./...` 逐个包跑，包之间默认并行（`-p` 控制）
- **测试缓存**：输入没变化时 go test 秒回 `(cached)`——`-count=1` 强制重跑（CI 常用）
- 包内测试默认串行；`t.Parallel()` 标记可并行的测试，配合 `-parallel` 并发执行（共享全局状态时注意隔离）

### 4.2 race detector 的实现原理（TSan）

- 基于 Google 的 **ThreadSanitizer（TSan）**：编译期对每个内存读写插桩，运行时为每个地址维护**访问历史（shadow memory）**
- 判定规则：两个 goroutine 对同一地址的访问之间**不存在 happens-before 关系**且至少一方是写 → 报告 DATA RACE；happens-before 由锁、channel、WaitGroup、atomic 等同步原语建立
- 报告格式：`WARNING: DATA RACE` + 两处 goroutine 栈 + "was created by" 指出 goroutine 诞生位置——据此定位"谁在并发碰同一份数据"
- **局限**：动态检测只能覆盖实际执行到的交错路径，**没跑到就不报**——需要设计真正并发的用例；不能证明"无竞争"

### 4.3 覆盖率统计的插桩机制

- `go test -cover` 在**编译期**对源码插桩：在每个基本块（语句序列）边界插入计数器，执行到即自增
- 测试结束后聚合："被覆盖块数 / 总块数"即语句覆盖率；`go tool cover -func` 输出函数级、`-html` 把未覆盖行标红——**红色通常是没测到的错误路径**
- **注意**：默认只统计被测包内代码（`-coverpkg` 可跨包）；分支条件的不同取值不一定全覆盖（谓词覆盖不足）——覆盖率低是明确信号，覆盖率高不代表正确

### 4.4 benchmark 的校准与最小时间

- **b.N 自动校准**：从小值开始倍增（1、2、5、10、25…），直到单次运行时长达到目标（默认 1 秒）且稳定——保证每种实现都跑"足够久"而非"同样多次"
- `-benchtime=5s` 调目标时长、`-count=3` 重复取方差；结果三列：**ns/op（每次耗时）、B/op（每次分配字节）、allocs/op（每次分配次数）**——分配多意味着 GC 压力大（ph13 详谈）
- 计时默认覆盖整个循环体：`b.ResetTimer()` 排除 setup，`b.StopTimer()/b.StartTimer()` 精确圈定计时区间
- **优化器风险**：计算结果未使用会被整段删除——用包级变量承接结果（示例 5 与 3.5 节的 benchmark 都用包级 sink 承接，正是这个思路的落地；复杂场景同理用 `globalSink = result`）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 业务函数回归保障 | testing、表格驱动测试、-cover |
| HTTP handler 行为验证 | httptest、JSON 断言、注入依赖 |
| 并发代码正确性 | -race、Mutex 修复 |
| 外部依赖隔离（数据库/网络/时钟） | 接口 + 手写 stub/mock |
| 核心路径性能基线 | BenchmarkXxx、-benchmem |
| 崩溃与边界输入挖掘 | FuzzXxx、testdata/fuzz |
| CI 质量门禁 | go test ./...、go vet、golangci-lint、gofmt -l |
| 团队格式与风格统一 | go fmt、gofmt |

**不适合**此阶段的事项：

- **pprof 深入剖析**（CPU/内存 profile、火焰图、GC 分析）：benchmark 只做"快不快、分配多不多"的初判，深入定位属 ph13
- **E2E / 契约测试**（真实服务间的端到端、consumer-driven contract）：属 ph11 微服务阶段
- **真实数据库/外部服务的集成测试**（MySQL、Redis、第三方 API）：本阶段一律接口 + stub 隔离，属 ph10/ph11
- **CI/CD 流水线搭建**：先让 `go test ./...` 本地一键通过，流水线编排属 ph12

## 6. 代码示例

### 示例 1：表格驱动测试（业务函数 + 边界用例）

```go
// examples/ex01-table-test/speed.go —— 车辆平均速度与超速判断
// 验证环境：go1.25.6（darwin/arm64），测试命令：go test -v ./...（已验证）
package main

import "fmt"

func AvgSpeed(speeds []float64) (float64, error) {
	if len(speeds) == 0 {
		return 0, fmt.Errorf("speeds 不能为空")
	}
	var total float64
	for _, s := range speeds {
		if s < 0 {
			return 0, fmt.Errorf("速度不能为负: %v", s)
		}
		total += s
	}
	return total / float64(len(speeds)), nil
}

// IsOverLimit 是否超速（等于限速不算超速）
func IsOverLimit(speed, limit float64) bool { return speed > limit }

func main() {
	avg, _ := AvgSpeed([]float64{60, 80})
	fmt.Println("平均速度:", avg)
}
```

```go
// examples/ex01-table-test/speed_test.go —— 正常 + 边界 + 错误路径全覆盖
package main

import "testing"

func TestAvgSpeed(t *testing.T) {
	cases := []struct {
		name    string
		in      []float64
		want    float64
		wantErr bool // 区分"期望错误"与"期望成功"两种断言分支
	}{
		{"空输入报错", nil, 0, true},
		{"单元素", []float64{60}, 60, false},
		{"正常", []float64{60, 80, 100}, 80, false},
		{"含零", []float64{0, 120}, 60, false},
		{"负速度报错", []float64{-1, 60}, 0, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := AvgSpeed(tc.in)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("期望报错, 实际得到 %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("意外错误: %v", err)
			}
			if got != tc.want {
				t.Errorf("AvgSpeed(%v) = %v, 期望 %v", tc.in, got, tc.want)
			}
		})
	}
}

func TestIsOverLimit(t *testing.T) {
	cases := []struct {
		speed, limit float64
		want         bool
	}{
		{120, 100, true},  // 超速
		{100, 100, false}, // 等于限速不超速（边界）
		{80, 100, false},
	}
	for _, tc := range cases {
		if got := IsOverLimit(tc.speed, tc.limit); got != tc.want {
			t.Errorf("IsOverLimit(%v, %v) = %v, 期望 %v", tc.speed, tc.limit, got, tc.want)
		}
	}
}
```

要点：**边界用例（空、负数、等于限速）比正常用例更能暴露缺陷**；wantErr 字段让一张表覆盖"期望成功"与"期望报错"两条分支；运行 `go test -v -run TestAvgSpeed`，再跑 `go test -cover` 观察覆盖率。这是 roadmap 练习"给业务函数写表格驱动测试"的完整答案。

### 示例 2：HTTP handler 测试（httptest + 断言 JSON）

```go
// examples/ex02-http-test/handler.go —— 可注入依赖的 handler 工厂（Go 1.22+ 路由通配符）
// 验证环境：go1.25.6（darwin/arm64），测试命令：go test -v ./...（已验证）
package main

import (
	"encoding/json"
	"net/http"
)

type Device struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// NewHandler 返回带路由的 handler；数据源作为参数注入，测试时可替换
func NewHandler(devices map[string]Device) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices/{id}", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		d, ok := devices[id]
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found"})
			return
		}
		writeJSON(w, http.StatusOK, d)
	})
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
```

```go
// examples/ex02-http-test/handler_test.go —— 零网络开销的 handler 测试
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetDevice(t *testing.T) {
	h := NewHandler(map[string]Device{"car-001": {ID: "car-001", Status: "online"}})
	req := httptest.NewRequest(http.MethodGet, "/devices/car-001", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 %d", rec.Code, http.StatusOK)
	}
	var got Device
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if got.ID != "car-001" || got.Status != "online" {
		t.Errorf("响应 = %+v, 期望 car-001/online", got)
	}
}

func TestGetDeviceNotFound(t *testing.T) {
	h := NewHandler(map[string]Device{})
	req := httptest.NewRequest(http.MethodGet, "/devices/nope", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("状态码 = %d, 期望 404", rec.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if body["error"] == "" {
		t.Error("错误响应缺少 error 字段")
	}
}
```

要点：**httptest.NewRequest + httptest.NewRecorder 让 handler 测试完全不启动网络**；handler 写成"工厂函数 + 注入依赖"而非全局 ServeMux——测试时传入内存 map，无需 mock 整个 HTTP 层；`r.PathValue` 是 Go 1.22 路由通配符（更早版本用 `strings.TrimPrefix`）；**状态码 + JSON 字段双重断言**。这是 roadmap 练习"给 handler 写测试"与推荐项目"带测试的 HTTP API"的核心。

### 示例 3：并发代码 race 检测（-race 复现并修复）

```go
// examples/ex03-race-detector/racy/cache.go —— 有竞争的版本：无锁 map
// 故意出错示例：请用 go test -race ./racy 观察 DATA RACE 报告，勿在生产使用
package racy

type Cache struct {
	data map[string]string
}

func NewCache() *Cache { return &Cache{data: make(map[string]string)} }

func (c *Cache) Set(k, v string)     { c.data[k] = v }
func (c *Cache) Get(k string) string { return c.data[k] }
```

```go
// examples/ex03-race-detector/racy/cache_test.go —— 制造真实并发交错（仅 -race 模式运行）
// raceEnabled 由同包 //go:build race 标签文件注入：不加 -race 时用例自动跳过，
// 避免裸跑触发 concurrent map writes 崩溃（完整文件见 examples/ex03-race-detector/racy/）
package racy

import (
	"sync"
	"testing"
)

func TestCacheConcurrent(t *testing.T) {
	if !raceEnabled {
		t.Skip("本用例演示 DATA RACE，仅在 go test -race 下运行")
	}
	c := NewCache()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(2)
		go func() { defer wg.Done(); c.Set("k", "v") }() // 并发写 map
		go func() { defer wg.Done(); _ = c.Get("k") }()  // 并发读 map
	}
	wg.Wait()
}
```

运行 `go test -race ./...` 会输出 `WARNING: DATA RACE`（测试"失败"是预期效果）；不加 `-race` 时用例自动跳过（`//go:build race` 探测），避免裸跑触发 `fatal error: concurrent map writes` 崩溃。修复——加 Mutex：

```go
// examples/ex03-race-detector/fixed/cache.go —— 修复版：Mutex 保护共享状态（ph06 并发编程阶段必会概念落地）
// 验证环境：go1.25.6（darwin/arm64），测试命令：go test -race ./...（fixed 包已验证通过）
package fixed

import "sync"

type Cache struct {
	mu   sync.Mutex
	data map[string]string
}

func NewCache() *Cache { return &Cache{data: make(map[string]string)} }

func (c *Cache) Set(k, v string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[k] = v
}

func (c *Cache) Get(k string) string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.data[k]
}
```

再次运行 `go test -race ./...` 通过。要点：**map 并发写是 Go 里最典型的数据竞争**，即使不崩溃也可能读到损坏数据；**race detector 可发现数据竞争**（必会概念），`go test -race ./...` 是并发模块的标配；**坑：race 是动态检测，测试必须真正制造并发**（本示例用 WaitGroup 确保交错执行）；生产构建不要加 -race。这是练习"给并发代码跑 race"与推荐项目"并发模块 benchmark"的质量底座。

### 示例 4：mock 隔离外部依赖（接口 + 手写 stub）

```go
// examples/ex04-mock-stub/reporter.go —— 遥测上报服务：依赖接口，不依赖具体通道
// 验证环境：go1.25.6（darwin/arm64），测试命令：go test -v ./...（已验证）
package main

import "fmt"

// Reporter 外部上报通道（真实实现：MQTT/HTTP，见 ph09/ph11）
type Reporter interface {
	Report(deviceID string, payload map[string]any) error
}

type TelemetryService struct{ reporter Reporter }

func NewTelemetryService(r Reporter) *TelemetryService {
	return &TelemetryService{reporter: r}
}

func (s *TelemetryService) Publish(deviceID string, payload map[string]any) error {
	if deviceID == "" {
		return fmt.Errorf("deviceID 不能为空")
	}
	if s.reporter == nil {
		return fmt.Errorf("reporter 未初始化")
	}
	return s.reporter.Report(deviceID, payload)
}
```

```go
// examples/ex04-mock-stub/reporter_test.go —— 手写 stub：记录调用、可模拟故障
package main

import (
	"errors"
	"testing"
)

type stubReporter struct {
	calls []string // 记录每次上报的 deviceID，用于行为断言
	fail  bool
}

func (s *stubReporter) Report(deviceID string, payload map[string]any) error {
	if s.fail {
		return errors.New("上报通道不可用")
	}
	s.calls = append(s.calls, deviceID)
	return nil
}

func TestPublishSuccess(t *testing.T) {
	stub := &stubReporter{}
	svc := NewTelemetryService(stub)
	if err := svc.Publish("car-001", map[string]any{"speed": 80}); err != nil {
		t.Fatalf("上报失败: %v", err)
	}
	if len(stub.calls) != 1 || stub.calls[0] != "car-001" {
		t.Errorf("调用记录 = %v, 期望 [car-001]", stub.calls)
	}
}

func TestPublishChannelDown(t *testing.T) {
	stub := &stubReporter{fail: true}
	svc := NewTelemetryService(stub)
	if err := svc.Publish("car-001", map[string]any{}); err == nil {
		t.Error("通道故障时应当返回错误")
	}
}

func TestPublishEmptyID(t *testing.T) {
	svc := NewTelemetryService(&stubReporter{})
	if err := svc.Publish("", map[string]any{}); err == nil {
		t.Error("空 deviceID 应当返回错误")
	}
}
```

要点：**"接口有助于隔离测试依赖"是本阶段必会概念**——service 依赖 Reporter 接口，测试注入 stub，全程不碰真实网络；stub 除了返回预设值，还能**记录调用参数做行为断言**（"被调用了几次、用了什么参数"）；gomock、testify/mock 适合复杂依赖树，但**手写 stub 对 90% 场景足够且零依赖**；真实通道联调不属于单测范畴（见 5 不适合清单）。

### 示例 5：benchmark + 覆盖率（benchmem 分析 + 覆盖率报告）

```go
// examples/ex05-benchmark-cover/jsonutil.go —— 两种 JSON 编码实现，供基准对比
// 验证环境：go1.25.6（darwin/arm64），命令：go test -bench=. -benchmem -run=^$（已验证）
package main

import (
	"encoding/json"
	"fmt"
	"strconv"
)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

// EncodePoint 用 encoding/json（反射，通用但慢）
func EncodePoint(p Point) ([]byte, error) { return json.Marshal(p) }

// PointString 手写格式化：strconv 直接写字节缓冲，避开反射路径（快），但格式写死
func PointString(p Point) string {
	b := make([]byte, 0, 64)
	b = append(b, `{"x":`...)
	b = strconv.AppendFloat(b, p.X, 'g', -1, 64)
	b = append(b, `,"y":`...)
	b = strconv.AppendFloat(b, p.Y, 'g', -1, 64)
	b = append(b, '}')
	return string(b)
}

func main() {
	data, _ := EncodePoint(Point{X: 1.5, Y: 2.5})
	fmt.Println(string(data))
}
```

```go
// examples/ex05-benchmark-cover/jsonutil_test.go —— 正确性测试 + 两个 benchmark
// 包级 sink 承接结果，防止编译器把 benchmark 循环整体优化掉（见 4.4 优化器风险）
package main

import "testing"

var (
	sinkBytes  []byte
	sinkString string
)

func TestEncodePoint(t *testing.T) {
	data, err := EncodePoint(Point{X: 1.5, Y: 2.5})
	if err != nil {
		t.Fatalf("编码失败: %v", err)
	}
	if string(data) != `{"x":1.5,"y":2.5}` {
		t.Errorf("输出 = %s", data)
	}
}

func TestPointString(t *testing.T) {
	if got := PointString(Point{X: 1.5, Y: 2.5}); got != `{"x":1.5,"y":2.5}` {
		t.Errorf("输出 = %s", got)
	}
}

func BenchmarkEncodePoint(b *testing.B) {
	p := Point{X: 1.5, Y: 2.5}
	for i := 0; i < b.N; i++ {
		sinkBytes, _ = EncodePoint(p) // 赋值给包级变量，结果不可被优化消除
	}
}

func BenchmarkPointString(b *testing.B) {
	p := Point{X: 1.5, Y: 2.5}
	for i := 0; i < b.N; i++ {
		sinkString = PointString(p)
	}
}
```

运行与产出：

```bash
go test -bench=. -benchmem -run=^$ ./...
# BenchmarkEncodePoint-14    ...   120 ns/op   24 B/op   1 allocs/op
# BenchmarkPointString-14    ...    61 ns/op   24 B/op   1 allocs/op

go test -cover ./...
# coverage: 61.5% of statements   ← 未覆盖的是 main 入口，两个被测函数均 100%

go test -coverprofile=cover.out ./... && go tool cover -func=cover.out
go tool cover -html=cover.out     # 浏览器打开，红色标出未覆盖行
```

要点：**对比结论**——手写 strconv 版约 61 ns/op，比 json.Marshal（约 120 ns/op）**快约 2 倍**，因为它避开了反射路径；两者分配持平（24 B/op、1 allocs/op）——注意 **string(b) 转换仍需 1 次拷贝**，真正零分配需要 unsafe 技巧（超出本阶段）；"快不快"看 ns/op、"分配多不多"看 B/op 与 allocs/op（**benchmark 要结合 benchmem 看分配**，必会概念）；但**选型不能只看数字**：反射方案通用、字段多时仍正确，手写方案格式写死——低频率路径不值得手写（呼应 ph13 性能优化阶段"先 profile 再优化"）；覆盖率 61.5% 的缺口是 **main 入口（示例演示代码）没测**，两个被测函数均为 100%——覆盖率要盯核心函数，别被演示入口拖低百分比。这是练习"给核心模块写 benchmark"的完整答案。

### 示例 6：fuzz testing + Example 文档示例（不变量断言）

```go
// examples/ex06-fuzz-test/wordcount_test.go —— 不变量断言 + Example 文档示例
// 验证环境：go1.25.6（darwin/arm64），命令：go test -v（已验证）、go test -fuzz=FuzzWordCount -fuzztime=10s（已验证）
package main

import (
	"fmt"
	"strings"
	"testing"
)

func FuzzWordCount(f *testing.F) {
	f.Add("hello world") // 种子语料：从正常输入出发
	f.Add("  多空格  a\tb\n")
	f.Fuzz(func(t *testing.T, s string) {
		if got := WordCount(s); got != len(strings.Fields(s)) {
			t.Errorf("WordCount(%q) 结果不一致", s)
		}
	})
}

// Example 函数是"会被 go test 执行"的文档示例：Output 注释必须与实际输出逐字符一致
func ExampleWordCount() {
	fmt.Println(WordCount("hello world"))
	// Output: 2
}
```

要点：**fuzz 断言的是不变量**（与参考实现 `strings.Fields` 结果一致），不是具体期望值——完整被测代码见 3.8 节；Example 函数同时承担文档与测试两个角色，`go test` 会比对 `// Output:` 注释与实际输出。完整文件在 `examples/ex06-fuzz-test/`。

## 7. 总结

### 关键要点

1. **表格驱动测试是 Go 的惯用风格**：数据与断言分离，新增用例只加一行表数据，配合 t.Run 子测试精确定位失败
2. **t.Errorf 与 t.Fatalf 分工明确**：Errorf 记录失败继续跑、Fatalf 立即终止——后续断言依赖前置结果时用 Fatalf
3. **t.Helper() 是辅助断言的标配**：让失败信息指向调用处而不是辅助函数内部
4. **接口是测试隔离的钥匙**：业务依赖接口、测试注入手写 stub，不碰真实网络/数据库——"接口有助于隔离测试依赖"是本阶段必会概念
5. **benchmark 必须结合 benchmem**：ns/op 看速度、B/op 与 allocs/op 看分配——分配多意味着 GC 压力大
6. **race detector 是并发代码的必修课**：`go test -race ./...` 能发现数据竞争，但它是动态检测，需要用例真正制造并发
7. **覆盖率是"执行过"不是"正确"**：用 `-coverprofile` + `go tool cover` 找未覆盖分支（通常是错误路径），别只盯百分比
8. **fuzz testing 用不变量代替手写用例**：自动生成输入找崩溃与断言失败，失败输入自动入库防回归
9. **go test / go vet / go fmt / golangci-lint 是质量四件套**：vet 随 go test 自动跑，golangci-lint 做 CI 门禁，gofmt 消灭格式争论
10. **测试是工程底线不是额外负担**：ph08 之后每个阶段的项目都要带测试，为 ph09 起的 Web 服务、ph11 起的微服务打好可维护地基

### 跨语言对比：测试与质量工具

| 维度 | Go testing | Java JUnit | Python pytest | Rust cargo test | C++ 框架 |
|------|-----------|-----------|--------------|-----------------|---------|
| 测试框架 | testing（标准库内置） | JUnit 5（第三方） | pytest（第三方） | 内置测试属性 | GoogleTest / Catch2 |
| 断言风格 | t.Errorf/Fatalf + 手写 | Assertions.assertEquals | assert 语句 | assert! / assert_eq! | EXPECT_EQ / ASSERT_EQ |
| 表格/参数化 | 表 + t.Run（普通代码） | @ParameterizedTest | @pytest.mark.parametrize | 手写循环 | 手写循环 / 模板 |
| 基准测试 | testing.B + -benchmem | JMH（独立工具） | pytest-benchmark | 内置 bench | Google Benchmark |
| 数据竞争检测 | -race（内置 TSan） | 无内置 | 无内置 | loom / sanitizer | TSan（第三方） |
| 覆盖率 | go test -cover | JaCoCo | pytest-cov | tarpaulin / grcov | gcov / lcov |
| Mock 生态 | 手写 stub（默认）/ testify | Mockito | unittest.mock | mockall | GoogleMock |

### 阶段验收清单

- [ ] **能一键运行测试**：`go test ./...` 全部通过，并发包用 `go test -race ./...` 验证无数据竞争
- [ ] **能解释覆盖率结果**：说出 `go test -cover` 百分比的含义，会用 `go tool cover -func/-html` 定位未覆盖代码并补测试
- [ ] **能解释 benchmark 结果**：读懂 ns/op、B/op、allocs/op 三个数字，能说出分配对 GC 的影响，能对比两种实现的优劣
- [ ] **能用 mock 隔离外部依赖**：接口 + 手写 stub 让测试不依赖真实网络/数据库，能断言 stub 的调用行为
- [ ] **能写出表格驱动测试**：表结构 + 循环 + t.Run 子测试，覆盖边界与错误路径，会用 `-run` 筛选单个用例
- [ ] **质量工具纳入日常**：go vet / golangci-lint / go fmt 在本地与 CI 中均无告警

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap「练习」小节一一对应：

1. **给业务函数写表格驱动测试**：覆盖空输入、边界值、错误路径（提示：表结构加 wantErr 字段——示例 1）
2. **给 handler 写测试**：用 httptest.NewRequest + NewRecorder 测状态码与 JSON 响应，覆盖 200 与 404 两条路径（提示：handler 写成工厂函数 + 注入依赖——示例 2）
3. **给并发代码跑 race**：修掉数据竞争后用 `go test -race ./...` 验证（提示：Mutex 保护共享状态——示例 3）
4. **给核心模块写 benchmark**：对比两种实现并记录 benchmem 结果（提示：`-benchmem` 看 B/op 与 allocs/op——示例 5）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**带测试的设备管理 HTTP API**——在 ph07 标准库阶段 HTTP API server 基础上重构为 NewHandler + 依赖注入，为每个路由写 httptest 测试（200/404/400/405），跑 `-race` 验证并发安全，再用 `-cover` 生成覆盖率报告并补齐未覆盖分支。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

roadmap 第二个推荐项目「并发模块 benchmark」可在完成本项目后作为扩展：给 ph06 并发编程阶段的 worker pool 写 Benchmark + race 测试，对比不同池大小与同步方案的 ns/op 和分配。

### 下一阶段

[Web 后端开发阶段](../ph09-web-backend/09-web-backend.md) ——net/http 深入（路由、中间件、模板）、REST API 设计、参数校验、JWT 认证与 Cookie/Session、CORS 与限流；本阶段的 httptest 测试、依赖注入与质量工具链，将直接用于验证 ph09 的每一个接口。
