package kafka

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"sync"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
	"github.com/segmentio/kafka-go"
	"github.com/segmentio/kafka-go/protocol/metadata"
	"github.com/segmentio/kafka-go/protocol/produce"

	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/metrics"
)

// counterValue 读 Prometheus 计数器当前值(不引 testutil, 避免多拉一个测试依赖)
func counterValue(c prometheus.Counter) float64 {
	m := &dto.Metric{}
	if err := c.Write(m); err != nil {
		return -1
	}
	return m.GetCounter().GetValue()
}

// fakeBroker 假 broker: 实现 kafka.RoundTripper, 把 Produce 请求里的记录收集起来,
// 可注入传输级错误(网络不可达)或 broker 级错误(响应 Error)。
// 用它就能在没有真实 Kafka 的情况下验证投递内容/保序/失败计数(数据不丢链路的最后一环)。
type fakeBroker struct {
	mu         sync.Mutex
	records    []captured
	transport  error // 传输级错误: RoundTrip 直接返回 err
	brokerErr  error // broker 级错误: produce 响应分区错误码非 0
	partitions int   // 元数据里声明的分区数(≥2 才能验证 Hash 分布)
	done       chan struct{}
}

type captured struct {
	topic     string
	partition int
	key       string
	value     string
}

func newFakeBroker() *fakeBroker { return &fakeBroker{partitions: 8, done: make(chan struct{}, 64)} }

func (f *fakeBroker) RoundTrip(_ context.Context, _ net.Addr, req kafka.Request) (kafka.Response, error) {
	// writer 首次写入前会做元数据发现: 应答一个单 broker、N 分区的集群
	if mr, ok := req.(*metadata.Request); ok {
		partitions := make([]metadata.ResponsePartition, f.partitions)
		for i := range partitions {
			partitions[i] = metadata.ResponsePartition{PartitionIndex: int32(i), LeaderID: 1, ReplicaNodes: []int32{1}, IsrNodes: []int32{1}}
		}
		topics := make([]metadata.ResponseTopic, 0, len(mr.TopicNames))
		for _, name := range mr.TopicNames {
			topics = append(topics, metadata.ResponseTopic{Name: name, Partitions: partitions})
		}
		return &metadata.Response{
			Brokers:      []metadata.ResponseBroker{{NodeID: 1, Host: "127.0.0.1", Port: 19092}},
			ControllerID: 1,
			Topics:       topics,
		}, nil
	}

	pr, ok := req.(*produce.Request)
	if !ok {
		return nil, fmt.Errorf("假 broker 仅支持 Metadata/Produce, 收到 %T", req)
	}
	var batch []captured
	resp := &produce.Response{}
	for _, t := range pr.Topics {
		rt := produce.ResponseTopic{Topic: t.Topic}
		for _, pt := range t.Partitions {
			// 从 RecordSet 里取出原始记录(校验 key/value 原样透传)
			for {
				rec, err := pt.RecordSet.Records.ReadRecord()
				if errors.Is(err, io.EOF) {
					break
				}
				if err != nil {
					return nil, err
				}
				key, _ := io.ReadAll(rec.Key) // protocol.Bytes 是 io.ReadCloser
				val, _ := io.ReadAll(rec.Value)
				batch = append(batch, captured{
					topic: t.Topic, partition: int(pt.Partition),
					key: string(key), value: string(val),
				})
			}
			rp := produce.ResponsePartition{Partition: pt.Partition, ErrorCode: 0}
			if f.brokerErr != nil {
				rp.ErrorCode = 2 // CORRUPT_MESSAGE 之类, 非 0 即视为失败
			}
			rt.Partitions = append(rt.Partitions, rp)
		}
		resp.Topics = append(resp.Topics, rt)
	}

	f.mu.Lock()
	f.records = append(f.records, batch...)
	f.mu.Unlock()
	f.done <- struct{}{}

	if f.transport != nil {
		return nil, f.transport
	}
	return resp, nil
}

func (f *fakeBroker) snapshot() []captured {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]captured, len(f.records))
	copy(out, f.records)
	return out
}

