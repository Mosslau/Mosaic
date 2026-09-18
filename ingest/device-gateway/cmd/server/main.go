// Command server 车端接入网关主程序。
// main 只做组装: 读配置 → 建 producer → 挂中间件链 → 起服务 → 优雅退出。
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/auth"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/config"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/handler"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/kafka"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/ratelimit"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	cfg, err := config.Load()
	if err != nil {
		slog.Error("配置加载失败", "err", err)
		os.Exit(1)
	}
	if cfg.DevMode {
		slog.Warn("⚠️  GATEWAY_DEV_MODE 已开启, dev-{VIN} 形态 token 可绕过白名单(但仍校验 VIN 一致性); 生产环境必须关闭!")
	}
	if cfg.WebhookToken == "dev-webhook-secret" {
		slog.Warn("⚠️  GATEWAY_WEBHOOK_TOKEN 使用默认值; 生产环境必须更换!")
	}

	producer := kafka.New(cfg.KafkaBrokers, cfg.KafkaTopic)
	binProducer := kafka.New(cfg.KafkaBrokers, cfg.KafkaBinTopic)

	// 处理链: metrics(最外) → auth → ratelimit → handler(最内)
	authMw := auth.New(cfg.DeviceBinding, cfg.DevMode)
	limiter := ratelimit.New(cfg.RatePerDevice, cfg.RateGlobal)
	reportHandler := handler.NewReportHandler(producer)

	mux := http.NewServeMux()
	// 方法级路由("POST /path")是 Go 1.22+ ServeMux 原生能力: 第 1 阶段不引第三方路由库。
	// metrics.Instrument 放最外层: 连被鉴权/限流拒绝的请求也要计数, 否则拒绝率不可见。
	// 通道一: 设备直连 HTTP(鉴权 + 双层限流)
	mux.Handle("POST /api/v1/vehicle/report",
		metrics.Instrument("/api/v1/vehicle/report",
			authMw.Wrap(limiter.Wrap(http.HandlerFunc(reportHandler.Report)))))
	// 通道二: EMQX webhook(全局令牌桶兜底 —— 单设备限流在 EMQX 协议层, webhook 密钥鉴权在 handler 内)。
	// 此前这两条路由完全没挂限流, 任意速率可直达 Kafka(2026-09-18 审计整改)。
	mqttHandler := handler.NewMQTTIngestHandler(producer, cfg.WebhookToken)
	mux.Handle("POST /api/v1/mqtt/ingest",
		metrics.Instrument("/api/v1/mqtt/ingest",
			limiter.GlobalWrap(http.HandlerFunc(mqttHandler.Ingest))))
	// 通道三: 二进制透传(EMQX webhook, 不解帧 → ov.raw.binary.v1, 映射文档 §7)
	binHandler := handler.NewBinIngestHandler(binProducer, cfg.WebhookToken)
	mux.Handle("POST /api/v1/bin/ingest",
		metrics.Instrument("/api/v1/bin/ingest",
			limiter.GlobalWrap(http.HandlerFunc(binHandler.IngestBin))))
	mux.HandleFunc("/health", handler.Health)

	// 可观测端点拆分(2026-09-18 审计整改):
	//   ① /metrics → 专用端口(默认 18081), 需被容器内 Prometheus 抓取, 故监听全网卡
	//   ② /debug/pprof → **只绑回环**(默认 127.0.0.1:18082); 能读进程内存(含密钥), 不得出本机
	// 业务端口(18080)不再暴露这两个端点。
	metricsMux := http.NewServeMux()
	metrics.RegisterMetrics(metricsMux)
	metricsSrv := &http.Server{
		Addr:              ":" + strconv.Itoa(cfg.MetricsPort),
		Handler:           metricsMux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	pprofMux := http.NewServeMux()
	metrics.RegisterPprof(pprofMux)
	pprofSrv := &http.Server{
		Addr:              cfg.PprofBind + ":" + strconv.Itoa(cfg.PprofPort),
		Handler:           pprofMux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		slog.Info("指标端点启动", "addr", metricsSrv.Addr, "path", "/metrics")
		if err := metricsSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("指标端点异常退出", "err", err)
		}
	}()
	go func() {
		slog.Info("pprof 端点启动(仅回环)", "addr", pprofSrv.Addr)
		if err := pprofSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("pprof 端点异常退出", "err", err)
		}
	}()

	srv := &http.Server{
		Addr:         ":" + strconv.Itoa(cfg.Port),
		Handler:      mux,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	go func() {
		slog.Info("车端接入网关启动",
			"port", cfg.Port, "topic", cfg.KafkaTopic, "brokers", cfg.KafkaBrokers,
			"ratePerDevice", cfg.RatePerDevice, "rateGlobal", cfg.RateGlobal,
			"metricsPort", cfg.MetricsPort, "pprof", cfg.PprofBind+":"+strconv.Itoa(cfg.PprofPort))
		if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			slog.Error("HTTP 服务异常退出", "err", err)
			os.Exit(1)
		}
	}()

	// 优雅退出顺序有讲究:
	//   ① srv.Shutdown 先停收新请求、等存量处理完(不再产生新消息)
	//   ② limiter.Close 停后台清理协程
	//   ③ producer.Close 最后关, 冲刷 Kafka 客户端未发送的缓冲批次(兜底不丢)
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	slog.Info("收到退出信号, 开始优雅关闭...")

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownGrace)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("HTTP 关闭异常", "err", err)
	}
	if err := metricsSrv.Shutdown(ctx); err != nil {
		slog.Error("指标端点关闭异常", "err", err)
	}
	if err := pprofSrv.Shutdown(ctx); err != nil {
		slog.Error("pprof 端点关闭异常", "err", err)
	}
	limiter.Close()
	if err := producer.Close(); err != nil {
		slog.Error("Kafka producer 关闭异常", "err", err)
	}
	if err := binProducer.Close(); err != nil {
		slog.Error("Kafka bin producer 关闭异常", "err", err)
	}
	slog.Info("网关已退出")
}
