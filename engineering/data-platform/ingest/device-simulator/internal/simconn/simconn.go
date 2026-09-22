// Package simconn MQTT 模拟器的连接构造助手: 统一"两个身份形态"规则。
//
// 设计依据(设计文档 §8.1/§8.2 安全按路径排):
//   - dev 形态(内网 1883 匿名联调): clientid = dev-{vin}, 不带凭证
//   - 生产形态(公网 8883 TLS + 一车一密): clientid = {vin}, username = {vin}, password = {pwPrefix}{vin}
//
// 两种形态的 topic 不变(ov/{vin}/…), 差别只在连接身份与是否 TLS —— 便于同一套模拟器
// 分别演练内网联调与公网安全基线。
package simconn

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// Config 连接参数
type Config struct {
	Broker     string // 如 tcp://localhost:11883 或 localhost:8883(配 TLS 自动补 ssl://)
	TLS        bool   // 公网形态: TLS + 一车一密
	CACert     string // TLS 时校验服务端用的 CA 证书路径
	VIN        string
	PwPrefix   string // 生产形态密码前缀, 默认 "pw-"
	KeepAlive  time.Duration
	AutoReconn bool

	// 以下为异常/自检场景的显式覆盖(正常设备不用填):
	Username string // 覆盖 username
	Password string // 覆盖 password
	// ClientIDOverride 覆盖 clientid(仅自检用): 用于验证"自报他人 clientid 也无法越权"——
	// ACL 的锚点必须是认证过的 username, 而不是客户端自报的 clientid。
	ClientIDOverride string
	ForceAnonymous   bool // 显式不带凭证(用于自检"匿名应被拒")
}

// Identity 返回该身份形态下的 (clientID, username, password)。
// dev: 匿名 + dev- 前缀 clientid; 生产: 一车一密。
func Identity(cfg Config) (clientID, username, password string) {
	if cfg.TLS {
		pw := cfg.PwPrefix
		if pw == "" {
			pw = "pw-"
		}
		return cfg.VIN, cfg.VIN, pw + cfg.VIN
	}
	return "dev-" + cfg.VIN, "", ""
}

// BrokerURL 补齐 scheme: TLS 用 ssl://, 明文用 tcp://
func BrokerURL(cfg Config) string {
	b := cfg.Broker
	hasScheme := len(b) > 6 && (b[:6] == "tcp://" || b[:6] == "ssl://" || b[:6] == "ws://" || b[:7] == "wss://")
	if hasScheme {
		return b
	}
	if cfg.TLS {
		return "ssl://" + b
	}
	return "tcp://" + b
}

// New 按配置构造 paho 客户端(未连接)。
func New(cfg Config) (mqtt.Client, error) {
	clientID, username, password := Identity(cfg)
	switch {
	case cfg.ClientIDOverride != "":
		clientID = cfg.ClientIDOverride
	case cfg.ForceAnonymous:
		username, password = "", ""
	case cfg.Username != "":
		username, password = cfg.Username, cfg.Password
	}
	keepAlive := cfg.KeepAlive
	if keepAlive == 0 {
		keepAlive = 60 * time.Second
	}
	opts := mqtt.NewClientOptions().
		AddBroker(BrokerURL(cfg)).
		SetClientID(clientID).
		SetAutoReconnect(cfg.AutoReconn).
		SetConnectRetry(cfg.AutoReconn).
		SetConnectRetryInterval(5 * time.Second).
		SetKeepAlive(keepAlive).
		SetCleanSession(true)
	if username != "" {
		opts.SetUsername(username).SetPassword(password)
	}
	if cfg.TLS {
		tlsCfg, err := TLSConfig(cfg.CACert)
		if err != nil {
			return nil, err
		}
		opts.SetTLSConfig(tlsCfg)
	}
	return mqtt.NewClient(opts), nil
}

// TLSConfig 单向 TLS: 用自签 CA 校验证书链与主机名(设计文档 §8.2 公网基线;
// 双向 mTLS 待设备证书体系落地后在此基础上加 Certificates)。
func TLSConfig(caCertPath string) (*tls.Config, error) {
	ca, err := os.ReadFile(caCertPath)
	if err != nil {
		return nil, fmt.Errorf("读取 CA 证书失败: %w", err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(ca) {
		return nil, fmt.Errorf("CA 证书解析失败: %s", caCertPath)
	}
	return &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12}, nil
}
