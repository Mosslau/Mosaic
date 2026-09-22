# 阶段项目：可替换存储层的 Todo 服务

对应 roadmap ph04 推荐项目第一个「可替换存储层的 Todo 服务」。用 Storage 接口解耦业务与存储：`TodoService` 只依赖接口，存储后端可在 `MemStorage`（内存）与 `FileStorage`（文件持久化）之间一条命令切换。

## 需求

实现一个 Todo 待办服务，核心是**可替换存储层**：

- 定义消费侧的 `Storage` 接口（`Save` / `Load` / `Delete`，显式返回 `error`，未命中返回 `ErrNotFound` 哨兵错误）
- 提供两个实现：`MemStorage`（进程内 map，零值可用）与 `FileStorage`（单个文本文件持久化，重开进程数据仍在）
- `TodoService` 只依赖接口，提供 `Add` / `Done` / `List` 三个业务操作
- 命令行参数 `-backend=mem|file` 切换后端；`-selfcheck` 对两个后端跑同一组断言

## 功能清单

| 功能 | 说明 |
|------|------|
| Storage 接口 | 消费侧定义，3 个方法均显式返回 error |
| ErrNotFound | Load 未命中的哨兵错误，调用方用 errors.Is 判断 |
| MemStorage | map 实现，零值可用，Delete 幂等 |
| FileStorage | 文本文件持久化，格式 `key\tvalue`，重建时加载 |
| TodoService | Add / Done / List，错误用 `%w` 携带上下文 |
| 后端切换 | `go run . -backend=mem` / `-backend=file -path=...` |
| 内置自检 | `-selfcheck` 用同一组断言验证两个后端行为一致 + 文件持久化 |

## 验收标准

- [ ] `gofmt -l .` 零差异、`go vet ./...` 零报告
- [ ] `go run . -backend=mem` 跑通 添加 → 列表 → 完成 → 列表 全流程，退出码 0
- [ ] `go run . -backend=file -path=/tmp/todo.txt` 全流程通过，且 `/tmp/todo.txt` 落盘内容可查看
- [ ] `go run . -selfcheck` 输出「自检通过」，退出码 0（两个后端行为一致、file 重载后数据仍在）
- [ ] 代码符合 ph04 接口要点：接口由使用方定义、显式 error、不用 panic 控制流程

## 扩展方向

- `FileStorage` 增加**转义**处理（当前 key/value 含换行会破坏文件格式）
- 用 `os.Rename` 原子写文件，避免写一半断电丢数据
- 加 `sync.Mutex` 支持并发读写（属于 ph06 并发阶段的内容）
- 存储后端扩展到 Redis / SQL（ph10 数据库阶段），`TodoService` 无需改动
- 把 `-selfcheck` 替换为 `go test` 表格驱动测试（ph08 测试阶段的内容）

## 验证环境

- Go 1.22.2（darwin/arm64），无第三方依赖
- 运行命令：
  - `go run . -backend=mem`
  - `go run . -backend=file -path=/tmp/todo.txt`
  - `go run . -selfcheck`
- 验证状态：已验证（Go 1.22.2）
