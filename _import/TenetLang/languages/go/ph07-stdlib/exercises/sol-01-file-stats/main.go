// 来源：exercises/README.md 练习 1 参考实现 —— 文件统计工具（行数/单词数/字节数）
// 一句话说明：bufio.Scanner 逐行统计，strings.Fields 切单词，流式处理不占内存。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . <文件路径>
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
)

// count 从 r 中流式统计行数/单词数/字节数
func count(r io.Reader) (lines, words, bytes int, err error) {
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line := scanner.Text()
		lines++
		words += len(strings.Fields(line))
		bytes += len(line) + 1 // +1 补上被 Scanner 吃掉的换行符
	}
	if err := scanner.Err(); err != nil {
		return 0, 0, 0, fmt.Errorf("扫描失败: %w", err)
	}
	return lines, words, bytes, nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "用法: go run . <文件路径>")
		os.Exit(1)
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, "打开文件失败:", err)
		os.Exit(1)
	}
	defer f.Close()
	lines, words, bytes, err := count(f)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("行数: %d\n单词数: %d\n字节数: %d\n", lines, words, bytes)
}
