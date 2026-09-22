// 来源：ph08-testing 练习 1 参考实现 —— 给业务函数写表格驱动测试
// 一句话说明：表 + 循环 + t.Run 子测试，wantErr 区分期望分支，浮点近似比较。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...        # 逐用例输出
//	go test -cover ./...    # 覆盖率（本实现为 100%）
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"math"
	"reflect"
	"testing"
)

func TestMedian(t *testing.T) {
	cases := []struct {
		name    string
		in      []float64
		want    float64
		wantErr bool
	}{
		{"空输入报错", nil, 0, true},
		{"单元素", []float64{42}, 42, false},
		{"奇数个", []float64{3, 1, 2}, 2, false},
		{"偶数个取平均", []float64{4, 1, 3, 2}, 2.5, false},
		{"含负数", []float64{-5, 0, 5}, 0, false},
		{"已排序输入", []float64{1, 2, 3, 4}, 2.5, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := Median(tc.in)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("期望报错, 实际得到 %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("意外错误: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 { // 浮点比较用近似判定
				t.Errorf("Median(%v) = %v, 期望 %v", tc.in, got, tc.want)
			}
		})
	}
}

// TestMedianNotMutateInput：验证函数不修改入参切片的元素顺序
func TestMedianNotMutateInput(t *testing.T) {
	in := []float64{3, 1, 2}
	orig := make([]float64, len(in))
	copy(orig, in)

	if _, err := Median(in); err != nil {
		t.Fatalf("意外错误: %v", err)
	}
	if !reflect.DeepEqual(in, orig) {
		t.Errorf("入参被修改: %v, 原为 %v", in, orig)
	}
}
