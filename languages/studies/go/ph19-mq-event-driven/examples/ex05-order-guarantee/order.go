// 来源：ph19-mq-event-driven examples/ex05-order-guarantee/order.go
// 一句话说明：顺序性判定的两个纯函数——顺序消费（partition 0..N 逐区读到底）
// 与按 key 抽子序列校验。消息队列只承诺"分区内有序"，跨分区交错由分区键负责
// 圈定：同 key 必须落在同一分区，顺序才有意义（主文档 3.4/4 章）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

// ConsumeSerially 按分区号从小到大、分区内从头到尾把日志读完。
// 这是"最朴素顺序消费"：任何 partition 内部严格有序，跨分区则按分区号拼接。
func ConsumeSerially(b *Broker) []Record {
	var out []Record
	for i := 0; i < b.NumPartitions(); i++ {
		out = append(out, b.PartitionAt(i).All()...)
	}
	return out
}

// PerKey 从消费序列里抽出某 key 的子序列（保持其相对顺序）。
func PerKey(all []Record, key string) []Record {
	var out []Record
	for _, r := range all {
		if r.Key == key {
			out = append(out, r)
		}
	}
	return out
}

// Values 仅取值的列表，便于断言"读到的就是按序写的"。
func Values(recs []Record) []string {
	out := make([]string, len(recs))
	for i, r := range recs {
		out[i] = r.Value
	}
	return out
}

// ValuesEqual 逐元素比较两个值切片（测试辅助，保证可读断言信息）。
func ValuesEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
