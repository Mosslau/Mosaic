// 来源：ph21-data-ingest-gateway examples/ex03-websocket-configState/ws.go
// 一句话说明：RFC 6455 最小实现——HTTP 升级握手 + 数据帧编解码（掩码/长度扩展/
// 控制帧）+ 读循环所需的 Conn 抽象。只支持单帧（不分片）、无扩展协商，教学子集；
// 帧布局与方向不对称规则见主文档 4.2。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18880   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"bufio"
	"crypto/rand"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"strings"
	"sync"
)

// WebSocket 操作码（RFC 6455 §5.2）。
const (
	opContinuation byte = 0x0
	opText         byte = 0x1
	opBinary       byte = 0x2
	opClose        byte = 0x8
	opPing         byte = 0x9
	opPong         byte = 0xA
)

const wsGUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

// ErrClosed 连接已关闭/读到关闭帧。
var ErrClosed = errors.New("websocket: closed")

// Conn 一条已升级的 WebSocket 连接。写方向带锁；读方向单 goroutine。
type Conn struct {
	raw       net.Conn
	br        *bufio.Reader
	writeMu   sync.Mutex
	maskWrite bool // 客户端→服务器必须掩码，服务器→客户端必须不掩码（4.2 不对称规则）
	closeOnce sync.Once
}

// ReadMessage 读一帧（文本/二进制/控制帧都返回 opcode + payload）。
// 调用方负责按 opcode 处理（ping 回 pong、close 收尾）。
func (c *Conn) ReadMessage() (byte, []byte, error) {
	var hdr [2]byte
	if _, err := io.ReadFull(c.br, hdr[:]); err != nil {
		return 0, nil, err
	}
	opcode := hdr[0] & 0x0F
	fin := hdr[0]&0x80 != 0
	masked := hdr[1]&0x80 != 0
	_ = fin // 教学子集只支持单帧：出现 FIN=0 的分片直接按整帧读，不重组
	// 负载长度：7 位，126 → 后随 2 字节，127 → 后随 8 字节（大帧路径按规范走）。
	length := uint64(hdr[1] & 0x7F)
	switch length {
	case 126:
		var ext [2]byte
		if _, err := io.ReadFull(c.br, ext[:]); err != nil {
			return 0, nil, err
		}
		length = uint64(binary.BigEndian.Uint16(ext[:]))
	case 127:
		var ext [8]byte
		if _, err := io.ReadFull(c.br, ext[:]); err != nil {
			return 0, nil, err
		}
		length = binary.BigEndian.Uint64(ext[:])
	}
	if length > 16<<20 {
		return 0, nil, fmt.Errorf("websocket: 帧过大 %d", length)
	}
	var maskKey [4]byte
	if masked {
		if _, err := io.ReadFull(c.br, maskKey[:]); err != nil {
			return 0, nil, err
		}
	}
	payload := make([]byte, length)
	if _, err := io.ReadFull(c.br, payload); err != nil {
		return 0, nil, err
	}
	if masked { // 客户端帧必须掩码：payload[i] ^= maskKey[i%4]
		for i := range payload {
			payload[i] ^= maskKey[i%4]
		}
	}
	return opcode, payload, nil
}

// WriteMessage 发一帧。
func (c *Conn) WriteMessage(opcode byte, payload []byte) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	// 组装帧：固定头 2~14 字节 + 掩码键 + 负载。
	length := len(payload)
	hdr := make([]byte, 0, 14)
	hdr = append(hdr, 0x80|opcode) // FIN=1
	var maskBit byte
	if c.maskWrite {
		maskBit = 0x80
	}
	switch {
	case length < 126:
		hdr = append(hdr, maskBit|byte(length))
	case length <= 0xFFFF:
		hdr = append(hdr, maskBit|126, byte(length>>8), byte(length))
	default:
		hdr = append(hdr, maskBit|127)
		var ext [8]byte
		binary.BigEndian.PutUint64(ext[:], uint64(length))
		hdr = append(hdr, ext[:]...)
	}
	if c.maskWrite {
		var key [4]byte
		if _, err := rand.Read(key[:]); err != nil {
			return err
		}
		hdr = append(hdr, key[:]...)
		masked := make([]byte, len(payload))
		for i, b := range payload {
			masked[i] = b ^ key[i%4]
		}
		payload = masked
	}
	buf := append(hdr, payload...)
	_, err := c.raw.Write(buf)
	return err
}

