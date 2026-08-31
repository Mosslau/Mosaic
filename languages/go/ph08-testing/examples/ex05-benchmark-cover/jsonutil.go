// 来源：ph08-testing 主文档示例 5 —— benchmark + 覆盖率（benchmem 分析）
// 一句话说明：两种 JSON 编码实现（反射 vs 手写格式化），供基准对比。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go run .
//	go test -bench=. -benchmem -run=^$   # 只跑 benchmark
//	go test -cover ./...                 # 覆盖率
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"fmt"
)

// Point 待编码的坐标点
type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

// EncodePoint 用 encoding/json（反射，通用但慢）
func EncodePoint(p Point) ([]byte, error) { return json.Marshal(p) }

// PointString 手写格式化（快，但格式写死）
func PointString(p Point) string { return fmt.Sprintf(`{"x":%v,"y":%v}`, p.X, p.Y) }

func main() {
	data, err := EncodePoint(Point{X: 1.5, Y: 2.5})
	if err != nil {
		fmt.Println("编码失败:", err)
		return
	}
	fmt.Println(string(data))
}
