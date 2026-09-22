// 来源：07-stdlib.md 第 6 章示例 1 —— 文件统计工具（bufio 逐行统计单词/行数）
// 一句话说明：bufio.Scanner 逐行扫描 + strings.Fields 统计单词，流式处理不整载入内存。
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
	"log"
	"os"
	"strings"
)

func main() {
	if len(os.Args) < 2 {
		log.Fatal("用法: go run . <文件路径>")
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()
	lines, words := 0, 0
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		lines++
		words += len(strings.Fields(scanner.Text())) // 按空白切分统计单词
	}
	if err := scanner.Err(); err != nil {
		log.Fatal("扫描出错:", err)
	}
	fmt.Printf("行数: %d\n单词数: %d\n", lines, words)
}
