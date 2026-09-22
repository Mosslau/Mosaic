// 来源：ph08-testing 主文档示例 1 —— 表格驱动测试（业务函数 + 边界用例）
// 一句话说明：表 + 循环 + t.Run 子测试，正常/边界/错误路径全覆盖。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...                          # 全部测试
//	go test -run 'TestAvgSpeed/负速度报错' -v  # 按子测试名筛选
//	go test -cover ./...                      # 覆盖率
//
// 验证状态：已验证（go1.25.6）
package main

import "testing"

func TestAvgSpeed(t *testing.T) {
	cases := []struct {
		name    string
		in      []float64
		want    float64
		wantErr bool // 区分"期望错误"与"期望成功"两种断言分支
	}{
		{"空输入报错", nil, 0, true},
		{"单元素", []float64{60}, 60, false},
		{"正常", []float64{60, 80, 100}, 80, false},
		{"含零", []float64{0, 120}, 60, false},
		{"负速度报错", []float64{-1, 60}, 0, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := AvgSpeed(tc.in)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("期望报错, 实际得到 %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("意外错误: %v", err)
			}
			if got != tc.want {
				t.Errorf("AvgSpeed(%v) = %v, 期望 %v", tc.in, got, tc.want)
			}
		})
	}
}

func TestIsOverLimit(t *testing.T) {
	cases := []struct {
		speed, limit float64
		want         bool
	}{
		{120, 100, true},  // 超速
		{100, 100, false}, // 等于限速不超速（边界）
		{80, 100, false},
	}
	for _, tc := range cases {
		if got := IsOverLimit(tc.speed, tc.limit); got != tc.want {
			t.Errorf("IsOverLimit(%v, %v) = %v, 期望 %v", tc.speed, tc.limit, got, tc.want)
		}
	}
}
