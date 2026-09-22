// 来源：ph08-testing 主文档示例 5 —— benchmark + 覆盖率（benchmem 分析）
// 一句话说明：正确性测试 + 两个 benchmark，用包级变量防止结果被编译器优化消除。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...                                  # 正确性测试
//	go test -bench=. -benchmem -run=^$ -count=3 ./... # benchmark（重复 3 次看方差）
//
// 验证状态：已验证（go1.25.6）
package main

import "testing"

// 包级 sink：承接 benchmark 结果，防止 dead code elimination 把循环整体优化掉
var (
	sinkBytes  []byte
	sinkString string
)

func TestEncodePoint(t *testing.T) {
	data, err := EncodePoint(Point{X: 1.5, Y: 2.5})
	if err != nil {
		t.Fatalf("编码失败: %v", err)
	}
	if string(data) != `{"x":1.5,"y":2.5}` {
		t.Errorf("输出 = %s", data)
	}
}

func TestPointString(t *testing.T) {
	if got := PointString(Point{X: 1.5, Y: 2.5}); got != `{"x":1.5,"y":2.5}` {
		t.Errorf("输出 = %s", got)
	}
}

func BenchmarkEncodePoint(b *testing.B) {
	p := Point{X: 1.5, Y: 2.5}
	for i := 0; i < b.N; i++ {
		sinkBytes, _ = EncodePoint(p) // 赋值给包级变量，结果不可被优化消除
	}
}

func BenchmarkPointString(b *testing.B) {
	p := Point{X: 1.5, Y: 2.5}
	for i := 0; i < b.N; i++ {
		sinkString = PointString(p)
	}
}
