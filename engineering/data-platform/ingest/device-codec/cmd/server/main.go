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
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/Mosaic/ingest/device-codec/internal/gbt32960"
	"github.com/Mosslau/Mosaic/ingest/device-codec/internal/metrics"
	"github.com/Mosslau/Mosaic/ingest/device-contracts/vehicle"
)

// rawEnvelope 网关透传信封(映射文档 §7)
type rawEnvelope struct {
	VIN      string `json:"vin"`
	Ts       int64  `json:"ts"`
	ProtoVer string `json:"proto_ver"`
	Cmd      byte   `json:"cmd"`
	Payload  string `json:"payload"` // 原始帧 base64

	// IngestTsMS EMQX 接收该消息的毫秒时间戳(网关透传, 2026-09-18 补)。
	// 用于精确观测"EMQX 接收 → 解码完成"; 缺失/为 0 时跳过观测(兼容存量的旧信封)。
	IngestTsMS int64 `json:"ingest_ts_ms"`
}

// dlqMessage DLQ 记录(带原始字节 + 失败原因)
type dlqMessage struct {
	VIN      string `json:"vin,omitempty"`
	Stage    string `json:"stage"` // envelope / parse / vin_invalid / vin_mismatch / decode / validate / encode
	Reason   string `json:"reason"`
	RawB64   string `json:"raw_b64,omitempty"`
	UnitType int    `json:"unit_type,omitempty"`
	At       int64  `json:"at"`
}

// pendingReport 待写出的解析产物: 消息本体 + 指标标签。
// 标签随消息一起排队, 使得指标只在**写出成功**后累加(失败重试不虚增)。
type pendingReport struct {
	msg      kafka.Message
	typeName string
}

// pendingDLQ 待写出的 DLQ 记录(同上, 带 stage 标签)
type pendingDLQItem struct {
	msg   kafka.Message
	stage string
}

// 写出成功的累计计数(flushBatch 内累加; 主循环在 mu 下读取用于日志统计)
var (
	decodedTotal atomic.Int64
	dlqedTotal   atomic.Int64
)

// batchWriter 微批写出口(生产实现是 *kafka.Writer; 接口化是为了让 flush 的
// 失败路径可单测 —— 这段代码此前 0% 覆盖, 正是"写失败仍清空缓冲"能潜伏至今的原因)。
type batchWriter interface {
	WriteMessages(ctx context.Context, msgs ...kafka.Message) error
}

// offsetCommitter 位移提交口(生产实现是 *kafka.Reader)
type offsetCommitter interface {
	CommitMessages(ctx context.Context, msgs ...kafka.Message) error
}

// batchState 微批缓冲状态。抽出成结构体后 flush 成为纯状态迁移函数, 可脱离 Kafka 测试。
type batchState struct {
	pendingReports []pendingReport
	pendingDLQ     []pendingDLQItem
	pendingMsgs    []kafka.Message
	retryNotBefore time.Time
	failures       int64
}

