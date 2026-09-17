// Command server device-codec 编解码服务(上行)。
//
// 职责(映射文档 §7 职责表): 消费 ov.raw.binary.v1 → 按 proto_ver 选解码器 →
// 输出 VehicleReport 到 vehicle-report-raw(与 JSON 通道汇合, 下游无感);
// 帧解析失败/未知版本/CRC 错 → DLQ(ov.dlq.codec.v1, 带原始字节+失败原因)。
//
// 不做: 鉴权/限流(网关职责)、业务判断; 无状态可横扩(消费者组天然并行)。
package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
	"github.com/Mosslau/OceanVerse/ingest/device-codec/internal/gbt32960"
)

// rawEnvelope 网关透传信封(映射文档 §7)
type rawEnvelope struct {
	VIN      string `json:"vin"`
	Ts       int64  `json:"ts"`
	ProtoVer string `json:"proto_ver"`
	Cmd      byte   `json:"cmd"`
	Payload  string `json:"payload"` // 原始帧 base64
}

// dlqMessage DLQ 记录(带原始字节 + 失败原因)
type dlqMessage struct {
	VIN      string `json:"vin,omitempty"`
	Stage    string `json:"stage"` // envelope / parse / decode / validate
	Reason   string `json:"reason"`
	RawB64   string `json:"raw_b64,omitempty"`
	UnitType int    `json:"unit_type,omitempty"`
	At       int64  `json:"at"`
}

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	cfg := loadConfig()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     cfg.brokers,
		Topic:       cfg.srcTopic,
		GroupID:     cfg.groupID,
		MinBytes:    1,
		MaxBytes:    10 << 20,
		StartOffset: kafka.FirstOffset,
	})
	parsedWriter := &kafka.Writer{
		Addr: kafka.TCP(cfg.brokers...), Topic: cfg.dstTopic,
		Balancer: &kafka.Hash{}, RequiredAcks: kafka.RequireOne,
	}
	dlqWriter := &kafka.Writer{
		Addr: kafka.TCP(cfg.brokers...), Topic: cfg.dlqTopic,
		Balancer: &kafka.Hash{}, RequiredAcks: kafka.RequireOne,
	}
	defer func() {
		reader.Close()
		parsedWriter.Close()
		dlqWriter.Close()
	}()

	slog.Info("device-codec 启动",
		"src", cfg.srcTopic, "dst", cfg.dstTopic, "dlq", cfg.dlqTopic, "group", cfg.groupID)

	ctx, cancel := context.WithCancel(context.Background())
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-quit; slog.Info("收到退出信号, 优雅关闭..."); cancel() }()

	var consumed, decoded, dlqed int64
	var mu sync.Mutex
	var pendingReports, pendingDLQ []kafka.Message
	var pendingMsgs []kafka.Message // 待提交的原始消息(与产出同批提交)

	// flush 批量写出 + 提交位移: 全部成功才提交, 崩溃/失败 → 重读(at-least-once, 下游幂等)
	flush := func() {
		mu.Lock()
		defer mu.Unlock()
		if len(pendingMsgs) == 0 {
			return
		}
		t0 := time.Now()
		var dWrite, dCommit time.Duration
		ok := true
		if len(pendingReports) > 0 {
			if err := parsedWriter.WriteMessages(ctx, pendingReports...); err != nil {
				ok = false
				slog.Error("批量投递解析产物失败", "msgs", len(pendingReports), "err", err)
			} else {
				decoded += int64(len(pendingReports))
			}
		}
		if len(pendingDLQ) > 0 {
			if err := dlqWriter.WriteMessages(ctx, pendingDLQ...); err != nil {
				ok = false
				slog.Error("批量投递 DLQ 失败", "msgs", len(pendingDLQ), "err", err)
			} else {
				dlqed += int64(len(pendingDLQ))
			}
		}
		dWrite = time.Since(t0)
		if ok {
			t1 := time.Now()
			if err := reader.CommitMessages(ctx, pendingMsgs...); err != nil {
				slog.Error("提交位移失败", "err", err)
			}
			dCommit = time.Since(t1)
		}
		if d := time.Since(t0); d > 200*time.Millisecond {
			slog.Warn("flush 耗时过长", "total", d, "write", dWrite, "commit", dCommit, "msgs", len(pendingMsgs))
		}
		pendingReports = pendingReports[:0]
		pendingDLQ = pendingDLQ[:0]
		pendingMsgs = pendingMsgs[:0]
	}

	// 定时冲刷: 消息稀疏时微批不积压(攒批 200 条 / 100ms)
	go func() {
		t := time.NewTicker(100 * time.Millisecond)
		stats := time.NewTicker(5 * time.Second)
		defer t.Stop()
		defer stats.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				flush()
			case <-stats.C:
				slog.Info("处理统计", "consumed", consumed, "decoded", decoded, "dlq", dlqed)
			}
		}
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				flush()
				break
			}
			slog.Error("拉取消息失败", "err", err)
			time.Sleep(time.Second)
			continue
		}
		consumed++

		reports, dlqs := process(msg.Value)
		mu.Lock()
		for i := range reports {
			payload, err := reports[i].Encode()
			if err != nil {
				slog.Error("解析产物序列化失败", "vin", reports[i].VIN, "err", err)
				continue
			}
			pendingReports = append(pendingReports, kafka.Message{Key: reports[i].Key(), Value: payload, Time: time.Now()})
		}
		for _, d := range dlqs {
			b, err := json.Marshal(d)
			if err != nil {
				continue
			}
			pendingDLQ = append(pendingDLQ, kafka.Message{Key: []byte(d.VIN), Value: b, Time: time.Now()})
			slog.Warn("消息进 DLQ", "stage", d.Stage, "reason", d.Reason, "vin", d.VIN)
		}
		pendingMsgs = append(pendingMsgs, msg)
		needFlush := len(pendingMsgs) >= 200
		mu.Unlock()
		if needFlush {
			flush()
		}
		if consumed%1000 == 0 {
			slog.Info("处理统计", "consumed", consumed, "decoded", decoded, "dlq", dlqed)
		}
	}
	slog.Info("device-codec 已退出", "consumed", consumed, "decoded", decoded, "dlq", dlqed)
}

