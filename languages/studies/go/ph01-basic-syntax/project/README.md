# ph01 阶段项目：Todo CLI

## 需求

对应 Roadmap（`languages/studies/go/go.md`）「ph01 Go 基础语法阶段」推荐项目第一个。实现一个命令行待办事项工具：启动后循环读入命令，支持添加待办、列出全部待办、按编号完成（删除）待办、退出程序。数据用 slice 存储在内存中（本阶段不做持久化）。

## 功能清单

- [ ] `add <内容>`：添加一条待办，输出新待办的编号和内容
- [ ] `list`：按编号列出全部待办，空列表有提示
- [ ] `done <编号>`：完成（删除）指定编号的待办，编号无效时给出提示
- [ ] `quit` / `exit`：退出程序，返回码 0
- [ ] 空行忽略，未知命令给出帮助提示
- [ ] 支持 EOF（Ctrl+D）正常退出

## 验收标准

- `go build -o todo main.go` 编译通过（无警告）
- `add 学习 Go` 输出 `已添加 1: 学习 Go`
- `add 写报告` 后 `list` 输出两条，编号 1、2
- `done 1` 输出 `已完成: 学习 Go`，再 `list` 只剩原第 2 条（编号重新从 1 开始）
- `done 99`（编号越界）和 `done abc`（非数字）都提示用法，不崩溃
- 输入 `quit` 正常退出；Ctrl+D（EOF）也能正常退出
- 代码通过 `gofmt -l .` 检查（无输出）

## 扩展方向（可选）

- 待办加完成标记而不是直接删除（`done` 打勾，`list` 显示状态）
- 用 map 按分类管理待办 —— 巩固本阶段 map 知识点
- 持久化到文件（JSON）—— 属于 ph07 标准库阶段的 `encoding/json`、`os` 内容
- 命令解析改用 `flag` 包 —— 属于 ph07 标准库阶段

## 验证环境

已在本环境验证：Go 1.22.2 darwin/arm64（建议 Go 1.21+）。运行：`go run main.go`；编译：`go build -o todo main.go`。`go vet` 通过，`gofmt -l` 无差异；add/list/done/quit 及编号越界、非数字、EOF 路径均验证。
