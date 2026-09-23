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
//	⑦ 自报他人 clientid        → 仍发不了他人 VIN topic(身份锚点 = 认证过的 username)
//	⑧ 不冒充的正常身份          → 发布成功(⑦ 的正向对照, 防"负向判据自我满足")
//
// 用法(先跑 deploy/emqx/seed-users.sh 灌入对应 VIN 的凭证):
//
//	go run ./cmd/security-check -tls-broker localhost:8883 -plain-broker localhost:11883 \
//	  -cacert ../../deploy/emqx/certs/ca.crt -vin OV20260001
//
// **前置自检**(2026-09-20 加, CI 踩过): 开跑前先验证"该 VIN 的凭证**确实可用**"。
// 背景: CI 首跑时 ①④ 报 `network Error : EOF` —— 但那是**不可判定**的信号
// (分不清"凭证没生效" / "ACL 拦错" / "TLS 抖动")。加了这一步后:
// 凭证不可用直接给出明确结论 + 退出码 3, 不再伪装成"安全项不达标"。
package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"

	"github.com/Mosslau/Mosaic/ingest/device-simulator/internal/simconn"
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
	fmt.Println("=== Mosaic 公网路径安全基线自检 ===")
	fmt.Printf("TLS 端口: %s | 明文端口: %s | 被测设备: %s\n\n", *tlsBroker, *plainBroker, *vin)

	// 前置: 凭证可用性(不可判定 → 早退, 见文件头说明)
	if err := preflightCredentials(); err != nil {
		fmt.Printf("❌ 前置自检未通过: %v\n", err)
		fmt.Println("   → 后续安全判据不可信, 故不继续; 这不是\"安全项不达标\", 而是环境/前置条件问题")
		fmt.Println("   处置: 确认 seed-users.sh 已灌入该 VIN, 且 EMQX 已就绪(emqx ctl status); 明细见 EMQX 日志的 AUTHN/AUTHZ 记录")
		os.Exit(3)
	}
	fmt.Println()

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
		return mustBeDisconnected(c, "ov/"+*otherVIN+"/bin", []byte("##forged"))
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

	// ⑦ 身份锚点不可伪造: 用**自己的凭证 + 别人的 clientid** 连接, 再发**别人 VIN** 的 topic。
	// 背景(2026-09-20 发现并修复): ACL 原先写 `ov/${clientid}/#` —— clientid 是客户端自报的,
	// 于是一台设备只要把 clientid 填成他人 VIN, 就能发布 `ov/{他人VIN}/#`,
	// 把网关/codec 两端刚补齐的 topic-VIN 身份锚点整个绕过(冒充他人车辆写数据)。
	// 修复后规则是 `ov/${username}/#`: username 由一车一密认证绑定, 不可伪造。
	//
	// 判据与 ④ 同形(deny_action=disconnect, QoS0 发布成功不代表没被拒):
	// **连接必须被断开**; 连接仍在线 = 仍以 clientid 为锚点 = 身份可伪造。
	check("⑦ TLS 自报他人 clientid → 发他人 VIN topic 必须被拒", func() error {
		c, err := connect(simconn.Config{
			Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: *vin, PwPrefix: *pwPrefix,
			ClientIDOverride: *otherVIN, // 冒充: 自报成他人车辆
		})
		if err != nil {
			return nil // 连接阶段即被拒, 同样算通过
		}
		defer c.Disconnect(200)
		return mustBeDisconnected(c, "ov/"+*otherVIN+"/bin", []byte("##spoof-clientid"))
	})

	// ⑧ 正向对照: 同一套凭证、**不冒充**时必须仍然成功。
	// 为什么需要它: ⑦ 的"被拒"必须被证明来自身份校验, 而不是"链路被配坏了"——
	// 否则把 ACL 写成 deny all 也能让 ⑦ 通过(这类"负向判据自我满足"是安全自检的典型陷阱)。
	check("⑧ TLS 正常身份(不冒充) → 发布自己的 topic 成功(对照)", func() error {
		c, err := connect(simconn.Config{Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: *vin, PwPrefix: *pwPrefix})
		if err != nil {
			return err
		}
		defer c.Disconnect(200)
		return publishAndWait(c, "ov/"+*vin+"/bin", []byte("##normal"))
	})

	fmt.Println()
	if failed > 0 {
		fmt.Printf("❌ %d 项未通过 —— 公网路径未达基线, 不得开通 8883 对外(设计文档 §8 红线)\n", failed)
		os.Exit(1)
	}
	fmt.Println("✅ 八项全过 —— 公网路径安全基线达标(三件套: TLS / 一车一密 / ACL, 且身份锚点不可伪造)")
}

// preflightCredentials 确认"该 VIN 的凭证在当前 EMQX 上确实可用"。
//
// 为什么要单独一步: 一车一密是**运行时写入**(seed-users.sh → emqx ctl), 而 8883 的认证链
// 在监听器上生效。二者之间若有时序/可见性问题, 后续所有 TLS 判据都会以 `EOF` 这种
// **不可判定**的形式失败(CI 实测踩过) —— 既看不出是环境问题还是安全配置问题。
// 本函数把这类失败变成明确结论, 并让退出码 3 与之对应。
func preflightCredentials() error {
	c, err := connect(simconn.Config{Broker: *tlsBroker, TLS: true, CACert: *caCert, VIN: *vin, PwPrefix: *pwPrefix})
	if err != nil {
		return fmt.Errorf("凭证 %s 无法通过 8883 认证(密码前缀 %q): %w", *vin, *pwPrefix, err)
	}
	defer c.Disconnect(200)
	return nil
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

// publishAndWait 发布并等待 broker 确认。
func publishAndWait(c mqtt.Client, topic string, payload []byte) error {
	token := c.Publish(topic, 1, false, payload)
	if !token.WaitTimeout(*timeout) {
		return fmt.Errorf("发布超时")
	}
	return token.Error()
}

// mustBeDisconnected 断言"越权发布导致连接被断开"。
//
// 为什么不能只看发布返回值: 违规发布常用 QoS0 或"发布后断连"的通知方式,
// 此时 Publish 的 token 可能没有任何错误 —— 必须看**连接状态**。
// deny_action=disconnect(emqx.conf)下, 被拒的发布会让 broker 直接断链。
func mustBeDisconnected(c mqtt.Client, topic string, payload []byte) error {
	token := c.Publish(topic, 1, false, payload)
	token.WaitTimeout(*timeout)
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
	return fmt.Errorf("越权发布未被拒绝(连接仍在线) → 身份锚点可伪造")
}

func check(name string, fn func() error) {
	if err := fn(); err != nil {
		failed++
		fmt.Printf("❌ %s\n     原因: %v\n", name, err)
		return
	}
	fmt.Printf("✅ %s\n", name)
}
