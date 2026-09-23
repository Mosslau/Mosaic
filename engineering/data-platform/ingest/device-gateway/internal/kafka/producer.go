// Package kafka 封装 Kafka producer: 同步投递、按 VIN 哈希分区、有界重试。
package kafka

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/metrics"
)

// Producer 车端数据 Kafka 生产者
type Producer struct {
	writer *kafka.Writer
	topic  string
}

// New 创建 producer(生产路径: 真实 broker)。
func New(brokers []string, topic string) *Producer {
	return newProducer(brokers, topic, nil)
}

// newProducer 内部构造。
//
// 关键参数取舍(2026-09-18 审计整改: 由 Async 改为同步):
//   - Balancer=Hash: 按消息 key(VIN) 哈希分区 → 同一辆车的数据保序
//   - **同步投递(async=false)**: 这是"数据不丢"的前提。Async 模式下
//     kafka-go 的 WriteMessages 立即返回 nil, 投递失败只体现在回调计数里 →
//     网关已经回了 202/204 但消息从未落盘, 设备不会重试, 且 kafka-go 内部
//     batchQueue 无容量上限, 断连期内存无界增长(实测 VM OOM)。
//     同步模式让失败沿调用链返回, handler 据此回 500/5xx 让上游重试
//     (设计文档 §6 故障矩阵、示例集 §2④ 的既定语义)。
//   - 重试有界: MaxAttempts=2 + WriteTimeout=2s → 单次上报最坏阻塞约 4s
//     (小于 HTTP WriteTimeout 5s, 保证能返回 5xx 而不是被连接级超时吞掉);
//     更长的中断由"上游重试"兜底(EMQX 缓冲重试 / 设备端 AutoReconnect)。
//   - 攒批 200 条/50ms: 高并发下合并 RTT; 低并发时最坏多等 50ms。
//   - RequiredAcks=**RequireAll**(2026-09-18 升级, 原 RequireOne): 消除"broker 落盘前宕机
//     仍丢已确认消息"这条最后的可靠性缺口。注意单 broker 下 ISR={leader},
//     acks=all 与 acks=1 在**断电**场景等价 —— 真正的断电级持久性需要
//     replication-factor>=2 + min.insync.replicas>=2(多 broker), 见 deploy/README Q17。
//     本次升级的价值是**语义正确**: 代码不再依赖"只有一个副本"的部署假设,
//     将来加 broker/改副本数即可自动获得完整保证, 无需再动代码。
//
// transport 非 nil 时注入自定义 RoundTripper —— 供单测用假 broker 验证
// "投递内容/保序/失败计数"而无需真实 Kafka(见 producer_test.go)。
func newProducer(brokers []string, topic string, transport kafka.RoundTripper) *Producer {
	w := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		BatchSize:    200,
		BatchTimeout: 50 * time.Millisecond,
		RequiredAcks: kafka.RequireAll,
		Async:        false,
		MaxAttempts:  2,
		WriteTimeout: 2 * time.Second,
		Transport:    transport,
	}
	return &Producer{writer: w, topic: topic}
}

// WriteReport 同步写入一条消息。key 决定分区, payload 为已序列化 JSON。
// 返回 nil 表示**已收到 broker 确认**(RequiredAcks=RequireAll), 调用方可以安全回 202/204;
// 返回 error 表示未落盘, 调用方必须回 5xx 让上游重试(此时消息不保证不在途,
// 重试可能造成重复 —— 下游按 (vin, ts) 幂等去重, 契约设计已预留)。
func (p *Producer) WriteReport(ctx context.Context, key, payload []byte) error {
	err := p.writer.WriteMessages(ctx, kafka.Message{
		Key:   key,
		Value: payload,
		Time:  time.Now(),
	})
	if err != nil {
		// context 取消是调用方主动放弃(如客户端断开), 不计入 broker 故障
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			metrics.KafkaWriteTotal.WithLabelValues(p.topic, "canceled").Add(1)
			return err
		}
		metrics.KafkaWriteTotal.WithLabelValues(p.topic, "error").Add(1)
		slog.Error("kafka 写入失败", "topic", p.topic, "err", err)
		return err
	}
	metrics.KafkaWriteTotal.WithLabelValues(p.topic, "ok").Add(1)
	return nil
}

// Close 关闭 writer(会冲刷未发送的批次)
func (p *Producer) Close() error { return p.writer.Close() }
