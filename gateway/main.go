package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"
)

// Event 车辆事件
type Event struct {
	VehicleID string `json:"vehicle_id" binding:"required"`
	Timestamp int64  `json:"timestamp" binding:"required"`
	EventType string `json:"event_type" binding:"required,oneof=status fault trip battery"`
	GPS       GPS    `json:"gps" binding:"required"`
	Battery   Battery `json:"battery" binding:"required"`
	FaultCode *string `json:"fault_code"`
}

// GPS 定位信息
type GPS struct {
	Lat   float64 `json:"lat" binding:"required,min=-90,max=90"`
	Lng   float64 `json:"lng" binding:"required,min=-180,max=180"`
	Speed float64 `json:"speed" binding:"min=0"`
}

// Battery 电池信息
type Battery struct {
	Voltage float64 `json:"voltage" binding:"required,min=0,max=100"`
	Current float64 `json:"current" binding:"required"`
	Temp    float64 `json:"temp" binding:"required,min=-40,max=100"`
	SOC     int     `json:"soc" binding:"min=0,max=100"`
	SOH     int     `json:"soh" binding:"min=0,max=100"`
}

// ReportRequest 上报请求
type ReportRequest struct {
	Events    []Event `json:"events" binding:"required,min=1,max=1000"`
	Source    string  `json:"source" binding:"required"`
	Timestamp int64   `json:"timestamp" binding:"required"`
}

// Gateway 网关服务
type Gateway struct {
	kafkaWriter *kafka.Writer
	logger      *zap.Logger
}

// NewGateway 创建网关
func NewGateway(brokers []string, topic string, logger *zap.Logger) *Gateway {
	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.LeastBytes{},
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		RequiredAcks: kafka.RequireOne,
		Compression:  kafka.Snappy,
	}

	return &Gateway{
		kafkaWriter: writer,
		logger:      logger,
	}
}

// ReportHandler 处理数据上报
func (g *Gateway) ReportHandler(c *gin.Context) {
	var req ReportRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		g.logger.Warn("invalid request", zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"code":    400,
			"message": "invalid request: " + err.Error(),
		})
		return
	}

	// 转换为 Kafka 消息
	messages := make([]kafka.Message, 0, len(req.Events))
	for _, event := range req.Events {
		data, err := json.Marshal(event)
		if err != nil {
			g.logger.Error("marshal event failed", zap.Error(err), zap.String("vehicle_id", event.VehicleID))
			continue
		}
		messages = append(messages, kafka.Message{
			Key:   []byte(event.VehicleID),
			Value: data,
			Time:  time.Unix(event.Timestamp, 0),
		})
	}

	// 写入 Kafka
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	if err := g.kafkaWriter.WriteMessages(ctx, messages...); err != nil {
		g.logger.Error("write kafka failed", zap.Error(err), zap.Int("count", len(messages)))
		c.JSON(http.StatusInternalServerError, gin.H{
			"code":    500,
			"message": "failed to write to kafka",
		})
		return
	}

	g.logger.Info("events reported",
		zap.String("source", req.Source),
		zap.Int("count", len(req.Events)),
	)

	c.JSON(http.StatusOK, gin.H{
		"code":    0,
		"message": "success",
		"data": gin.H{
			"received": len(req.Events),
			"written":  len(messages),
		},
	})
}

// HealthHandler 健康检查
func (g *Gateway) HealthHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"time":   time.Now().Unix(),
	})
}

// Close 关闭资源
func (g *Gateway) Close() error {
	return g.kafkaWriter.Close()
}

func main() {
	// 初始化日志
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	// 从环境变量读取配置
	brokers := []string{getEnv("KAFKA_BROKERS", "localhost:9092")}
	topic := getEnv("KAFKA_TOPIC", "vehicle-events")
	port := getEnv("PORT", "8080")

	// 创建网关
	gateway := NewGateway(brokers, topic, logger)
	defer gateway.Close()

	// 设置路由
	r := gin.Default()
	r.Use(gin.Recovery())

	v1 := r.Group("/api/v1")
	{
		v1.POST("/report", gateway.ReportHandler)
		v1.GET("/health", gateway.HealthHandler)
	}

	// 启动服务
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: r,
	}

	go func() {
		logger.Info("gateway starting", zap.String("port", port), zap.String("topic", topic))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("server failed", zap.Error(err))
		}
	}()

	// 优雅关闭
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("shutting down gateway...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		logger.Error("shutdown failed", zap.Error(err))
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