// waitRecords 等到达 n 条记录(异步 producer, 需等待攒批/回调), 超时即失败。
func (f *fakeBroker) waitRecords(t *testing.T, n int, timeout time.Duration) []captured {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if got := f.snapshot(); len(got) >= n {
			return got
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("等 %d 条记录超时(实际 %d 条)", n, len(f.snapshot()))
	return nil
}

// waitMetric 等指标增量达到 want(Completion 回调异步触发)。
func waitMetric(t *testing.T, topic, result string, want float64, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if counterValue(metrics.KafkaWriteTotal.WithLabelValues(topic, result)) >= want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("指标 kafka_write_total{%s,%s} 未达到 %v", topic, result, want)
}

// TestProducer_WriteReport_DeliversKeyValueAndTopic 投递内容/主题/key 原样透传,
// 且同一 VIN 落同一分区(Hash(VIN) 保序契约)。
func TestProducer_WriteReport_DeliversKeyValueAndTopic(t *testing.T) {
	const topic = "test-deliver-topic"
	fb := newFakeBroker()
	p := newProducer([]string{"localhost:19092"}, topic, fb)
	defer p.Close()

	ctx := context.Background()
	for i, payload := range []string{`{"n":1}`, `{"n":2}`} {
		if err := p.WriteReport(ctx, []byte("OV20260001"), []byte(payload)); err != nil {
			t.Fatalf("第 %d 条投递失败: %v", i+1, err)
		}
	}
	// 另一辆车: 不应与上面同分区(哈希不同 key)
	if err := p.WriteReport(ctx, []byte("OV20260002"), []byte(`{"n":3}`)); err != nil {
		t.Fatalf("第三台车投递失败: %v", err)
	}

	got := fb.waitRecords(t, 3, 3*time.Second)
	for i, g := range got {
		if g.topic != topic {
			t.Errorf("第 %d 条 topic 应 %q, 实际 %q", i+1, topic, g.topic)
		}
	}
	// 同 key 保序且同分区
	var p1, p2 int
	seen := 0
	for _, g := range got {
		if g.key == "OV20260001" {
			switch seen {
			case 0:
				p1 = g.partition
				if g.value != `{"n":1}` {
					t.Errorf("首条 payload 应 {\"n\":1}, 实际 %s", g.value)
				}
			case 1:
				p2 = g.partition
				if g.value != `{"n":2}` {
					t.Errorf("次条 payload 应 {\"n\":2}, 实际 %s", g.value)
				}
			}
			seen++
		}
	}
	if seen != 2 {
		t.Fatalf("应收到该 VIN 的 2 条记录, 实际 %d", seen)
	}
	if p1 != p2 {
		t.Errorf("同一 VIN 必须落同一分区(保序契约), 实际 %d vs %d", p1, p2)
	}
}

// TestProducer_TransportError_ReturnsErrorAndCounts 传输层故障(如 broker 不可达) →
// **必须把错误返回给调用方**(handler 据此回 500 让设备重试), 并计入 error 且 ok 不涨。
// 这是 2026-09-18 审计整改的核心回归: Async 模式下此处曾返回 nil, 造成"已回 202 但未落盘"。
func TestProducer_TransportError_ReturnsErrorAndCounts(t *testing.T) {
	const topic = "test-transport-error-topic"
	fb := newFakeBroker()
	fb.transport = errors.New("connection refused")
	p := newProducer([]string{"localhost:19092"}, topic, fb)
	p.writer.MaxAttempts = 1 // 测试内降重试, 免退避拖慢用例(生产为 2)
	defer p.Close()

	beforeOK := counterValue(metrics.KafkaWriteTotal.WithLabelValues(topic, "ok"))
	beforeErr := counterValue(metrics.KafkaWriteTotal.WithLabelValues(topic, "error"))

	if err := p.WriteReport(context.Background(), []byte("OV20260001"), []byte(`{"n":1}`)); err == nil {
		t.Fatal("同步模式必须把投递失败返回给调用方, 实际返回 nil(会导致 202 假受理)")
	}
	waitMetric(t, topic, "error", beforeErr+1, 3*time.Second)
	if got := counterValue(metrics.KafkaWriteTotal.WithLabelValues(topic, "ok")); got != beforeOK {
		t.Errorf("传输失败不应计入 ok, 实际 ok=%v", got)
	}
}

// TestProducer_BrokerError_ReturnsErrorAndCounts broker 应答里带错误(如 topic 不存在/配额)
// → 同样必须返回 error 并计入 error。
func TestProducer_BrokerError_ReturnsErrorAndCounts(t *testing.T) {
	const topic = "test-broker-error-topic"
	fb := newFakeBroker()
	fb.brokerErr = errors.New("UNKNOWN_TOPIC_OR_PARTITION")
	p := newProducer([]string{"localhost:19092"}, topic, fb)
	p.writer.MaxAttempts = 1 // 测试内降重试, 免退避拖慢用例(生产为 2)
	defer p.Close()

	beforeErr := counterValue(metrics.KafkaWriteTotal.WithLabelValues(topic, "error"))
	if err := p.WriteReport(context.Background(), []byte("OV20260001"), []byte(`{"n":1}`)); err == nil {
		t.Fatal("broker 级错误必须返回给调用方, 实际返回 nil")
	}
	waitMetric(t, topic, "error", beforeErr+1, 5*time.Second)
}

// TestProducer_WriterConfig 固化 §3.5 的投递参数与"同步 + 有界重试 + RequireAll"不变量(配置漂移会被这条测试挡住)。
func TestProducer_WriterConfig(t *testing.T) {
	p := newProducer([]string{"localhost:19092"}, "vehicle-report-raw", nil)
	defer p.Close()

	w := p.writer
	if _, ok := w.Balancer.(*kafka.Hash); !ok {
		t.Errorf("Balancer 应为 Hash(VIN 保序), 实际 %T", w.Balancer)
	}
	if w.BatchSize != 200 || w.BatchTimeout != 50*time.Millisecond {
		t.Errorf("攒批应为 200 条/50ms, 实际 %d 条/%v", w.BatchSize, w.BatchTimeout)
	}
	if w.RequiredAcks != kafka.RequireAll {
		t.Errorf("RequiredAcks 应为 RequireAll(2026-09-18 由 RequireOne 升级), 实际 %v", w.RequiredAcks)
	}
	if w.Async {
		t.Error("必须为同步模式(async=false): Async 会让投递失败被吞掉, 破坏 §6 的 5xx 重试语义")
	}
	if w.MaxAttempts != 2 {
		t.Errorf("重试必须有界(MaxAttempts=2, 单次最坏约 4s < HTTP WriteTimeout 5s), 实际 %d", w.MaxAttempts)
	}
	if w.WriteTimeout != 2*time.Second {
		t.Errorf("WriteTimeout 应为 2s, 实际 %v", w.WriteTimeout)
	}
	if p.topic != "vehicle-report-raw" {
		t.Errorf("topic 应记录为 vehicle-report-raw, 实际 %q", p.topic)
	}
}
