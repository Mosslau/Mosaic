# ph03 Slice、Map、Struct 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：Go 1.22.2（darwin/arm64），无外部依赖。

| 文件 | 说明 | 运行 |
|------|------|------|
| ex01-slice-grow.go | Slice 扩容实验：观察 append 过程中 len/cap 的变化 | `go run ex01-slice-grow.go` |
| ex02-subslices-share.go | 子切片共享底层数组，扩容后解除共享 | `go run ex02-subslices-share.go` |
| ex03-map-ops.go | Map 安全操作（ok 模式）、删除与遍历 | `go run ex03-map-ops.go` |
| ex04-struct-embed.go | Struct 组合嵌入——设备实体（字段提升） | `go run ex04-struct-embed.go` |
| ex05-device-status.go | 设备状态管理（Map + Struct，按 ID 排序遍历） | `go run ex05-device-status.go` |

每个文件都是独立的 package main，单独 `go run` 即可（同一目录下多个 main 函数不能一起 `go build ./...`，请逐文件运行）。

全部已在本环境验证：`gofmt -l` 无差异、`go vet` 通过、`go run` 输出符合预期（Go 1.22.2）。
