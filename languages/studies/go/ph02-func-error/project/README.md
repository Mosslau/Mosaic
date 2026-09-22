# ph02 阶段项目：配置加载器

对应 Roadmap「ph02 函数与错误处理阶段」推荐项目之一。实现一个配置加载器：读取配置文件、解析 `key=value`、校验必填项、返回带上下文的错误链。

## 需求

一个命令行演示程序 + 一个可复用的加载逻辑：

- 从指定路径读取配置文件（`key=value` 格式，支持 `#` 注释与空行）
- 解析为 `Config` 结构体（`timeout`、`max_conn` 两个整数字段）
- 校验必填项与取值范围（两者都必须为正整数）
- 每一层错误都携带上下文（路径、行号、键名），调用方能用 `errors.Is`/`errors.As` 区分错误类别

## 功能清单

- [ ] 读取配置文件，打开后立即 `defer f.Close()` 释放资源
- [ ] 解析 `key=value` 格式，跳过空行与 `#` 注释行
- [ ] 坏行返回自定义错误 `*ConfigError`（含行号、键名），经 `Unwrap` 链到哨兵错误 `ErrInvalidConfig`
- [ ] 未知键、非整数值分别给出明确错误
- [ ] 校验必填项：`timeout`、`max_conn` 必须为正整数
- [ ] 演示四种场景：正常加载、文件不存在（`errors.Is(err, os.ErrNotExist)`）、坏行（`errors.Is(err, ErrInvalidConfig)`）、未知键（`errors.As` 提取 `*ConfigError`）

## 验收标准

- `go run .` 依次输出四种场景的结果，正常场景打印 `timeout=30s, max_conn=100`
- 文件不存在时错误链能被 `errors.Is(err, os.ErrNotExist)` 判定
- 坏行时 `errors.Is(err, ErrInvalidConfig)` 为 true，且错误信息含行号
- 未知键时 `errors.As` 能提取 `*ConfigError`，拿到 `Line`、`Key` 字段
- 全程序不使用 `panic` 处理业务错误；文件句柄用 `defer` 保证关闭

## 扩展方向（可选）

- 支持从环境变量覆盖配置值 —— 属于 ph20 配置管理与发布策略阶段
- 为解析逻辑写表驱动单元测试 —— 属于测试阶段（见 Roadmap 后续阶段）
- 支持更多字段与默认值机制 —— 可结合 ph03 的 map 与 struct 深化

## 验证环境

Go 1.22.2（darwin/arm64），无外部依赖（仅标准库）。

```bash
# 1. 运行（project/ 目录下）
go run .

# 2. 静态检查
go vet ./...
gofmt -l .
```

已在本环境验证：`gofmt -l` 无差异、`go vet` 通过、`go run .` 输出符合预期。
