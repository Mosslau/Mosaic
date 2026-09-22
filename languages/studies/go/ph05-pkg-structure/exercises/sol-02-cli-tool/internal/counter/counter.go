// 来源：exercises/README.md 练习 2 —— 写 CLI 工具参考实现
// 一句话说明：internal/counter 包：对任意 io.Reader 统计字节/单词/行数，显式返回 error。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd sol-02-cli-tool && go run ./cmd/wc -l -w -c <文件>
// 验证状态：已验证（Go 1.22.2）
package counter

import (
	"bufio"
	"fmt"
	"io"
)

// Stats 统计结果
type Stats struct {
	Bytes int
	Words int
	Lines int
}

// Count 统计 r 中的字节数、单词数、行数。
// 单词定义：以空白（空格/制表符/换行/回车）分隔的连续非空白片段。
func Count(r io.Reader) (Stats, error) {
	var st Stats
	br := bufio.NewReader(r)
	inWord := false
	for {
		b, err := br.ReadByte()
		if err == io.EOF {
			break
		}
		if err != nil {
			return st, fmt.Errorf("counter: read: %w", err)
		}
		st.Bytes++
		if b == '\n' {
			st.Lines++
		}
		space := b == ' ' || b == '\t' || b == '\n' || b == '\r'
		if space {
			inWord = false
		} else if !inWord {
			st.Words++
			inWord = true
		}
	}
	return st, nil
}
