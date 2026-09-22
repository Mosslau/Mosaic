// 来源：ph21-data-ingest-gateway examples/ex03-websocket-configState/ws_test.go
// 一句话说明：帧层测试——net.Pipe 双向：服务器侧不掩码写/读、客户端侧掩码写，
// 两端收发还原；握手应答 key 正确性（RFC 6455 §4.2.2 已知向量）。
// net.Pipe 是同步管道：写必须等对端并发读，故每个用例先起读 goroutine。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"bufio"
	"net"
	"reflect"
	"testing"
	"time"
)

type frameRes struct {
	op  byte
	p   []byte
	err error
}

// startReader 起一个并发读（net.Pipe 同步语义：写必须等读）。
func startReader(c *Conn) chan frameRes {
	ch := make(chan frameRes, 1)
	go func() {
		op, p, err := c.ReadMessage()
		ch <- frameRes{op, p, err}
	}()
	return ch
}

func TestFrameRoundTripMaskedBothSides(t *testing.T) {
	// net.Pipe 两端都可当"客户端"（掩码写），验证掩码编解码正确性。
	a, b := net.Pipe()
	defer a.Close()
	defer b.Close()
	ca := &Conn{raw: a, br: newBuf(a), maskWrite: true}
	cb := &Conn{raw: b, br: newBuf(b), maskWrite: true}

	msg := []byte(`{"value":66,"flag":"中文负载"}`)
	readCh := startReader(cb)
	if err := ca.WriteMessage(opText, msg); err != nil {
		t.Fatalf("写帧: %v", err)
	}
	select {
	case r := <-readCh:
		if r.err != nil {
			t.Fatalf("读帧: %v", r.err)
		}
		if r.op != opText || !reflect.DeepEqual(r.p, msg) {
			t.Errorf("读到的帧 op=%d payload=%q, want op=%d payload=%q", r.op, r.p, opText, msg)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("帧往返超时")
	}
}

func TestFrameServerWritesUnmasked(t *testing.T) {
	// 服务器 → 客户端方向必须不掩码；客户端读后应还原出原文。
	a, b := net.Pipe()
	defer a.Close()
	defer b.Close()
	serverSide := &Conn{raw: a, br: newBuf(a), maskWrite: false}
	clientSide := &Conn{raw: b, br: newBuf(b), maskWrite: true}

	readCh := startReader(clientSide)
	if err := serverSide.WriteMessage(opText, []byte("server-push")); err != nil {
		t.Fatal(err)
	}
	select {
	case r := <-readCh:
		if r.err != nil || r.op != opText || string(r.p) != "server-push" {
			t.Errorf("服务器裸写应可被客户端读取: op=%d err=%v got=%q", r.op, r.err, r.p)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("读帧超时")
	}
}

func TestPingPongRoundTrip(t *testing.T) {
	a, b := net.Pipe()
	defer a.Close()
	defer b.Close()
	ca := &Conn{raw: a, br: newBuf(a), maskWrite: true}
	cb := &Conn{raw: b, br: newBuf(b), maskWrite: true}

	readCh := startReader(cb)
	if err := ca.WriteMessage(opPing, []byte("hb")); err != nil {
		t.Fatal(err)
	}
	select {
	case r := <-readCh:
		if r.err != nil || r.op != opPing || string(r.p) != "hb" {
			t.Fatalf("ping 读回异常: op=%d payload=%q err=%v", r.op, r.p, r.err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("ping 往返超时")
	}
}

func TestServerAcceptVector(t *testing.T) {
	// RFC 6455 §4.2.2 的官方样例：key=dGhlIHNhbXBsZSBub25jZQ==
	// → accept=s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
	want := "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
	if got := serverAccept("dGhlIHNhbXBsZSBub25jZQ=="); got != want {
		t.Errorf("accept = %q, want %q", got, want)
	}
}

// newBuf 给 net.Conn 包 bufio.Reader（Conn 结构在 net.Pipe 测试里直接构造）。
func newBuf(c net.Conn) *bufio.Reader {
	return bufio.NewReader(c)
}
