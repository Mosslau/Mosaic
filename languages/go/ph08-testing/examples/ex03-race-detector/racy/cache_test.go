// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（racy 版）
// 故意出错示例：本测试用 WaitGroup 制造真实并发交错，-race 下必然报告 DATA RACE。
// 运行：
//
//	go test ./racy        # 不加 -race：自动跳过（避免并发 map 写崩溃）
//	go test -race ./racy  # 预期输出 WARNING: DATA RACE 并失败——这正是要演示的效果
//
// 验证状态：已验证（go1.25.6）：-race 下报告 DATA RACE，非 -race 下 SKIP。
package racy

import (
	"sync"
	"testing"
)

func TestCacheConcurrent(t *testing.T) {
	if !raceEnabled {
		t.Skip("本用例演示 DATA RACE，仅在 go test -race 下运行")
	}
	c := NewCache()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(2)
		go func() { defer wg.Done(); c.Set("k", "v") }() // 并发写 map
		go func() { defer wg.Done(); _ = c.Get("k") }()  // 并发读 map
	}
	wg.Wait()
}
