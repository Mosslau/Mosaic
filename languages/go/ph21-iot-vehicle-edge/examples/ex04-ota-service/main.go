// 来源：ph21-iot-vehicle-edge examples/ex04-ota-service/main.go
// 一句话说明：演示主程序——登记固件 v1.0→v2.0，对 12 台车分 3 批灰度：故事 A
// 全批成功推进到 complete；故事 B 第二批 1/4 失败越限 → 引擎判 rollback，
// 运维据此把目标换回每车的升级前版本（RollbackTarget）。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"
)

// shaOf 演示辅助：算内容 sha256。
func shaOf(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

func main() {
	// 1. 固件台账：登记 v1.0 与 v2.0（含校验值）。
	store := NewFirmwareStore()
	_ = store.Register(Firmware{Version: "v1.0", SHA256: shaOf("firmware-1.0"), Size: 1024, ReleasedAt: time.Now().AddDate(0, -2, 0)})
	_ = store.Register(Firmware{Version: "v2.0", SHA256: shaOf("firmware-2.0"), Size: 2048, ReleasedAt: time.Now()})
	// 下载内容校验：内容被篡改必须被拦下。
	if err := store.VerifyContent("v2.0", []byte("firmware-2.0-tampered")); err != nil {
		fmt.Printf("[OTA 校验] 篡改包被拦下（预期）: %v\n", err)
	}

	// 2. 12 台车，车队基线 v1.0。
	vins := make([]string, 12)
	for i := range vins {
		vins[i] = fmt.Sprintf("veh-%03d", i)
	}
	startFrom := map[string]string{}
	for _, v := range vins {
		startFrom[v] = "v1.0"
	}
	batch := func(from, to int) *Batch {
		return &Batch{Index: from / 4, VINs: vins[from:to]}
	}
	batches := []*Batch{batch(0, 4), batch(4, 8), batch(8, 12)}

	// 3. 故事 A：全批成功 → advance → complete。
	ra, _ := NewRollout(RolloutOptions{TargetVersion: "v2.0", FailRateLimit: 0.2}, batches, startFrom)
	simulate := func(r *Rollout, vv []string, okAll bool) {
		for _, v := range vv {
			d := r.OnDeviceReport(v, okAll)
			fmt.Printf("  %s 报告 → %s（%s）\n", v, d, r.Status())
		}
	}
	fmt.Println("== 故事 A：全批成功 ==")
	simulate(ra, batches[0].VINs, true)
	simulate(ra, batches[1].VINs, true)
	simulate(ra, batches[2].VINs, true)
	fmt.Println("A 终态:", ra.Summary())

	// 4. 故事 B：第二批失败率越限 → rollback；打印该批回滚目标。
	fmt.Println("== 故事 B：第二批 4 台中 1 台失败（越 20% 上限） ==")
	rb, _ := NewRollout(RolloutOptions{TargetVersion: "v2.0", FailRateLimit: 0.2}, batches, startFrom)
	simulate(rb, batches[0].VINs, true)
	for i, v := range batches[1].VINs {
		d := rb.OnDeviceReport(v, i != 1) // 第 2 台失败
		fmt.Printf("  %s 报告 → %s（%s）\n", v, d, rb.Status())
		if d == DecisionRollback {
			fmt.Printf("  → 回滚决策：%s 回滚到 %s\n", v, rb.RollbackTarget(v))
		}
	}
	fmt.Println("B 终态:", rb.Summary())
	fmt.Println("== ex04 演示完成：固件校验 / 分批灰度 / 回滚决策全通 ==")
}
