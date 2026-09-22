// exercises/sol-02-read-file.go —— 练习 2 参考实现：文件读取错误处理
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-02-read-file.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
)

// readLines 按行读取文件；打开/读取失败时包装错误并携带路径上下文。
func readLines(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		// os.PathError 已含路径，包装时只补充操作语义，避免路径重复出现
		return nil, fmt.Errorf("read lines: %w", err)
	}
	defer f.Close() // 打开成功后立即注册关闭

	var lines []string
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		lines = append(lines, sc.Text())
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	return lines, nil
}

func main() {
	tmp := "/tmp/ph02_sol02_data.txt"
	if err := os.WriteFile(tmp, []byte("alpha\nbeta\ngamma\n"), 0644); err != nil {
		fmt.Println("创建临时文件失败:", err)
		return
	}

	lines, err := readLines(tmp)
	if err != nil {
		fmt.Println("读取失败:", err)
	} else {
		fmt.Println("文件内容:")
		for _, l := range lines {
			fmt.Println(" ", l)
		}
	}

	// 用 errors.Is 区分「文件不存在」与其他错误
	if _, err := readLines("/tmp/ph02_not_exist.txt"); errors.Is(err, os.ErrNotExist) {
		fmt.Println("文件不存在:", err)
	} else if err != nil {
		fmt.Println("其他错误:", err)
	}
}
