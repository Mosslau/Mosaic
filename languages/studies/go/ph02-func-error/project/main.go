// project/main.go —— 配置加载器（演示入口）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run .
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	dir, err := os.MkdirTemp("", "ph02cfg")
	if err != nil {
		fmt.Println("创建临时目录失败:", err)
		os.Exit(1)
	}
	defer os.RemoveAll(dir) // 演示结束时清理临时目录

	// 1. 正常配置
	goodPath := filepath.Join(dir, "server.conf")
	if err := os.WriteFile(goodPath, []byte("# 服务配置\ntimeout=30\nmax_conn=100\n"), 0644); err != nil {
		fmt.Println("写入配置文件失败:", err)
		os.Exit(1)
	}
	cfg, err := LoadConfig(goodPath)
	if err != nil {
		fmt.Println("加载失败:", err)
	} else {
		fmt.Printf("加载成功: timeout=%ds, max_conn=%d\n", cfg.Timeout, cfg.MaxConn)
	}

	// 2. 文件不存在（errors.Is 判定 os.ErrNotExist）
	if _, err := LoadConfig(filepath.Join(dir, "missing.conf")); errors.Is(err, os.ErrNotExist) {
		fmt.Println("加载失败: 文件不存在 -", err)
	}

	// 3. 坏行（errors.Is 判定哨兵错误 ErrInvalidConfig）
	badPath := filepath.Join(dir, "bad.conf")
	if err := os.WriteFile(badPath, []byte("timeout=30\nnot-a-kv-line\n"), 0644); err != nil {
		fmt.Println("写入配置文件失败:", err)
		os.Exit(1)
	}
	if _, err := LoadConfig(badPath); errors.Is(err, ErrInvalidConfig) {
		fmt.Println("加载失败: 配置格式错误 -", err)
	}

	// 4. 未知键（errors.As 提取 *ConfigError 的结构化字段）
	unknownPath := filepath.Join(dir, "unknown.conf")
	if err := os.WriteFile(unknownPath, []byte("timeout=30\nfoo=bar\n"), 0644); err != nil {
		fmt.Println("写入配置文件失败:", err)
		os.Exit(1)
	}
	if _, err := LoadConfig(unknownPath); err != nil {
		var ce *ConfigError
		if errors.As(err, &ce) {
			fmt.Printf("加载失败: 第 %d 行 %q 出错（%s）\n", ce.Line, ce.Key, ce.Message)
		}
	}
}
