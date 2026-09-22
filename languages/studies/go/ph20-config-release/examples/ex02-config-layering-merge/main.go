// 来源：ph20-config-release examples/ex02-config-layering-merge/main.go
// 一句话说明：跑完整的分层合并流水线——default → file(dev.json) → env → flag，
// 每步打印合并后的叶子与来源，直观看到"高优先级层覆盖低优先级层的同一键"（主文档 3.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -port 6060      验证状态：已验证
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
)

// 树上的叶子键（点路径小写）：
//   port / service.name / service.region / features.dark /
//   features.newtelemetry.percent / features.newtelemetry.enabled / retries（数组）。
// env 层大写变量名经「去前缀 → __ 变 . → lower」归一后与这些键匹配：
//   PH20EX02_FEATURES__NEWTELEMETRY__PERCENT=10 → features.newtelemetry.percent=10。

// defaultJSON 代码内嵌的默认层（等价于 struct 默认值，只是用 JSON 表达便于演示）。
const defaultJSON = `{
  "port": 8080,
  "service": {"name": "fleet-api", "region": ""},
  "features": {"dark": false, "newtelemetry": {"percent": 0, "enabled": false}},
  "retries": [1, 2, 3]
}`

// devConfigJSON 模拟「dev 环境的配置文件」。真实工程里 dev/test/prod 各一份
// （见 exercises/sol-01 与 project），文件内容由环境/编排系统挂载进来。
const devConfigJSON = `{
  "port": 9090,
  "features": {"dark": true},
  "retries": [5]
}`

func main() {
	// 0. 让默认层也走一遍 MergeInto（合入空 map），叶子来源统一记入 trace。
	trace := Trace{}
	merged := map[string]any{}
	dt, err := decodeJSONTree([]byte(defaultJSON))
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	MergeInto(merged, dt, SourceDefault, trace)
	fmt.Println("== 1. default 层 ==")
	fmt.Print(formatTree(merged, trace))

	// 1. file 层：写一份 dev.json 再读取，模拟外部挂载的配置文件。
	path := writeTempConfig([]byte(devConfigJSON))
	defer os.Remove(path)
	ft, err := decodeJSONTree(loadTemp(path))
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	MergeInto(merged, ft, SourceFile, trace)
	fmt.Println("== 2. +file(dev.json) 层 ==")
	fmt.Print(formatTree(merged, trace))

	// 2. env 层：先"注入"几个环境变量（真实场景由 docker/K8s/CI 注入），
	//    再按前缀收集并转成点路径更新树（双下划线 __ → 点，见 merge.go）。
	defer setEnv("PH20EX02_PORT", "7070")()
	defer setEnv("PH20EX02_FEATURES__NEWTELEMETRY__PERCENT", "10")()
	if err := applyEnv(merged, "PH20EX02_", trace); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	fmt.Println("== 3. +env 层 ==")
	fmt.Print(formatTree(merged, trace))

	// 3. flag 层：-port 6060 覆盖 env 的 7070；-features-dark 也按点路径落到树。
	fs := flag.NewFlagSet("server", flag.ContinueOnError)
	port := fs.String("port", "", "override listen port")
	featuresDark := fs.Bool("features-dark", false, "override features.dark")
	if err := fs.Parse(os.Args[1:]); err != nil {
		fmt.Println("解析 flag 失败：", err)
		os.Exit(1)
	}
	if *port != "" {
		if err := ApplyDotted(merged, "port", *port, SourceFlag, trace); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
	}
	if *featuresDark {
		if err := ApplyDotted(merged, "features.dark", "true", SourceFlag, trace); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
	}
	fmt.Println("== 4. +flag 层（最终） ==")
	fmt.Print(formatTree(merged, trace))

	fmt.Println("\n要点：port=6060 来自 flag、dark=true 来自 file、percent=10 来自 env、")
	fmt.Println("      name/region/enabled 保持 default——分层按「键」竞争，不是「整层赢者通吃」。")
}

// applyEnv 扫描进程环境，提取 prefix 开头变量，转成点路径键应用到配置树。
func applyEnv(root map[string]any, prefix string, trace Trace) error {
	for _, kv := range os.Environ() {
		k, v, ok := strings.Cut(kv, "=")
		if !ok || !strings.HasPrefix(k, prefix) {
			continue
		}
		dotted := strings.ToLower(strings.ReplaceAll(strings.TrimPrefix(k, prefix), "__", "."))
		if err := ApplyDotted(root, dotted, v, SourceEnv, trace); err != nil {
			return fmt.Errorf("env %s: %w", k, err)
		}
	}
	return nil
}

// writeTempConfig 写配置文件到临时目录并返回路径。
func writeTempConfig(data []byte) string {
	f, err := os.CreateTemp("", "ph20-ex02-*.json")
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

func loadTemp(path string) []byte {
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	return data
}

// setEnv 设置环境变量并返回清理函数（defer 时必须调用返回的 func，
// 否则 defer 绑定在 helper 内部会立即执行——见 main 里的用法）。
func setEnv(k, v string) func() {
	os.Setenv(k, v)
	return func() { os.Unsetenv(k) }
}
