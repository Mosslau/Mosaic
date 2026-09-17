// Command bin-simulator 二进制车端模拟器: 按 GB/T 32960 帧框架(映射文档 v1.4)
// 造二进制帧, 以 MQTT 载荷方式发布(§8-⑦ MQTT 载荷先行), 供"模拟器 → EMQX →
// 网关透传 → ov.raw.binary.v1 → device-codec"链路联调与对拍。
//
// 与 cmd/mqtt-simulator 的关系: 同一批虚拟车辆、同一份 simdata 数据分布,
// 只是编码从 JSON 换成二进制帧; topic 走独立二进制家族 ov/{vin}/bin。
//
// 用法(100 台设备, 每台 10s 一帧——§3.1 频率基线建议值):
//
//	go run ./cmd/bin-simulator -broker tcp://localhost:1883 -devices 100 -interval 10s -duration 60s
//
// 公网安全形态(8883 TLS + 一车一密, 设计文档 §8.2; 需先跑 deploy/emqx/seed-users.sh):
//
//	go run ./cmd/bin-simulator -tls -cacert ../../deploy/emqx/certs/ca.crt \
//	  -broker localhost:8883 -devices 100 -duration 60s
package main

import (
	"context"
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"

	"github.com/Mosslau/OceanVerse/ingest/device-simulator/internal/simconn"
	"github.com/Mosslau/OceanVerse/ingest/device-simulator/internal/simdata"
	"github.com/Mosslau/OceanVerse/ingest/device-simulator/internal/simframe"
)

var (
	broker   = flag.String("broker", "tcp://localhost:1883", "EMQX 地址")
	devices  = flag.Int("devices", 100, "模拟设备数")
	interval = flag.Duration("interval", 10*time.Second, "单设备上报间隔(国标基线: 建议 10s, §3.1)")
	duration = flag.Duration("duration", 60*time.Second, "压测总时长 (0=不限, Ctrl+C 停止)")
	faultPct = flag.Float64("fault-pct", 0.01, "每次上报附带报警信息体(0x07)的概率 [0,1]")
	useTLS   = flag.Bool("tls", false, "公网形态: TLS(8883) + 一车一密; clientid/username=VIN, 密码=pwPrefix+VIN")
	caCert   = flag.String("cacert", "../../deploy/emqx/certs/ca.crt", "TLS 校验用 CA 证书路径(自签 dev CA)")
	pwPrefix = flag.String("password-prefix", "pw-", "一车一密密码前缀(与 seed-users.sh 规则一致)")
)

var (
	connOK   atomic.Int64
	connFail atomic.Int64
	pubOK    atomic.Int64
	pubFail  atomic.Int64
	frameN   atomic.Int64
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

	fmt.Printf("二进制模拟 %d 台设备 → %s, 间隔 %v (GB/T 32960 帧, MQTT 载荷)\n", *devices, *broker, *interval)
	start := time.Now()

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
			fmt.Printf("[%6.0fs] 连接 ok=%d fail=%d | 帧 %d | 发布 ok=%d fail=%d | 近5s qps=%.1f\n",
				time.Since(start).Seconds(), connOK.Load(), connFail.Load(),
				frameN.Load(), pub, fail, float64(pub+fail-lastPub)/5)
			lastPub = pub + fail
		}
	}

	elapsed := time.Since(start).Seconds()
	fmt.Printf("\n===== 压测结束 =====\n")
	fmt.Printf("时长: %.0fs, 连接成功: %d/%d, 帧: %d, 发布成功: %d, 失败: %d, 平均 QPS: %.1f\n",
		elapsed, connOK.Load(), *devices, frameN.Load(), pubOK.Load(), pubFail.Load(), float64(pubOK.Load())/elapsed)
}

