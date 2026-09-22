// 来源：ph17-architecture-layering project/internal/config
// 一句话说明：配置包。全部配置（监听地址/存储选型/文件路径）先解析进 Config 结构体
// 再下发各层，禁止在业务代码里散读 os.Getenv（12-factor：环境注入配置，主文档 3.5）。
// 读取优先级：命令行 flag > 环境变量 > 默认值。
// 注意：配置中心/灰度开关等发布期编排属 ph20 配置管理与发布策略阶段（roadmap 第 20 节，目录待建）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package config

import (
	"flag"
	"os"
)

// Config 应用配置。
type Config struct {
	Addr      string // 监听地址
	Store     string // mem | file
	StoreFile string // Store=file 时的数据文件路径
}

// Load 解析命令行与环境变量，返回完整配置。
// 配置不合法（如 Store 值未知）由调用方在启动期 fail-fast（见 cmd/deviceapi/main.go）。
func Load() Config {
	addr := flag.String("addr", envOr("ADDR", "127.0.0.1:18084"), "监听地址")
	kind := flag.String("store", envOr("STORE", "mem"), "存储实现: mem | file")
	path := flag.String("store-file", envOr("STORE_FILE", "/tmp/ph17-nodes.json"), "Store=file 时的数据文件路径")
	flag.Parse()
	return Config{
		Addr:      *addr,
		Store:     *kind,
		StoreFile: *path,
	}
}

// envOr 取环境变量，未设置时回退默认值。
func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
