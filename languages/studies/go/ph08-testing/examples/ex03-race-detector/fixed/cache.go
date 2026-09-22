// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（修复版）
// 一句话说明：Mutex 保护共享状态，go test -race 下通过（ph06 并发编程阶段必会概念落地）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -race ./fixed
//
// 验证状态：已验证（go1.25.6）
package fixed

import "sync"

// Cache 修复版：Mutex 保护共享 map，建立 happens-before 关系
type Cache struct {
	mu   sync.Mutex
	data map[string]string
}

func NewCache() *Cache { return &Cache{data: make(map[string]string)} }

func (c *Cache) Set(k, v string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[k] = v
}

func (c *Cache) Get(k string) string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.data[k]
}
