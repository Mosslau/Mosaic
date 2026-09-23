// 来源：ph19-mq-event-driven project/internal/broker/topic.go
// 一句话说明：内存 fake broker（Kafka 语义的"离线可测"落地）——N 分区日志、
// key 稳定散列、高水位可查。它只提供 topic 原始能力，消费侧所需的
// 只读接口（NumPartitions/HighWater/Slice）在 consumer 包里按"使用方声明"
// 定义（主文档 3.1；golang-patterns：接口定义在使用方附近）。
// 真 Kafka 切换：本文件换成 kafka-go Writer/Reader（见 project/README 命令），
// consumer/process/store 全都不用改。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package broker

import (
	"hash/fnv"
	"sync"

	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
)

// partition 单分区有序日志。
type partition struct {
	mu      sync.Mutex
	records []model.Message
}

// append 追加并返回 offset。
func (p *partition) append(msg model.Message) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	msg.Offset = len(p.records) // 分区内 offset = 追加前长度，从 0 起
	p.records = append(p.records, msg)
	return msg.Offset
}

// lenAt 返回高水位。
func (p *partition) lenAt() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.records)
}

// sliceAt 返回 [from, 高水位) 的副本，并补齐 Partition 字段。
func (p *partition) sliceAt(partition, from int) []model.Message {
	p.mu.Lock()
	defer p.mu.Unlock()
	if from < 0 || from > len(p.records) {
		from = len(p.records)
	}
	recs := p.records[from:]
	out := make([]model.Message, 0, len(recs))
	for _, r := range recs {
		out = append(out, model.Message{Partition: partition, Offset: r.Offset, Key: r.Key, Payload: r.Payload})
	}
	return out
}

// Topic 一个 N 分区的 topic（本服务的数据源，对应 "fleet.telemetry.v1"）。
type Topic struct {
	partitions []*partition
}

// NewTopic 建 topic。
func NewTopic(partitions int) *Topic {
	t := &Topic{partitions: make([]*partition, partitions)}
	for i := range t.partitions {
		t.partitions[i] = &partition{}
	}
	return t
}

// Produce 按 key（deviceID）稳定散列写入，返回 (partition, offset)。
// 生产端调用，可并发；分区内 Append 有锁。
func (t *Topic) Produce(key string, payload []byte) (int, int) {
	p := PartitionForKey(key, t.NumPartitions())
	off := t.partitions[p].append(model.Message{Key: key, Payload: append([]byte(nil), payload...)})
	return p, off
}

// ProduceRaw 直接写一条 payload 到指定分区（测试/数据集注入用）。
func (t *Topic) ProduceRaw(p int, payload []byte) int {
	return t.partitions[p].append(model.Message{Payload: append([]byte(nil), payload...)})
}

// NumPartitions 分区数。
func (t *Topic) NumPartitions() int { return len(t.partitions) }

// HighWater 分区高水位：已写入条数（下一条 offset）。
func (t *Topic) HighWater(p int) int {
	return t.partitions[p].lenAt()
}

// Slice 返回分区 [from, 高水位) 的消息副本（消息带真实的 partition/offset）。
func (t *Topic) Slice(p, from int) []model.Message {
	return t.partitions[p].sliceAt(p, from)
}

// PartitionForKey FNV 散列取模：同 key 同分区（顺序性前提，主文档 3.4）。
func PartitionForKey(key string, n int) int {
	h := fnv.New32a()
	_, _ = h.Write([]byte(key))
	return int(h.Sum32() % uint32(n))
}
