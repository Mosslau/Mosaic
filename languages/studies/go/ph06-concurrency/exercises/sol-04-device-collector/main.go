// 来源：06-concurrency.md 第 7 章「动手练习」练习 4 —— 数据采集并发处理
// 一句话说明：每设备一个 goroutine 并发上报采样，经 channel 汇聚到单一聚合 goroutine 去重统计，-race 验证。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd exercises/sol-04-device-collector && go run .
//	cd exercises/sol-04-device-collector && go run -race .
//
// 验证状态：已验证（Go 1.22.2，go run -race 无 DATA RACE）
package main

import (
	"fmt"
	"sync"
)

// reading 是一条采样：device 设备 ID，seq 序号，value 数值。
type reading struct {
	device string
	seq    int
	value  int
}

// sampleKey 是去重键：同一设备同一序号的采样只统计一次。
type sampleKey struct {
	device string
	seq    int
}

// stats 是单设备的聚合结果：count 有效样本数，sum 数值总和。
type stats struct {
	count int
	sum   int
}

// collect 模拟设备上报：每台设备上报 readings 条采样（value = seq*10），序号 3 的采样重复上报一次。
func collect(device string, readings int, out chan<- reading, wg *sync.WaitGroup) {
	defer wg.Done()
	for i := 1; i <= readings; i++ {
		out <- reading{device: device, seq: i, value: i * 10}
		if i == 3 {
			out <- reading{device: device, seq: i, value: i * 10} // 重复上报
		}
	}
}

// aggregate 是唯一的数据消费者：单 goroutine 消费 channel，天然无竞争，按 (device, seq) 去重后聚合。
func aggregate(in <-chan reading) map[string]stats {
	seen := make(map[sampleKey]bool)
	perDevice := make(map[string]stats)
	for r := range in {
		key := sampleKey{device: r.device, seq: r.seq}
		if seen[key] {
			continue // 去重：重复上报只计一次
		}
		seen[key] = true
		s := perDevice[r.device]
		s.count++
		s.sum += r.value
		perDevice[r.device] = s
	}
	return perDevice
}

func main() {
	const (
		devices  = 5
		readings = 10
	)
	in := make(chan reading, devices*readings*2) // 留足缓冲容纳重复上报

	var wg sync.WaitGroup
	for d := 1; d <= devices; d++ {
		wg.Add(1)
		go collect(fmt.Sprintf("D%02d", d), readings, in, &wg)
	}

	// 所有采集 goroutine 结束后关闭 channel，聚合者才能收尾
	wg.Wait()
	close(in)

	perDevice := aggregate(in)

	total := 0
	for d := 1; d <= devices; d++ {
		name := fmt.Sprintf("D%02d", d)
		s := perDevice[name]
		avg := 0
		if s.count > 0 {
			avg = s.sum / s.count
		}
		fmt.Printf("%s：有效样本 %d 条，总和 %d，平均 %d\n", name, s.count, s.sum, avg)
		total += s.count
	}
	fmt.Printf("合计有效样本 %d 条（期望 %d）\n", total, devices*readings)
}
