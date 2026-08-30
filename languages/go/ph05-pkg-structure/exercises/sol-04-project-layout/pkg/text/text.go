// 来源：exercises/README.md 练习 4 —— 建立标准项目结构参考实现
// 一句话说明：pkg/text 可复用公共库：分词与大小写不敏感包含判断，内部/入口均可引用。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd sol-04-project-layout && go run ./cmd/app search 关键词
// 验证状态：已验证（Go 1.22.2）
package text

import "strings"

// Words 把文本按空白拆分为单词
func Words(s string) []string {
	return strings.Fields(s)
}

// ContainsFold 大小写不敏感的子串判断
func ContainsFold(haystack, needle string) bool {
	return strings.Contains(strings.ToLower(haystack), strings.ToLower(needle))
}
