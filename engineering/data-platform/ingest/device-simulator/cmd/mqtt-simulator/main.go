// Command mqtt-simulator MQTT 车端设备模拟器: N 个虚拟车辆通过 MQTT 长连接
// 向 EMQX 上报数据, 验证"设备 → EMQX → 规则引擎 → 网关 → Kafka"完整链路。
//
// 用法(1000 台设备, 每台 5 秒一条状态, 随机 1% 概率附带故障):
//
//	go run ./cmd/mqtt-simulator -broker tcp://localhost:1883 -devices 1000 -interval 5s -duration 60s
//
// 公网安全形态(8883 TLS + 一车一密, 设计文档 §8.2; 需先跑 deploy/emqx/seed-users.sh):
//
//	go run ./cmd/mqtt-simulator -tls -cacert ../../deploy/emqx/certs/ca.crt \
//	  -broker localhost:8883 -devices 100 -duration 60s
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"

	"github.com/Mosslau/Mosaic/ingest/device-simulator/internal/simconn"
	"github.com/Mosslau/Mosaic/ingest/device-simulator/internal/simdata"
)

var (
	broker   = flag.String("broker", "tcp://localhost:1883", "EMQX 地址")
	devices  = flag.Int("devices", 100, "模拟设备数")
	interval = flag.Duration("interval", 5*time.Second, "单设备上报间隔")
	duration = flag.Duration("duration", 60*time.Second, "压测总时长 (0=不限, Ctrl+C 停止)")
	faultPct = flag.Float64("fault-pct", 0.01, "每次上报附带故障消息的概率 [0,1]")
	useTLS   = flag.Bool("tls", false, "公网形态: TLS(8883) + 一车一密; clientid/username=VIN, 密码=pwPrefix+VIN")
	caCert   = flag.String("cacert", "../../deploy/emqx/certs/ca.crt", "TLS 校验用 CA 证书路径(自签 dev CA)")
	pwPrefix = flag.String("password-prefix", "pw-", "一车一密密码前缀(与 seed-users.sh 规则一致)")
)

var (
	connOK   atomic.Int64
	connFail atomic.Int64
	pubOK    atomic.Int64
	pubFail  atomic.Int64
)

func main() {
	flag.Parse()

	ctx, cancel := context.WithCancel(context.Background())
	if *duration > 0 {
		ctx, cancel = context.WithTimeout(ctx, *duration)
	}
	defer cancel()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sig; cancel() }()

	fmt.Printf("MQTT 模拟 %d 台设备 → %s, 间隔 %v\n", *devices, *broker, *interval)
	start := time.Now()

	// 分批启动(每批 256 台, 间隔 100ms 爬坡, 防惊群)
	step := (*devices + 255) / 256
	for batch := 0; batch < *devices; batch += step {
		end := min(batch+step, *devices)
		for i := batch; i < end; i++ {
			go runDevice(ctx, i)
		}
		time.Sleep(100 * time.Millisecond)
	}

	tick := time.NewTicker(5 * time.Second)
	defer tick.Stop()
	var lastPub int64
loop:
	for {
		select {
		case <-ctx.Done():
			break loop
		case <-tick.C:
			pub, fail := pubOK.Load(), pubFail.Load()
			fmt.Printf("[%6.0fs] 连接 ok=%d fail=%d | 发布 ok=%d fail=%d | 近5s qps=%.1f\n",
				time.Since(start).Seconds(), connOK.Load(), connFail.Load(),
				pub, fail, float64(pub+fail-lastPub)/5)
			lastPub = pub + fail
		}
	}

	elapsed := time.Since(start).Seconds()
	fmt.Printf("\n===== 压测结束 =====\n")
	fmt.Printf("时长: %.0fs, 连接成功: %d/%d, 发布成功: %d, 失败: %d, 平均 QPS: %.1f\n",
		elapsed, connOK.Load(), *devices, pubOK.Load(), pubFail.Load(), float64(pubOK.Load())/elapsed)
}

// runDevice 一台虚拟车辆: 建立 MQTT 长连接 → 周期发布 → ctx 取消时断连
func runDevice(ctx context.Context, id int) {
	vin := fmt.Sprintf("OV%08d", id)
	rng := rand.New(rand.NewPCG(uint64(id), uint64(id>>32)))

	client, err := simconn.New(simconn.Config{
		Broker:     *broker,
		TLS:        *useTLS,
		CACert:     *caCert,
		VIN:        vin,
		PwPrefix:   *pwPrefix,
		KeepAlive:  60 * time.Second,
		AutoReconn: true,
	})
	if err != nil {
		connFail.Add(1)
		fmt.Printf("构造 MQTT 客户端失败: %v\n", err)
		return
	}

	// 初次连接允许重试(真实设备行为): 千台开局是连接风暴, 单次 10s 超时就放弃
	// 会把"瞬时拥塞"误判成"大批永久离线"; 失败计数照记(反映风暴压力), 但继续重试。
	for {
		token := client.Connect()
		if token.WaitTimeout(10*time.Second) && token.Error() == nil {
			break
		}
		connFail.Add(1)
		select {
		case <-ctx.Done():
			return
		case <-time.After(2 * time.Second):
		}
	}
	connOK.Add(1)
	defer client.Disconnect(1000)

	soc := 60 + rng.Float64()*40
	// 随机相位防同刻齐发
	jitter := time.Duration(rng.Int64N(int64(*interval)))
	t := time.NewTimer(jitter)
	select {
	case <-ctx.Done():
		t.Stop()
		return
	case <-t.C:
	}

	ticker := time.NewTicker(*interval)
	defer ticker.Stop()
	for {
		// 周期状态: QoS 0(周期数据可丢, 网络开销最小)
		publish(client, "ov/"+vin+"/status", 0, simdata.BuildVehicleStatus(vin, rng, &soc))
		// 随机故障: QoS 1(事件数据必达, at-least-once → 下游幂等去重)
		if rng.Float64() < *faultPct {
			publish(client, "ov/"+vin+"/fault", 1, simdata.BuildFault(vin, rng))
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// publish 发布一条消息。
// WaitTimeout 只等"本地排队完成"而非 broker 端到端确认: 压测目标是链路吞吐,
// 逐条等往返 ACK 会把 QPS 压到延迟的倒数, 失去压测意义。
func publish(client mqtt.Client, topic string, qos byte, v any) {
	payload, err := json.Marshal(v)
	if err != nil {
		pubFail.Add(1)
		return
	}
	t := client.Publish(topic, qos, false, payload)
	// 异步发送, 只等本地排队(不等 broker ACK), 压测吞吐优先
	if t.WaitTimeout(5*time.Second) && t.Error() == nil {
		pubOK.Add(1)
	} else {
		pubFail.Add(1)
	}
}