// runDevice 一台虚拟车辆: MQTT 长连接 → 周期造帧发布 → ctx 取消时断连。
// 连接策略与 mqtt-simulator 完全一致(初次连接允许重试, 模拟真实设备)。
func runDevice(ctx context.Context, id int) {
	vin := fmt.Sprintf("OV%08d", id)
	rng := rand.New(rand.NewPCG(uint64(id), uint64(id>>32)))

	client, err := simconn.New(simconn.Config{
		Broker:     *broker,
		TLS:        *useTLS,
		CACert:     *caCert,
		VIN:        vin,
		PwPrefix:   *pwPrefix,
		KeepAlive:  60 * time.Second, // §8-⑨: MQTT 路线保活走 keepalive, 省略心跳帧
		AutoReconn: true,
	})
	if err != nil {
		connFail.Add(1)
		fmt.Printf("构造 MQTT 客户端失败: %v\n", err)
		return
	}

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
	topic := "ov/" + vin + "/bin"
	for {
		publish(client, topic, buildFrame(vin, rng, &soc, time.Now()))
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// buildFrame 造一帧 0x02 实时上报: 时间 + 0x01 整车 + 0x05 位置 + 0x06 极值
// + 0x08/0x09 电池明细, 随机附带 0x07 报警 / 0x80 充电 / 0x81 工况。
// 数值分布与 JSON 通道一致(共用 simdata.BuildVehicleStatus)。
func buildFrame(vin string, rng *rand.Rand, soc *float64, now time.Time) []byte {
	vs := simdata.BuildVehicleStatus(vin, rng, soc)
	d := vs.Data

	charging := *soc > 99.9 // simdata 换电满电视为充电完成窗口
	chargeStatus := byte(0x03)
	if charging {
		chargeStatus = 0x04
	}
	bodies := [][]byte{
		simframe.BodyVehicle(simframe.VehicleBody{
			VehicleStatus: 0x01,
			ChargeStatus:  chargeStatus,
			SpeedKmh:      *d.Speed,
			OdometerKm:    *d.Odometer,
			SOC:           *d.SOC,
		}),
		simframe.BodyPosition(*d.Lng, *d.Lat),
		simframe.BodyExtremes(*d.TempMax, *d.TempMax-2-rng.Float64()*3),
	}

	detail := simdata.BuildBatteryDetail(rng, charging)
	work := simdata.BuildWork(rng, *d.Speed)
	bodies = append(bodies,
		simframe.BodyBatteryVolt(simframe.BatteryVoltBody{
			Voltage:      *d.Voltage,
			Current:      *d.Current,
			CellVoltages: detail.CellVoltages,
		}),
		simframe.BodyBatteryTemp(detail.ProbeTemps),
		simframe.BodyWork(simframe.WorkBody{
			RideState:   work.RideState,
			RideMode:    work.RideMode,
			MotorRPM:    work.MotorRPM,
			MotorTorque: work.MotorTorque,
			MotorPower:  work.MotorPower,
			Throttle:    work.Throttle,
		}),
	)
	if charging {
		c := simdata.BuildCharging(rng)
		bodies = append(bodies, simframe.BodyCharging(simframe.ChargingBody{
			RemainMin: c.RemainMin, PowerKW: c.PowerKW, EnergyKWh: c.EnergyKWh,
			PileID: c.PileID, StationID: c.StationID, SlotNo: c.SlotNo,
		}))
	}
	if rng.Float64() < *faultPct {
		bodies = append(bodies, simframe.BodyAlarm(0x01, []uint32{0xE1001}))
	}

	frame := simframe.Frame(simframe.CmdRealtime, simframe.AckNone, vin, simframe.DataUnit(now, bodies...))
	frameN.Add(1)
	return frame
}

// publish 发布一帧(QoS 0: 周期数据可丢, §4.2 topic 契约同口径)。
// WaitTimeout 只等本地排队完成(压测吞吐优先, 同 mqtt-simulator 注释)。
func publish(client mqtt.Client, topic string, frame []byte) {
	t := client.Publish(topic, 0, false, frame)
	if t.WaitTimeout(5*time.Second) && t.Error() == nil {
		pubOK.Add(1)
	} else {
		pubFail.Add(1)
	}
}