// flushBatch 把缓冲写进 Kafka 并提交位移。
//
// 不变量(**数据不丢的根据**): 位移只在"本批全部产出与 DLQ 都已写出"之后才提交; 位移提交成功
// 才清空 pendingMsgs。任一环节失败 → 相关缓冲保留 + 有界退避, 位移不提交 → 崩溃/重启后
// Kafka 重读(at-least-once)。
//
// ⚠️ **ACK 语义收窄(2026-09-20)**: DLQ 落盘失败**不再拖住主链路**。
// 修复前 dlq 写失败也会让整批(含已成功写出的正常产出)滞留在缓冲、位移不推进 ——
// "一条脏数据的 DLQ topic 故障"会把正常数据的实时性一起拖垮(可用性退化; 数据不丢但链路停)。
// 现在的规则:
//   - 产出写失败 → 整批保留(与修复前一致);
//   - DLQ 写失败 → **只有 DLQ 缓冲保留**, 产出照常提交位移并放行, 已写出的 DLQ 条目出缓冲;
//   - 位移提交失败 → 整批保留(产出已写出, 重读会重复, 下游按 (vin,ts) 幂等吸收)。
//
// 返回值语义: true = 本批已推进(位移已提交); false = 本批有部分未推进。
// 便于测试与指标, 主循环不依赖它做控制流。
func flushBatch(ctx context.Context, st *batchState, pw, dw batchWriter, c offsetCommitter,
	now time.Time) bool {
	// 空判据必须同时看两条队列: DLQ 写失败时 pendingMsgs 已清空, 只有 DLQ 条目留下等重试。
	if len(st.pendingMsgs) == 0 && len(st.pendingDLQ) == 0 {
		return true
	}
	if now.Before(st.retryNotBefore) {
		return false // 退避中: 不重试也不清空
	}
	blocked := false

	// ① 产出: 失败即整批滞留(产出是主链路, 其故障本就该挡住位移推进)
	if len(st.pendingReports) > 0 {
		msgs := make([]kafka.Message, len(st.pendingReports))
		for i := range st.pendingReports {
			msgs[i] = st.pendingReports[i].msg
		}
		if err := pw.WriteMessages(ctx, msgs...); err != nil {
			blocked = true
			slog.Error("批量投递解析产物失败", "msgs", len(msgs), "err", err)
		} else {
			// 指标在**写出成功后**才累加, 否则 flush 失败会让对账公式虚高
			for i := range st.pendingReports {
				metrics.DecodedTotal.WithLabelValues(st.pendingReports[i].typeName).Add(1)
			}
			decodedTotal.Add(int64(len(msgs)))
		}
	}

	// ② DLQ: 写失败只保留 DLQ 条目, **不**置 blocked —— 主链路继续推进
	if len(st.pendingDLQ) > 0 {
		msgs := make([]kafka.Message, len(st.pendingDLQ))
		for i := range st.pendingDLQ {
			msgs[i] = st.pendingDLQ[i].msg
		}
		if err := dw.WriteMessages(ctx, msgs...); err != nil {
			// 只保留写失败的这批(逐条重试), 已写出的不再重复投递
			for i := range st.pendingDLQ {
				metrics.DLQFlushFailuresTotal.WithLabelValues(st.pendingDLQ[i].stage).Inc()
			}
			slog.Error("批量投递 DLQ 失败(主链路不受影响, DLQ 缓冲保留待重试)",
				"msgs", len(msgs), "err", err)
		} else {
			for i := range st.pendingDLQ {
				metrics.DLQTotal.WithLabelValues(st.pendingDLQ[i].stage).Add(1)
			}
			dlqedTotal.Add(int64(len(msgs)))
			st.pendingDLQ = st.pendingDLQ[:0]
		}
	}

	if !blocked {
		// 没有待提交的原始消息时跳过提交调用(kafka-go 对空消息集会报错, 且无意义):
		// 这是"只重试 DLQ"那一轮的情形 —— 原始消息早在上一轮就提交过位移了。
		if len(st.pendingMsgs) > 0 {
			if err := c.CommitMessages(ctx, st.pendingMsgs...); err != nil {
				// 位移提交失败: 产出已写出, 重试会造成重复(下游按 (vin,ts) 幂等吸收),
				// 但**不能**当作成功推进 —— 下一轮重新提交同一批。
				blocked = true
				slog.Error("提交位移失败", "err", err)
			}
		}
	}
	if !blocked {
		st.pendingReports = st.pendingReports[:0]
		st.pendingMsgs = st.pendingMsgs[:0]
		st.failures = 0
		st.retryNotBefore = time.Time{}
		return len(st.pendingDLQ) == 0
	}
	// 有界退避: 持续失败时不刷屏, 但缓冲保留 → 数据不丢
	st.failures++
	backoff := time.Duration(st.failures) * 500 * time.Millisecond
	if backoff > 10*time.Second {
		backoff = 10 * time.Second
	}
	st.retryNotBefore = now.Add(backoff)
	metrics.FlushFailuresTotal.Inc()
	slog.Error("flush 失败, 批次保留待重试(位移未提交, 数据不丢)",
		"backoff", backoff, "msgs", len(st.pendingMsgs), "dlqPending", len(st.pendingDLQ),
		"consecutiveFailures", st.failures)
	return false
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
	// 微批写到 Kafka。**必须显式设置 BatchTimeout**: kafka-go 的默认值是 1s,
	// 同步写的每一条都会等满这个窗口 —— 实测(同 broker 对照实验):
	//   仅 Hash+RequireOne(默认 BatchTimeout=1s) → 平均 1004 ms/批
	//   + BatchSize=200/BatchTimeout=50ms        → 平均   53 ms/批
	// 本服务已在上层做攒批(200 条/100ms), 这里的 BatchSize 只作为并发下的合并窗口;
	// 单条时靠 BatchTimeout 收口, 否则 flush 会把 100ms 的微批拖成秒级。
	parsedWriter := &kafka.Writer{
		Addr: kafka.TCP(cfg.brokers...), Topic: cfg.dstTopic,
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll, // 2026-09-18 由 RequireOne 升级; 单 broker 下语义等价但不再依赖单副本假设(见 gateway producer.go 注释)
		BatchSize:    200,
		BatchTimeout: 50 * time.Millisecond,
	}
	dlqWriter := &kafka.Writer{
		Addr: kafka.TCP(cfg.brokers...), Topic: cfg.dlqTopic,
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchSize:    200,
		BatchTimeout: 50 * time.Millisecond,
	}
	defer func() {
		reader.Close()
		parsedWriter.Close()
		dlqWriter.Close()
	}()

	// 可观测端点拆分(与网关同形态, 2026-09-18 审计整改):
	//   ① /metrics + /health → 专用端口(默认 18090), 需被容器内 Prometheus 抓取
	//   ② /debug/pprof → **只绑回环**(默认 127.0.0.1:18091); 能读进程内存(含凭据), 不得出本机
	srv := &http.Server{
		Addr:              ":" + strconv.Itoa(cfg.metricsPort),
		Handler:           metrics.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		slog.Info("codec 指标端点启动", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			// 端口被占等情况下 fail-fast: 否则"进程活着但指标不可见", 排障成本极高(README Q11)
			slog.Error("指标端点异常退出", "err", err)
			os.Exit(1)
		}
	}()
	pprofSrv := &http.Server{
		Addr:              cfg.pprofBind + ":" + strconv.Itoa(cfg.pprofPort),
		Handler:           metrics.PprofHandler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		slog.Info("codec pprof 端点启动(仅回环)", "addr", pprofSrv.Addr)
		if err := pprofSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("pprof 端点异常退出", "err", err)
		}
	}()

	slog.Info("device-codec 启动",
		"src", cfg.srcTopic, "dst", cfg.dstTopic, "dlq", cfg.dlqTopic, "group", cfg.groupID,
		"metricsAddr", srv.Addr)

	ctx, cancel := context.WithCancel(context.Background())
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-quit; slog.Info("收到退出信号, 优雅关闭..."); cancel() }()

	var consumed, decoded, dlqed int64
	var mu sync.Mutex
	// 微批缓冲状态(含待提交的原始消息)。抽出成 batchState 后, flush 逻辑可脱离 Kafka 单测。
	st := &batchState{}

	// flushCtx 是写 Kafka/提交位移用的 context: 正常运行时随主 ctx 取消,
	// 停机排空时临时替换为独立的 5s context(见主循环 context.Canceled 分支)。
	flushCtx := ctx
	pendingCount := func() int {
		mu.Lock()
		defer mu.Unlock()
		return len(st.pendingMsgs)
	}

	// flush 批量写出 + 提交位移(核心逻辑在 flushBatch, 见其不变量注释)。
	//
	// ⚠️ 空判据必须**同时**看 pendingMsgs 与 pendingDLQ(2026-09-20 ACK 收窄后):
	// DLQ 写失败时原始消息已提交位移、pendingMsgs 已清空, 只有 DLQ 条目留在缓冲里等重试 ——
	// 若这里只看 pendingMsgs, 那些 DLQ 条目就**再也没有机会被投出去**(单测当场抓到)。
	flush := func() {
		mu.Lock()
		defer mu.Unlock()
		if len(st.pendingMsgs) == 0 && len(st.pendingDLQ) == 0 {
			return
		}
		n := len(st.pendingMsgs)
		t0 := time.Now()
		flushBatch(flushCtx, st, parsedWriter, dlqWriter, reader, t0)
		d := time.Since(t0)
		decoded, dlqed = decodedTotal.Load(), dlqedTotal.Load()
		metrics.FlushDuration.Observe(d.Seconds())
		metrics.FlushBatchSize.Observe(float64(n))
		metrics.PendingMessages.Set(float64(len(st.pendingMsgs)))
		if d > 200*time.Millisecond {
			slog.Warn("flush 耗时过长", "total", d.String(), "msgs", n)
		}
	}

	// lag 采集: 每 5s 从 kafka-go ReaderStats 取消费者滞后(实时性的核心指标)
	go func() {
		t := time.NewTicker(5 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				metrics.Lag.Set(float64(reader.Stats().Lag))
			}
		}
	}()

	// 定时冲刷: 消息稀疏时微批不积压(攒批 200 条 / 100ms); 同时承担失败重试
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
				mu.Lock()
				d, l, c := decoded, dlqed, consumed
				mu.Unlock()
				slog.Info("处理统计", "consumed", c, "decoded", d, "dlq", l, "pending", pendingCount())
			}
		}
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				// 停机排空: 用独立的 context, 不复用已取消的 ctx ——
				// 否则 WriteMessages 会因 ctx.Done() 直接失败, 尾批语义不确定(可能写了却当作失败)。
				drainCtx, cancelDrain := context.WithTimeout(context.Background(), 5*time.Second)
				flushCtx = drainCtx
				flush()
				cancelDrain()
				break
			}
			slog.Error("拉取消息失败", "err", err)
			time.Sleep(time.Second)
			continue
		}
		mu.Lock()
		consumed++
		handleMessage(st, msg)
		decoded, dlqed = decodedTotal.Load(), dlqedTotal.Load()
		needFlush := shouldFlush(st)
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

