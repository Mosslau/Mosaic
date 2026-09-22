package device

import (
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"strings"
	"testing"
	"time"
)

// newRPCClient 用标准库 net/rpc/jsonrpc 客户端直连设备服务（wire 格式与手写服务端兼容）
func newRPCClient(addr string) (*rpc.Client, error) {
	return jsonrpc.Dial("tcp", addr)
}

// startTestServer 起一个设备服务（随机端口），用 net/rpc/jsonrpc 客户端直接测服务端行为
func startTestServer(t *testing.T, rate int64, refill time.Duration) (addr string, srv *Server, stop func()) {
	t.Helper()
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	srv = NewServer(rate, refill)
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go srv.ServeConn(conn)
		}
	}()
	return lis.Addr().String(), srv, func() { lis.Close() }
}

func TestReportAndGet(t *testing.T) {
	addr, _, stop := startTestServer(t, 1000, time.Hour)
	defer stop()
	c, err := newRPCClient(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	var rr ReportReply
	if err := c.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: "car-001", Speed: 66, Ts: 1000}}, &rr); err != nil {
		t.Fatalf("Report: %v", err)
	}
	if !rr.Ok || rr.DeviceID != "car-001" {
		t.Fatalf("回复异常: %+v", rr)
	}
	var gr GetReply
	if err := c.Call(MethodGet, &GetArgs{DeviceID: "car-001"}, &gr); err != nil {
		t.Fatalf("Get: %v", err)
	}
	if gr.Status == nil || gr.Status.Speed != 66 {
		t.Fatalf("Get 结果异常: %+v", gr.Status)
	}
}

func TestGetNotFound(t *testing.T) {
	addr, _, stop := startTestServer(t, 1000, time.Hour)
	defer stop()
	c, err := newRPCClient(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	var gr GetReply
	err = c.Call(MethodGet, &GetArgs{DeviceID: "ghost"}, &gr)
	if err == nil || !strings.Contains(err.Error(), "device not found") {
		t.Fatalf("应报 device not found, got %v", err)
	}
}

func TestReportOverwritesLatest(t *testing.T) {
	addr, _, stop := startTestServer(t, 1000, time.Hour)
	defer stop()
	c, err := newRPCClient(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	for _, sp := range []float64{60, 90, 120} {
		if err := c.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: "car-001", Speed: sp}}, &ReportReply{}); err != nil {
			t.Fatal(err)
		}
	}
	var gr GetReply
	if err := c.Call(MethodGet, &GetArgs{DeviceID: "car-001"}, &gr); err != nil {
		t.Fatal(err)
	}
	if gr.Status.Speed != 120 { // 幂等语义：重复上报只更新最新值
		t.Fatalf("最新值应为 120, got %v", gr.Status.Speed)
	}
}

func TestRateLimit(t *testing.T) {
	addr, _, stop := startTestServer(t, 3, time.Hour) // refill 极长：桶不中途补满
	defer stop()
	c, err := newRPCClient(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	for i := 0; i < 3; i++ {
		if err := c.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: "d", Speed: 1}}, &ReportReply{}); err != nil {
			t.Fatalf("第 %d 次应在限流内: %v", i+1, err)
		}
	}
	err = c.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: "d", Speed: 1}}, &ReportReply{})
	if err == nil || !strings.Contains(err.Error(), "rate limited") {
		t.Fatalf("第 4 次应被限流, got %v", err)
	}
}

func TestListSorted(t *testing.T) {
	addr, _, stop := startTestServer(t, 1000, time.Hour)
	defer stop()
	c, err := newRPCClient(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	for _, id := range []string{"car-003", "car-001", "car-002"} {
		if err := c.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: id}}, &ReportReply{}); err != nil {
			t.Fatal(err)
		}
	}
	var lr ListReply
	if err := c.Call(MethodList, &struct{}{}, &lr); err != nil {
		t.Fatal(err)
	}
	if len(lr.Statuses) != 3 {
		t.Fatalf("len=%d, want 3", len(lr.Statuses))
	}
	if lr.Statuses[0].DeviceID != "car-001" || lr.Statuses[2].DeviceID != "car-003" {
		t.Fatalf("应按设备号排序: %+v", lr.Statuses)
	}
}
