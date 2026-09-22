// 来源：ph21-data-ingest-gateway examples/ex02-agent-reconnect-idempotent/auth.go
// 一句话说明：采集端动态 token 的签名与校验——HMAC-SHA256 按时间槽派生、平台按
// (当前槽, 上一槽) 校验，容忍小量时钟偏移；比较用 crypto/subtle 常量时间，
// 防计时侧信道逐字节猜出 token（主文档 3.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"time"
)

// ErrUnauthorized 鉴权失败哨兵：重连循环对它直接放弃（重试无意义），
// 与网络类错误分开处理（主文档 3.2/3.3）。
var ErrUnauthorized = errors.New("agent auth: unauthorized")

// SignToken 为 agentID 签发一个覆盖时间槽 slot 的动态 token。
// slot = now 对齐 slotDur 的序号：HMAC(secret, agentID|slot)。
func SignToken(secret, agentID string, slotDur time.Duration, now time.Time) string {
	slot := now.Unix() / int64(slotDur.Seconds())
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(agentID + "|" + strconv.FormatInt(slot, 10)))
	return hex.EncodeToString(mac.Sum(nil))
}

// VerifyToken 校验 token 是否由 secret 对 agentID 在当前或上一时间槽签发。
// 容忍"采集端时钟比平台慢一个槽"的偏移；返回错误统一包 ErrUnauthorized。
func VerifyToken(secret, agentID, token string, slotDur time.Duration, now time.Time) error {
	cur := now.Unix() / int64(slotDur.Seconds())
	for _, slot := range []int64{cur, cur - 1} { // 上一槽：容时钟负偏移
		want := hmac.New(sha256.New, []byte(secret))
		_, _ = want.Write([]byte(agentID + "|" + strconv.FormatInt(slot, 10)))
		got := []byte(token)
		// 长度不同时 subtle 也安全返回 0，不会泄露有效前缀信息。
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(want.Sum(nil))), got) == 1 {
			return nil
		}
	}
	return fmt.Errorf("%w: 采集端 %s token 校验失败", ErrUnauthorized, agentID)
}
