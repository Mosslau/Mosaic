// Package kafka 封装 Kafka producer: 批量、异步、按 VIN 哈希分区。
package kafka

import (
	"context"
	"log/slog"
	"time"

	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
)

// Producer 车端数据 Kafka 生产者
type Producer struct {
	writer *kafka.Writer
	topic  string
}

// New 创建 producer。
// 关键参数取舍:
//   - Balancer=Hash: 按消息 key(VIN) 哈希分区 → 同一辆车的数据保序
//   - Async=true + Completion: 发送不阻塞 HTTP 链路, 失败在回调里计数
//   - BatchSize/BatchTimeout: 攒批 200 条或 50ms, 吞吐优先, 延迟代价 ≈50ms
//   - RequiredAcks=RequireOne: 第 1 阶段性能优先; 升级 All 可获得更强持久性
func New(brokers []string, topic string) *Producer {
	w := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		BatchSize:    200,
		BatchTimeout: 50 * time.Millisecond,
		RequiredAcks: kafka.RequireOne,
		Async:        true,
		Completion: func(msgs []kafka.Message, err error) {
			if err != nil {
				metrics.KafkaWriteTotal.WithLabelValues(topic, "error").Add(float64(len(msgs)))
				slog.Error("kafka 批量写入失败", "topic", topic, "msgs", len(msgs), "err", err)
				return
			}
			metrics.KafkaWriteTotal.WithLabelValues(topic, "ok").Add(float64(len(msgs)))
		},
	}
	return &Producer{writer: w, topic: topic}
}

// WriteReport 异步写入一条消息。key 决定分区, payload 为已序列化 JSON。
// 注意: Async 模式下此调用本身不保证投递成功, 失败只在回调计数。
func (p *Producer) WriteReport(ctx context.Context, key, payload []byte) error {
	return p.writer.WriteMessages(ctx, kafka.Message{
		Key:   key,
		Value: payload,
		Time:  time.Now(),
	})
}

// Close 关闭 writer(会冲刷未发送的批次)
func (p *Producer) Close() error { return p.writer.Close() }