// handleMessage 处理一条原始消息: 解析产出 + 指标 + 入缓冲(不触发 flush, 由调用方决定)。
// 必须持有 mu 调用。
//
// 注意 pendingDLQ 的语义(2026-09-20 ACK 收窄后): 它是**独立于 pendingMsgs 的重试队列** ——
// DLQ 写失败时条目会跨越若干轮 flush 存活(此时它对应的原始消息早已提交位移)。
// 因此它可能非空而 pendingMsgs 为空, 主循环的定时 flush 仍会推进它。
func handleMessage(st *batchState, msg kafka.Message) {
	metrics.ConsumedTotal.Inc()

	reports, dlqs := process(msg.Value)
	for i := range reports {
		encoded, err := reports[i].Encode()
		if err != nil {
			// 序列化失败不能静默丢: 该消息位移仍会推进, 必须留痕在 DLQ 里
			slog.Error("解析产物序列化失败, 转 DLQ", "vin", reports[i].VIN, "err", err)
			if b, mErr := json.Marshal(dlqMessage{
				VIN: reports[i].VIN, Stage: "encode",
				Reason: "解析产物序列化失败: " + err.Error(), At: time.Now().Unix(),
			}); mErr == nil {
				st.pendingDLQ = append(st.pendingDLQ, pendingDLQItem{
					msg:   kafka.Message{Key: []byte(reports[i].VIN), Value: b, Time: time.Now()},
					stage: "encode",
				})
			}
			continue
		}
		st.pendingReports = append(st.pendingReports, pendingReport{
			msg:      kafka.Message{Key: reports[i].Key(), Value: encoded, Time: time.Now()},
			typeName: string(reports[i].Type),
		})
	}
	for _, d := range dlqs {
		b, err := json.Marshal(d)
		if err != nil {
			continue
		}
		st.pendingDLQ = append(st.pendingDLQ, pendingDLQItem{
			msg:   kafka.Message{Key: []byte(d.VIN), Value: b, Time: time.Now()},
			stage: d.Stage,
		})
		slog.Warn("消息进 DLQ", "stage", d.Stage, "reason", d.Reason, "vin", d.VIN)
	}
	st.pendingMsgs = append(st.pendingMsgs, msg)
}

