# exercises —— 包管理与工程结构阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），建议按 1 → 2 → 3 → 4 顺序完成。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-split-program && go run ./cmd/student-mgr demo`）。请勿在 exercises/ 根目录执行 `go build ./...`——根目录没有 go.mod。

## 练习 1：拆分单文件程序（★★）

**目标**：把下面的单文件学生管理程序拆分为 `cmd/student-mgr` + `internal/student` 标准布局，并补齐显式 `error` 返回。

**起点程序**（单文件，先 `go mod init` 再动手）：

```go
package main

import "fmt"

type Student struct {
	ID   int
	Name string
	Age  int
}

type Manager struct {
	students []Student
	nextID   int
}

func (m *Manager) Add(name string, age int) int {
	id := m.nextID
	m.students = append(m.students, Student{ID: id, Name: name, Age: age})
	m.nextID++
	return id
}

func (m *Manager) Delete(id int) bool {
	for i, s := range m.students {
		if s.ID == id {
			m.students = append(m.students[:i], m.students[i+1:]...)
			return true
		}
	}
	return false
}

func (m *Manager) List() []Student {
	out := make([]Student, len(m.students))
	copy(out, m.students)
	return out
}

func main() {
	m := &Manager{nextID: 1}
	m.Add("Alice", 20)
	m.Add("Bob", 22)
	fmt.Println(m.List())
	m.Delete(1)
	fmt.Println(m.List())
}
```

**要求**：
- `internal/student` 包导出 `Student`、`Manager`，方法返回显式 `error`（空姓名/非法年龄拒绝，删除未找到返回哨兵错误 `ErrNotFound`）
- `cmd/student-mgr/main.go` 只负责参数解析与打印，调用包前用 `errors.Is` 判断 `ErrNotFound`
- 模块路径自定（如 `tenetlang/go/ph05-pkg-structure/exercises/sol-01-split-program`）

**验收**：`go build ./...` 通过；`go vet ./...` 零报告；`go run ./cmd/student-mgr demo` 输出添加/列表/删除全流程，非法输入被拒绝并打印原因。

## 练习 2：写 CLI 工具（★★）

**目标**：用 `flag` 包 + `internal` 包写一个单词计数工具 `wc`，统计行数/单词数/字符数。

**要求**：
- 三个布尔 flag：`-l`（行数）、`-w`（单词数）、`-c`（字符数）；全部未指定时默认三者全统计（对齐 Unix `wc` 行为）
- `internal/counter` 包提供 `Count(r io.Reader) (Stats, error)`，接收接口返回结构体
- 支持从文件参数读取；无参数时从 stdin 读取；文件打开失败、读取失败均显式返回错误
- `cmd/wc/main.go` 用 `flag.Parse()` 解析，错误打印到 stderr 并以非零码退出

**验收**：对一个含多行文本的文件，`go run ./cmd/wc -l -w -c <文件>` 输出的行数/单词数/字符数与 `wc <文件>` 一致；`echo "hello world" | go run ./cmd/wc -w` 输出 `2`。

## 练习 3：写配置加载模块（★★★）

**目标**：写 `internal/config` 包：从 JSON 文件读配置 + 环境变量覆盖 + 集中校验（fail fast）。

**要求**：
- `Config` 结构体带 `json` tag（如 `port`、`data_dir`、`log_level`）
- `Load(path string) (*Config, error)`：读文件 → `json.Unmarshal` → 环境变量覆盖 → 集中校验
- 环境变量覆盖约定：`APP_PORT` / `APP_DATA_DIR` / `APP_LOG_LEVEL`（`APP_PORT` 解析失败要返回错误）
- 校验规则：`port` 必须在 1~65535，`data_dir` 非空；所有错误用 `%w` 包装携带上下文
- `cmd/server/main.go` 用 `flag` 指定 `-config` 路径，加载成功后打印配置；库代码不打印日志

**验收**：`go run ./cmd/server -config config.example.json` 打印正确配置；`APP_PORT=9090 go run ...` 时端口变为 9090；把配置文件 port 改成 0 后运行，程序以非零码退出并提示 invalid port。

## 练习 4：建立标准项目结构（★★★）

**目标**：综合练习——建立完整的 `cmd/` + `internal/` + `pkg/` 三层标准项目，业务自选（如任务管理、通讯录、设备状态管理）。

**要求**：
- `cmd/<app>/main.go`：程序入口，只做参数解析与输出
- `internal/<biz>/`：业务包，显式返回 `error`，不依赖入口
- `pkg/<lib>/`：至少一个可复用公共库包，且被 `internal/` 包引用（体现"pkg 可被模块内任意包引用"）
- 用 `go mod init` + `go mod tidy` 走完整模块流程

**验收**：`go build ./...`、`go vet ./...` 通过；命令至少支持 2 个以上子命令并能完整跑通；用一句话说明你的 `pkg/` 与 `internal/` 的边界划分理由。

---

四个练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
