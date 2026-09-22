// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（racy 版）
// 故意出错示例：本包的 Cache 无锁保护共享 map，专门用于演示 race detector。
// 请用 go test -race ./racy 观察 WARNING: DATA RACE 报告（此时测试"失败"是预期行为），
// 勿在生产代码中模仿本包写法；正确写法见同模块 fixed 包。
package racy

// Cache 故意无锁：并发读写 data map 会触发 DATA RACE / concurrent map writes
type Cache struct {
	data map[string]string
}

func NewCache() *Cache { return &Cache{data: make(map[string]string)} }

func (c *Cache) Set(k, v string)     { c.data[k] = v }
func (c *Cache) Get(k string) string { return c.data[k] }
