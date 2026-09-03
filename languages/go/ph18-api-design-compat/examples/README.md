# ph18 API 设计与兼容性示例

> 六个示例覆盖本阶段"可运行"的知识点主干：REST 资源与方法语义（ex01）→ 错误结构演进（ex02）→ 分页/过滤/排序稳定设计（ex03）→ 版本共存策略（ex04）→ OpenAPI 文档与实现同步（ex05）→ protobuf wire 兼容机制（ex06）。每个示例是自包含的独立 Go module，零第三方依赖，在 go1.25.6 上按文件头命令可复现（`go build ./...`、`go test ./...`、`go vet ./...`）。

| 示例 | 一句话说明 | 对应主文档 | 运行/测试命令（进入各自子目录） |
|------|-----------|-----------|------------------------------|
| ex01-rest-design | REST 资源设计：方法语义（GET 只读 / POST 创建 201+Location / PUT 全量替换 / PATCH 部分更新 / DELETE 幂等 204），规则集中在 HTTP 方法而不是 URL 动词 | 3.1 | `go run . -addr 127.0.0.1:18101`；`go test ./...`（7 个行为契约测试） |
| ex02-error-struct-evolution | 错误结构演进实验：`{code,message}` 演进到 v2 追加 requestId/details，老客户端解析新响应不炸、错误码注册表只增不删 | 3.4 | `go run .`（打印 v1/v2 序列化对比）；`go test ./...`（7 个演进纪律测试） |
| ex03-pagination-filter | 列表接口稳定设计：offset+limit 分页 envelope、过滤先于分页、排序白名单 + id 决胜、limit 默认/上限 | 3.5 | `go run . -addr 127.0.0.1:18103`；`go test ./...`（6 个稳定性测试） |
| ex04-versioning | URI 版本共存：v1/v2 共享领域数据与 service，DTO 按版本裁剪，v1 带 Deprecation/Sunset 通告头 | 3.3、3.6 | `go run . -addr 127.0.0.1:18104`；`go test ./...`（4 个版本契约测试） |
| ex05-openapi-sync | spec-first 契约同步：OpenAPI 文档是权威，契约测试让"实现比文档多字段/少路由"在 CI 立刻失败 | 3.7 | `go run . -addr 127.0.0.1:18105`；`go test ./...`（4 个契约测试） |
| ex06-protobuf-wire-compat | 手写 protobuf wire format：加字段老 reader 无损跳过、老数据缺字段落零值、改字段号造成无声错位 | 3.8、4 | `go run .`（打印字节编码对比）；`go test ./...`（5 个兼容实验测试） |

## 验证说明

- 全部示例 go.mod 为 `go 1.25.0`，与仓库语言版本档一致；`go build ./...`、`go test ./...`、`go vet ./...` 三条命令在每个子目录内执行。
- 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro）；GOCACHE/GOMODCACHE 重定位到 /tmp 临时目录（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）；零第三方依赖，可离线复现。
- **验证状态：已验证**——go1.25.6 本机实测：6 个模块 `go build ./... && go test ./... && go vet ./...` 全绿、gofmt 合规（`gofmt -l .` 无输出；详见各文件头）。
- 正确性自证设计：6 个示例全部带单元测试，单测通过即证明方法语义、演进纪律、分页稳定性、版本契约、文档同步、wire 兼容各自符合预期。
- HTTP 类示例（ex01/ex03/ex04/ex05）的 curl 冒烟方式：起服务后例如 `curl -s http://127.0.0.1:18101/v1/devices`；ex04 预置了两台设备（`curl -s http://127.0.0.1:18104/v1/devices/car-001` 与 `/v2/...` 对比 v1/v2 响应字段差异），ex03 数据集固定 103 台（`curl -s 'http://127.0.0.1:18103/v1/devices?status=offline&offset=20&limit=10'`）。
