// Command security-check 公网路径安全基线自检(设计文档 §8.2 三件套 + §12 清零清单①)。
//
// 六项检查, 全过才算"安全按路径达标":
//
//	① TLS + 正确凭证          → 连接成功且能发自己 topic(正向基线)
//	② TLS 匿名(无凭证)        → 拒绝(一车一密生效)
//	③ TLS 错密码              → 拒绝(凭证校验生效)
//	④ TLS 合法设备发他人 topic → 被拒并被断开(ACL 生效, 防伪造他人数据)
//	⑤ 明文 TCP 打 TLS 端口     → 失败(8883 不接受明文)
//	⑥ 明文 1883 匿名 dev 形态  → 成功(内网路径回归, ACL 不误伤)
//
// 用法(先跑 deploy/emqx/seed-users.sh 灌入对应 VIN 的凭证):
//
//	go run ./cmd/security-check -tls-broker localhost:8883 -plain-broker localhost:11883 \
//	  -cacert ../../deploy/emqx/certs/ca.crt -vin OV20260001
package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"

	"github.com/Mosslau/OceanVerse/ingest/device-simulator/internal/simconn"
)

var (
	tlsBroker   = flag.String("tls-broker", "localhost:8883", "TLS 监听器地址")
	plainBroker = flag.String("plain-broker", "localhost:11883", "明文监听器地址(dev 内网)")
	caCert      = flag.String("cacert", "../../deploy/emqx/certs/ca.crt", "自签 CA 证书路径")
	vin         = flag.String("vin", "OV20260001", "合法设备 VIN(需已灌入凭证)")
	otherVIN    = flag.String("other-vin", "OV00000099", "他人 VIN(用于越权发布检查)")
	pwPrefix    = flag.String("password-prefix", "pw-", "一车一密密码前缀")
	timeout     = flag.Duration("timeout", 8*time.Second, "单项检查超时")
)

var failed int

func main() {
	flag.Parse()
	fmt.Println("=== OceanVerse 公网路径安全基线自检 ===")
	fmt.Printf("TLS 端口: %s | 明文端口: %s | 被测设备: %s\n\n", *tlsBroker, *plainBroker, *vin)

	// ① 正向基线: TLS + 正确凭证, 发自己 topic
	check("① TLS + 正确凭证 → 连接并发布自己 topic", func() error {
		c, err := connect(simconn.Config{Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: *vin, PwPrefix: *pwPrefix})
		if err != nil {
			return err
		}
		defer c.Disconnect(200)
		return publishAndWait(c, "ov/"+*vin+"/bin", []byte("##security-check"))
	})

	// ② 匿名 TLS: 应被拒
	check("② TLS 匿名 → 拒绝", func() error {
		if err := mustReject(*vin, "", ""); err != nil {
			return fmt.Errorf("匿名连接未被拒绝(一车一密未生效): %v", err)
		}
		return nil
	})

	// ③ 错密码: 应被拒
	check("③ TLS 错密码 → 拒绝", func() error {
		if err := mustReject(*vin, *vin, "wrong-password"); err != nil {
			return fmt.Errorf("错密码未被拒绝: %v", err)
		}
		return nil
	})

	// ④ 越权发布: 合法设备发他人 topic, 应被拒并断开
	check("④ TLS 合法设备发他人 topic → 拒绝并断开", func() error {
		c, err := connect(simconn.Config{Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: *vin, PwPrefix: *pwPrefix})
		if err != nil {
			return err
		}
		defer c.Disconnect(200)
		token := c.Publish("ov/"+*otherVIN+"/bin", 1, false, []byte("##forged"))
		token.WaitTimeout(*timeout)
		// deny_action=disconnect: 越权发布后连接被 broker 断开
		deadline := time.Now().Add(3 * time.Second)
		for time.Now().Before(deadline) {
			if !c.IsConnectionOpen() {
				return nil
			}
			time.Sleep(100 * time.Millisecond)
		}
		if token.Error() != nil {
			return nil // 有的实现直接回错误, 也算拒绝
		}
		return fmt.Errorf("越权发布未被拒绝(ACL 未生效): 连接仍在线")
	})

	// ⑤ 明文打 TLS 端口: 应失败
	check("⑤ 明文 TCP 打 8883 → 失败", func() error {
		c, err := connect(simconn.Config{Broker: *tlsBroker, TLS: false, VIN: *vin})
		if err != nil {
			return nil // 连接阶段即失败, 符合预期
		}
		c.Disconnect(200)
		return fmt.Errorf("明文连接 TLS 端口竟然成功(8883 配置有误)")
	})

	// ⑥ 明文 1883 dev 形态: 应成功(回归, 确认 ACL 不误伤内网)
	check("⑥ 明文 1883 匿名 dev 形态 → 成功(回归)", func() error {
		c, err := connect(simconn.Config{Broker: *plainBroker, TLS: false, VIN: *vin})
		if err != nil {
			return err
		}
		defer c.Disconnect(200)
		return publishAndWait(c, "ov/"+*vin+"/bin", []byte("##dev-check"))
	})

	fmt.Println()
	if failed > 0 {
		fmt.Printf("❌ %d 项未通过 —— 公网路径未达基线, 不得开通 8883 对外(设计文档 §8 红线)\n", failed)
		os.Exit(1)
	}
	fmt.Println("✅ 六项全过 —— 公网路径安全基线达标(三件套: TLS / 一车一密 / ACL)")
}

// connect 建立连接(失败即返回错误)。
func connect(cfg simconn.Config) (mqtt.Client, error) {
	cfg.AutoReconn = false
	cfg.KeepAlive = 30 * time.Second
	c, err := simconn.New(cfg)
	if err != nil {
		return nil, err
	}
	token := c.Connect()
	if !token.WaitTimeout(*timeout) {
		return nil, fmt.Errorf("连接超时")
	}
	if err := token.Error(); err != nil {
		return nil, err
	}
	return c, nil
}

// mustReject 断言带指定凭证(或匿名)的连接被拒绝。
func mustReject(vin, username, password string) error {
	cfg := simconn.Config{Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: vin}
	if username == "" {
		cfg.ForceAnonymous = true
	} else {
		cfg.Username, cfg.Password = username, password
	}
	c, err := simconn.New(cfg)
	if err != nil {
		return err
	}
	token := c.Connect()
	token.WaitTimeout(*timeout)
	if token.Error() == nil {
		c.Disconnect(200)
		return fmt.Errorf("连接成功(预期被拒)")
	}
	return nil
}

func publishAndWait(c mqtt.Client, topic string, payload []byte) error {
	token := c.Publish(topic, 1, false, payload)
	if !token.WaitTimeout(*timeout) {
		return fmt.Errorf("发布超时")
	}
	return token.Error()
}

func check(name string, fn func() error) {
	if err := fn(); err != nil {
		failed++
		fmt.Printf("❌ %s\n     原因: %v\n", name, err)
		return
	}
	fmt.Printf("✅ %s\n", name)
}
