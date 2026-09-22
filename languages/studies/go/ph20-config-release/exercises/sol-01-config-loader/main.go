// 来源：ph20-config-release exercises/sol-01-config-loader/main.go
// 一句话说明：demo——用「多环境配置目录」演示 dev/test/prod 切换与字段来源表
// （主文档 3.2）。main 不做业务，只把 Load 的产物摊开给人看。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -profile dev -port 7777      验证状态：已验证
package main

import (
	"fmt"
	"os"
	"strings"
)

func main() {
	// 手工抽取 -profile（选择器），其余参数原样转给 Load 的 flag 层
	// （如 -port 7777 / -debug 继续覆盖）。flag 包遇到未定义 flag 会停止解析，
	// 不适合做两级 FlagSet 串接，这里用简单过滤。
	profile := "dev"
	var rest []string
	args := os.Args[1:]
	for i := 0; i < len(args); i++ {
		if args[i] == "-profile" && i+1 < len(args) {
			profile = args[i+1]
			i++
			continue
		}
		if v, ok := strings.CutPrefix(args[i], "-profile="); ok {
			profile = v
			continue
		}
		rest = append(rest, args[i])
	}

	cfg, src, err := Load(LoadOptions{
		Profile: profile,
		Dir:     "./configs",
		Args:    rest,
	})
	if err != nil {
		fmt.Printf("加载失败：%v\n", err)
		os.Exit(1)
	}
	fmt.Printf("== profile=%s 加载结果 ==\n", profile)
	fmt.Printf("   port=%d name=%q debug=%v region=%q\n", cfg.Port, cfg.Name, cfg.Debug, cfg.Region)
	fmt.Printf("   dbDsn=%s\n", maskDSN(cfg.DBDSN))
	fmt.Println("== 字段来源 ==")
	for _, f := range []string{"Port", "Name", "Debug", "Region", "DBDSN"} {
		fmt.Printf("   %-6s ← %s\n", f, src[f])
	}
}

// maskDSN 脱敏后再打印：DSN 可能带口令，日志只留形状。
func maskDSN(dsn string) string {
	if len(dsn) == 0 {
		return "(空)"
	}
	return "postgres://user:***@host:5432/app"
}