// Ping 发 ping 帧；对端必须回 pong（4.2 心跳）。
func (c *Conn) Ping() error { return c.WriteMessage(opPing, nil) }

// Close 发关闭帧并断开。
func (c *Conn) Close() error {
	var err error
	c.closeOnce.Do(func() {
		_ = c.WriteMessage(opClose, nil)
		err = c.raw.Close()
	})
	return err
}

// serverAccept 计算握手应答：base64(sha1(key + GUID))。
func serverAccept(key string) string {
	h := sha1.Sum([]byte(key + wsGUID))
	return base64.StdEncoding.EncodeToString(h[:])
}

// newClientKey 生成随机的 Sec-WebSocket-Key（16 字节随机 → base64）。
func newClientKey() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	return base64.StdEncoding.EncodeToString(b[:])
}

// httpRequest 服务端握手请求解析结果（升级前的授权判断需要它）。
type httpRequest struct {
	Path  string // 请求路径（不含查询串）
	Token string // 查询串中的 token=..（教学简化：token 走 URL）
	Key   string // Sec-WebSocket-Key
}

// readUpgradeRequest 读一个 HTTP GET 升级请求。失败时错误可写回 4xx。
func readUpgradeRequest(br *bufio.Reader) (*httpRequest, error) {
	line, err := br.ReadString('\n')
	if err != nil {
		return nil, err
	}
	parts := strings.Fields(line)
	if len(parts) < 3 || parts[0] != "GET" {
		return nil, errors.New("websocket: 非法握手请求行")
	}
	req := &httpRequest{Path: parts[1]}
	if i := strings.IndexByte(req.Path, '?'); i >= 0 {
		query := req.Path[i+1:]
		req.Path = req.Path[:i]
		if v, ok := strings.CutPrefix(query, "token="); ok {
			req.Token = v
		}
	}
	for {
		line, err = br.ReadString('\n')
		if err != nil {
			return nil, err
		}
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			break
		}
		if k, ok := strings.CutPrefix(line, "Sec-WebSocket-Key:"); ok {
			req.Key = strings.TrimSpace(k)
		}
	}
	if req.Key == "" {
		return nil, errors.New("websocket: 缺握手 key")
	}
	return req, nil
}

// Dial 客户端握手：连接 addr 并发送 GET 升级。之后 Conn 的 maskWrite=true（须掩码）。
func Dial(addr, reqPath string) (*Conn, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("websocket dial %s: %w", addr, err)
	}
	key := newClientKey()
	req := fmt.Sprintf("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n", reqPath, addr, key)
	if _, err := conn.Write([]byte(req)); err != nil {
		_ = conn.Close()
		return nil, err
	}
	br := bufio.NewReader(conn)
	status, err := br.ReadString('\n')
	if err != nil {
		_ = conn.Close()
		return nil, err
	}
	if !strings.Contains(status, " 101 ") {
		_, _ = io.Copy(io.Discard, br)
		_ = conn.Close()
		return nil, fmt.Errorf("websocket 握手失败: %s", strings.TrimSpace(status))
	}
	for {
		line, err := br.ReadString('\n')
		if err != nil {
			_ = conn.Close()
			return nil, err
		}
		if line == "\r\n" || line == "\n" {
			break
		}
	}
	return &Conn{raw: conn, br: br, maskWrite: true}, nil
}

func writeHTTPError(w io.Writer, code int, msg string) {
	fmt.Fprintf(w, "HTTP/1.1 %d %s\r\nContent-Type: text/plain\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s", code, httpStatusText(code), len(msg), msg)
}

func writeHTTP101(w io.Writer, accept string) {
	fmt.Fprintf(w, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n", accept)
}

func httpStatusText(code int) string {
	switch code {
	case 400:
		return "Bad Request"
	case 401:
		return "Unauthorized"
	default:
		return "Error"
	}
}
