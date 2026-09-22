// 来源：ph20-config-release examples/ex01-env-file-flag/main.go
// 一句话说明：跑一个场景，把环境变量 / 配置文件 / 命令行 flag 三种来源
// 的读取逐个演示：JSON 样例 → flag 显式覆盖 → 环境变量 lookup 陷阱（主文档 3.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -port 9000 -name demo       验证状态：已验证
package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	// 1. 从文件读：把一份"样例 config.json"写进临时文件再读——模拟外部提供的配置文件。
	//    样例只写了 port 与 region：name/debug 保持默认值（文件缺键不清默认）。
	sample := []byte(`{"port": 9090, "region": "cn-north-1"}`)
	path := writeSampleConfig(sample)
	defer os.Remove(path)
	cfg := DefaultConfig()
	if err := cfg.FromFile(path); err != nil {
		fmt.Println("读取配置文件失败：", err)
		os.Exit(1)
	}
	fmt.Printf("== 1. 文件层加载后：%v\n", cfg)

	// 2. flag 覆盖：把当前值当默认注册。-name 未传则不覆盖（保持文件层结果）。
	fs := flag.NewFlagSet("server", flag.ContinueOnError)
	cfg.RegisterFlags(fs)
	if err := fs.Parse(os.Args[1:]); err != nil {
		fmt.Println("解析 flag 失败：", err)
		os.Exit(1)
	}
	fmt.Printf("== 2. flag 覆盖后：%v\n", cfg)

	// 3. 环境变量覆盖：演示 LookupEnv 的「未设置」与「设置为空串」是两回事。
	//    用真实环境变量演示前先把前缀键清干净，避免本机残留污染结果。
	clearEnv()
	if err := cfg.FromEnv(os.LookupEnv); err != nil {
		fmt.Println("读取环境变量失败：", err)
		os.Exit(1)
	}
	fmt.Printf("== 3. env 覆盖后：%v\n", cfg)

	// 4. 把 NAME 显式设成空串再读：空值也"覆盖"（name 变成空），区别于"未设置"。
	os.Setenv(envPrefix+"NAME", "")
	_ = cfg.FromEnv(os.LookupEnv)
	fmt.Printf("== 4. NAME 设为空串后：%v  ← 空值覆盖了文件层的 demo\n", cfg)

	// 5. 演示"未设置"的正确姿势：别用 os.Getenv 判空——Getenv 分不清"空"与"没设"。
	fmt.Println("\n== lookup 判定差异（LookupEnv 返回 (值, 是否存在)）==")
	for _, key := range []string{envPrefix + "NAME", envPrefix + "REGION"} {
		v, ok := os.LookupEnv(key)
		fmt.Printf("   %-16s → 值=%q, 已设置=%v\n", key, v, ok)
	}
}

// writeSampleConfig 把样例 JSON 写入临时文件，返回路径。
func writeSampleConfig(data []byte) string {
	f, err := os.CreateTemp("", "ph20-ex01-config-*.json")
	if err != nil {
		panic(err)
	}
	if _, err := f.Write(data); err != nil {
		panic(err)
	}
	if err := f.Close(); err != nil {
		panic(err)
	}
	return f.Name()
}

// clearEnv 清掉前缀下全部键，保证演示步骤从干净状态开始。
func clearEnv() {
	for _, k := range []string{envPrefix + "PORT", envPrefix + "NAME", envPrefix + "DEBUG", envPrefix + "REGION"} {
		os.Unsetenv(k)
	}
}
