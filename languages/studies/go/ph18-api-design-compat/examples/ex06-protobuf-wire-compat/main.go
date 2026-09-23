// 来源：ph18-api-design-compat examples/ex06-protobuf-wire-compat/main.go
// 一句话说明：兼容实验的总览打印（主文档 3.8/4 章）。真正的断言见
// pbwire_test.go；这里把字节编码摆出来，让"加字段为什么兼容"看得见：
// v2 只是 v1 的字节尾巴上多了一段 (tag=4) 的数据，v1 reader 顺路跳过即可。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

func main() {
	b1 := encodeV1(v1Device{ID: "car-001", Name: "1号设备", Online: true})
	b2 := encodeV2(v2Device{ID: "car-001", Name: "1号设备", Online: true, Model: "M300"})

	fmt.Printf("v1 bytes (%d B): % x\n", len(b1), b1)
	fmt.Printf("v2 bytes (%d B): % x\n", len(b2), b2)
	fmt.Println()
	fmt.Printf("v1 reader 读 v2 数据 → %s\n", fmtV1(mustDecodeV1(b2)))
	fmt.Println("v1 reader 遇到字段号 4：按 wire type 跳过、继续向后读 → 旧客户端无损。")
	fmt.Println()
	fmt.Printf("v2 reader 读 v1 数据 → %+v\n", mustDecodeV2(b1))
	fmt.Println("v2 reader 读不到字段 4 → Model 落零值 \"\"（proto3 可选字段缺失的默认语义）。")
}

func mustDecodeV1(b []byte) v1Device {
	d, err := decodeV1(b)
	if err != nil {
		panic(err)
	}
	return d
}

func mustDecodeV2(b []byte) v2Device {
	d, err := decodeV2(b)
	if err != nil {
		panic(err)
	}
	return d
}
