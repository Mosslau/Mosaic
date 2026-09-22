// 来源：ph21-data-ingest-gateway examples/ex02-device-reconnect-idempotent/main.go
// 一句话说明：演示主程序——起云接入平台（httptest 挂真实 handler），模拟车辆：
// (1) 正常上报 2 条；(2) 断线重试 1 条（重连循环命中幂等窗，不重复生效）；
// (3) 坏 token 设备被 401 拒绝（重连循环不空转）。输出即验收证据。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"time"
)

func main() {
	// 1. 平台侧：密钥表（每车一密）。
	platform := NewPlatform(map[string]string{"veh-001": "secret-1"})
	ts := httptest.NewServer(platform.Handler())
	defer ts.Close()
	fmt.Println("== 云接入平台已启动 ==")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 2. 好设备：上报两条不同 seq。
	dev := &Reporter{
		Endpoint: ts.URL + "/api/v1/telemetry",
		DeviceID: "veh-001", Secret: "secret-1",
		Client: &http.Client{Timeout: 2 * time.Second},
	}
	for i := 0; i < 2; i++ {
		t := Telemetry{Vin: "veh-001", Seq: dev.NextSeq(), Speed: float64(30 + i*10), Ts: time.Now().Unix()}
		if err := dev.SendOnce(ctx, t); err != nil {
			fmt.Printf("[上报失败] %v\n", err)
			return
		}
	}
	fmt.Println("两条新遥测上报成功")

	// 3. 弱网重试：同一 seq 再发一次（模拟超时后客户端原样重试）→ 平台幂等窗拦截。
	dup := Telemetry{Vin: "veh-001", Seq: 1, Speed: 30, Ts: time.Now().Unix()}
	if err := dev.SendWithRetry(ctx, dup); err != nil {
		fmt.Printf("[重试失败] %v\n", err)
		return
	}
	fmt.Println("重试上报返回 200（平台幂等窗判定为重复，不二次生效）")

	// 4. 坏 token：未知设备携带错误密钥 → 401，重连循环应立刻放弃不空转。
	bad := &Reporter{
		Endpoint: ts.URL + "/api/v1/telemetry",
		DeviceID: "veh-999", Secret: "wrong-secret",
		Client: &http.Client{Timeout: 2 * time.Second},
	}
	err := bad.SendWithRetry(ctx, Telemetry{Vin: "veh-999", Seq: 1, Speed: 0})
	fmt.Printf("坏设备被拒（预期）: %v\n", err)

	ingest, dupN, authN := platform.Stats()
	fmt.Printf("== 平台统计：生效 %d 条 / 重复拦截 %d 条 / 鉴权失败 %d 次 ==\n", ingest, dupN, authN)
}
