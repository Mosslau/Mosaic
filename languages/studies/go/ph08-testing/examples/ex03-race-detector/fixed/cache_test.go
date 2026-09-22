// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（修复版）
// 一句话说明：与 racy 包相同的并发压力，加锁后 -race 下干净通过。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v -race ./fixed
//
// 验证状态：已验证（go1.25.6）
package fixed

import (
	"fmt"
	"sync"
	"testing"
)

func TestCacheConcurrent(t *testing.T) {
	c := NewCache()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(2)
		go func(i int) { defer wg.Done(); c.Set(fmt.Sprint(i), "v") }(i) // 并发写不同的 key 也需加锁
		go func() { defer wg.Done(); _ = c.Get("k") }()
	}
	wg.Wait()
}

func TestCacheSetGet(t *testing.T) {
	c := NewCache()
	c.Set("k", "v")
	if got := c.Get("k"); got != "v" {
		t.Errorf("Get(k) = %q, 期望 %q", got, "v")
	}
}
