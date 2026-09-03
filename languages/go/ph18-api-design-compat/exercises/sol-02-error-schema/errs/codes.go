// 来源：ph18-api-design-compat exercises/sol-02-error-schema/errs/codes.go
// 一句话说明：错误码注册表（文档的唯一权威列表）。Codes() 是全量对外 code——
// OpenAPI 文档的 enum、客户端 SDK、监控字典都以它为基准。把"只增不删"做成
// 表本身 + 测试（errs_test.go 用各代历史集去钉），而不是一句口头承诺。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package errs

// CodeMeta 错误码的文档元信息（错误码文档表的每一行）。
type CodeMeta struct {
	Code    Code
	Since   string // 首次对外发布的版本
	Meaning string // 一句话语义 + 调用方可做的事
}

// registry 全量注册表，按首次发布顺序排列。删除一个 code = 老客户端把错误当未知
// 处理 + 历史告警规则失效，因此永远只追加、不改名。
var registry = []CodeMeta{
	{CodeValidation, "v1.0", "入参不合法；details 指明哪个字段、什么问题"},
	{CodeNotFound, "v1.0", "任务不存在（查询/操作的目标缺失）"},
	{CodeInternal, "v1.0", "服务内部错误（兜底；细节只进日志，可稍后重试）"},
	{CodeConflict, "v1.2", "状态机冲突：任务当前状态不允许该操作"},
	{CodeRateLimit, "v2.0", "触发限流，请按 Retry-After 头后退重试"},
}

// Codes 全量已发布错误码，按首次发布顺序输出（即文档表顺序）。
func Codes() []Code {
	out := make([]Code, 0, len(registry))
	for _, m := range registry {
		out = append(out, m.Code)
	}
	return out
}

// Doc 返回完整错误码文档表（每行的 meaning 就是写给调用方看的错误说明）。
func Doc() []CodeMeta {
	return append([]CodeMeta(nil), registry...)
}

// Meta 查询单个 code 的元信息。
func Meta(c Code) (CodeMeta, bool) {
	for _, m := range registry {
		if m.Code == c {
			return m, true
		}
	}
	return CodeMeta{}, false
}