// shouldFlush 缓冲达到攒批阈值(200 条)即冲刷。
// 必须持有 mu 调用; 只做判断, 实际 flush 由调用方在**释放锁之后**执行(flush 自身要取锁)。
func shouldFlush(st *batchState) bool {
	return len(st.pendingMsgs) >= 200
}

// process 信封 → 帧解析 → VIN 身份校验 → v1 解码 → 契约校验。
// 无 I/O 副作用(仅累加上行延迟指标), 便于测试。
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

	// VIN 契约校验(2026-09-20 补齐对称性): 网关侧 JSON/MQTT 通道都会跑 vehicle.Validate(),
	// 其中 VIN 必须 5~32 字符; 而二进制通道的 VIN 来自**帧内字节**, 此前只判"与信封一致",
	// 于是一个 1 字节的 VIN(或空)能一路产出成合法 L2 数据 —— 两侧规则不对称。
	// 判定放在身份校验之前: 信封 VIN 与帧内 VIN 只要有一个不合契约就拒绝
	// (信封 VIN 受 EMQX ACL 约束, 这里同时兜住"ACL 配错导致 topic VIN 非法"的情形)。
	if reason := vehicle.VINContractReason(env.VIN); reason != "" {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "vin_invalid",
			Reason: "信封(topic) VIN " + reason, RawB64: env.Payload, At: now}}
	}
	if reason := vehicle.VINContractReason(f.VIN); reason != "" {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "vin_invalid",
			Reason: "帧内 VIN " + reason, RawB64: env.Payload, At: now}}
	}

	// VIN 身份锚点(与网关 JSON 通道的 ④.5 是同一道防线, 2026-09-18 补齐):
	// 信封 VIN 来自 MQTT topic(受 EMQX ACL 约束, 网关从 topic 取值后套信封),
	// 而帧内 VIN 由设备在载荷里自由填写 —— 网关按纪律**不解帧**, 无法校验, 只能在此拦。
	// 不校验则任何持合法凭证的设备都能在帧里填他人 VIN, 以他人身份写入平台数据
	// (污染车辆画像/触发误告警), 即 EMQX ACL 被绕过。
	// 放在 DecodeV1 **之前**: 恶意帧不必解码。
	// DLQ 的 VIN 取**信封 VIN**(= 已认证的发送者, 安全溯源看它), 两个 VIN 都写进 Reason。
	if f.VIN != env.VIN {
		return nil, []dlqMessage{{VIN: env.VIN, Stage: "vin_mismatch",
			Reason: fmt.Sprintf("帧内 VIN 与信封不一致(envelope=%s, frame=%s)", env.VIN, f.VIN),
			RawB64: env.Payload, At: now}}
	}

	reps, unitDLQs, err := gbt32960.DecodeV1(f)
	if err != nil {
		return nil, []dlqMessage{{VIN: f.VIN, Stage: "decode",
			Reason: err.Error(), RawB64: env.Payload, At: now}}
	}

	// 上行延迟 SLI(§9 的"两段之间的桥"): 观测点必须在"解码完成"这一刻, 故放在此。
	// 用网关透传的 EMQX 毫秒时间戳 —— 这是链路上唯一不受设备侧秒级 ts 限制的时间锚点。
	// 缺失(<=0, 旧信封)或负值(时钟不同步)时跳过: 噪声样本会污染分位数。
	if env.IngestTsMS > 0 {
		if d := time.Since(time.UnixMilli(env.IngestTsMS)); d >= 0 {
			metrics.IngestToDecode.Observe(d.Seconds())
		}
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
		// 端到端(粗): 设备数据时间 → 解码完成。只有 1 秒分辨率(契约 ts 是 Unix 秒),
		// 测的是"数据陈旧度"而非链路性能 —— 详见 metrics.DeviceToDecode 的注释。
		if d := time.Since(time.Unix(r.Ts, 0)); d >= 0 {
			metrics.DeviceToDecode.Observe(d.Seconds())
		}
		reports = append(reports, r)
	}
	return reports, dlqs
}

type codecConfig struct {
	brokers     []string
	metricsPort int
	pprofBind   string
	pprofPort   int
	srcTopic    string
	dstTopic    string
	dlqTopic    string
	groupID     string
}

func loadConfig() codecConfig {
	return codecConfig{
		brokers:     envList("KAFKA_BROKERS", []string{"localhost:19092"}),
		metricsPort: envInt("CODEC_METRICS_PORT", 18090),
		// pprof 只绑回环: 能读出进程内存(含凭据)
		pprofBind: envStr("CODEC_PPROF_BIND", "127.0.0.1"),
		pprofPort: envInt("CODEC_PPROF_PORT", 18091),
		srcTopic:  envStr("CODEC_SRC_TOPIC", "ov.raw.binary.v1"),
		dstTopic:  envStr("CODEC_DST_TOPIC", "vehicle-report-raw"),
		dlqTopic:  envStr("CODEC_DLQ_TOPIC", "ov.dlq.codec.v1"),
		groupID:   envStr("CODEC_GROUP", "device-codec-v1"),
	}
}

func envInt(key string, def int) int {
	if v, err := strconv.Atoi(os.Getenv(key)); err == nil && v > 0 {
		return v
	}
	return def
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
