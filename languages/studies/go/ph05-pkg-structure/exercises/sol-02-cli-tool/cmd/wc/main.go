// 来源：exercises/README.md 练习 2 —— 写 CLI 工具参考实现
// 一句话说明：cmd/wc 单词计数工具：-l/-w/-c 三个 flag，从文件参数或 stdin 读取。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd sol-02-cli-tool && go run ./cmd/wc -l -w -c <文件路径>
//	echo "hello world" | go run ./cmd/wc -w
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"tenetlang/go/ph05-pkg-structure/exercises/sol-02-cli-tool/internal/counter"
)

func main() {
	lines := flag.Bool("l", false, "统计行数")
	words := flag.Bool("w", false, "统计单词数")
	chars := flag.Bool("c", false, "统计字符数")
	flag.Parse()

	var input io.Reader = os.Stdin
	filename := ""
	if flag.NArg() > 0 {
		filename = flag.Arg(0)
		f, err := os.Open(filename)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		defer f.Close()
		input = f
	}

	st, err := counter.Count(input)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	// 未指定任何 flag 时默认全统计（对齐 Unix wc 行为）
	if !*lines && !*words && !*chars {
		*lines, *words, *chars = true, true, true
	}
	if *lines {
		fmt.Printf("%d ", st.Lines)
	}
	if *words {
		fmt.Printf("%d ", st.Words)
	}
	if *chars {
		fmt.Printf("%d ", st.Bytes)
	}
	fmt.Println(filename)
}
