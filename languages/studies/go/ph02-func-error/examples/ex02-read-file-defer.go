// examples/ex02-read-file-defer.go —— 文件读取：defer 关闭文件、%w 逐层包装错误
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex02-read-file-defer.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"os"
)

func readConfig(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("open config %s: %w", path, err)
	}
	defer f.Close() // 打开成功后立即注册关闭，保证所有退出路径都释放文件

	buf := make([]byte, 1024)
	n, err := f.Read(buf)
	if err != nil {
		return "", fmt.Errorf("read config %s: %w", path, err)
	}
	return string(buf[:n]), nil
}

func main() {
	tmpFile := "/tmp/ph02_sample_config.txt"
	if err := os.WriteFile(tmpFile, []byte("timeout=30\nmax_conn=100"), 0644); err != nil {
		fmt.Println("创建临时文件失败:", err)
		return
	}
	if content, err := readConfig(tmpFile); err != nil {
		fmt.Println("读取失败:", err)
	} else {
		fmt.Println("配置内容:")
		fmt.Println(content)
	}
}
