// 来源：ph08-testing 主文档示例 1 —— 表格驱动测试（业务函数 + 边界用例）
// 一句话说明：设备平均速度与超速判断，作为被测业务函数。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go run .
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import "fmt"

// AvgSpeed 计算平均速度；空输入或负速度返回错误
func AvgSpeed(speeds []float64) (float64, error) {
	if len(speeds) == 0 {
		return 0, fmt.Errorf("speeds 不能为空")
	}
	var total float64
	for _, s := range speeds {
		if s < 0 {
			return 0, fmt.Errorf("速度不能为负: %v", s)
		}
		total += s
	}
	return total / float64(len(speeds)), nil
}

// IsOverLimit 是否超速（等于限速不算超速）
func IsOverLimit(speed, limit float64) bool { return speed > limit }

func main() {
	avg, err := AvgSpeed([]float64{60, 80})
	if err != nil {
		fmt.Println("错误:", err)
		return
	}
	fmt.Println("平均速度:", avg)
}