// process 信封 → 帧解析 → v1 解码 → 契约校验。纯函数, 便于测试。
func process(raw []byte) (reports []vehicle.VehicleReport, dlqs []dlqMessage) {
	now := time.Now().Unix()

	var env rawEnvelope
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, []dlqMessage{{Stage: "envelope", Reason: "信封解析失败: " + err.Error(), At: now}}
	}
	// 版本纪律: 未知 proto_ver 不猜, 直接 DLQ(§7)
	if env.ProtoVer != "v1" {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "envelope",
			Reason: "未知 proto_ver: " + env.ProtoVer, RawB64: env.Payload, At: now}}
	}
	frame, err := base64.StdEncoding.DecodeString(env.Payload)
	if err != nil {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "envelope",
			Reason: "payload base64 解码失败", RawB64: env.Payload, At: now}}
	}
	f, err := gbt32960.ParseFrame(frame)
	if err != nil {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "parse",
			Reason: err.Error(), RawB64: env.Payload, At: now}}
	}
	reps, unitDLQs, err := gbt32960.DecodeV1(f)
	if err != nil {
		return nil, []dlqMessage{{VIN: f.VIN, Stage: "decode",
			Reason: err.Error(), RawB64: env.Payload, At: now}}
	}
	for _, d := range unitDLQs {
		dlqs = append(dlqs, dlqMessage{VIN: f.VIN, Stage: "decode",
			Reason: d.Reason, RawB64: env.Payload, UnitType: d.UnitType, At: now})
	}
	for _, r := range reps {
		if err := r.Validate(); err != nil {
			dlqs = append(dlqs, dlqMessage{VIN: r.VIN, Stage: "validate",
				Reason: err.Error(), RawB64: env.Payload, At: now})
			continue
		}
		reports = append(reports, r)
	}
	return reports, dlqs
}

type codecConfig struct {
	brokers  []string
	srcTopic string
	dstTopic string
	dlqTopic string
	groupID  string
}

func loadConfig() codecConfig {
	return codecConfig{
		brokers:  envList("KAFKA_BROKERS", []string{"localhost:19092"}),
		srcTopic: envStr("CODEC_SRC_TOPIC", "ov.raw.binary.v1"),
		dstTopic: envStr("CODEC_DST_TOPIC", "vehicle-report-raw"),
		dlqTopic: envStr("CODEC_DLQ_TOPIC", "ov.dlq.codec.v1"),
		groupID:  envStr("CODEC_GROUP", "device-codec-v1"),
	}
}

func envStr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envList(key string, def []string) []string {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	var out []string
	for _, p := range strings.Split(v, ",") {
		if s := strings.TrimSpace(p); s != "" {
			out = append(out, s)
		}
	}
	return out
}
