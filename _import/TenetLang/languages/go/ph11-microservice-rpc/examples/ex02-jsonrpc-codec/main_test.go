package main

import (
	"bufio"
	"encoding/json"
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"strconv"
	"strings"
	"testing"
)

func newTestClient(t *testing.T) (*rpc.Client, func()) {
	t.Helper()
	addr, stop, err := startJSONServer()
	if err != nil {
		t.Fatalf("startJSONServer: %v", err)
	}
	c, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		stop()
		t.Fatalf("dial: %v", err)
	}
	return c, func() { c.Close(); stop() }
}

// TestWireFormat 验证 JSON-RPC wire 格式：请求是 {"method","params","id"}，响应回显 id
func TestWireFormat(t *testing.T) {
	addr, stop, err := startJSONServer()
	if err != nil {
		t.Fatal(err)
	}
	defer stop()

	// 先造一条数据，否则 GetUser 找不到
	client, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	var ar AddUserReply
	if err := client.Call("UserService.AddUser", &AddUserArgs{Name: "alice"}, &ar); err != nil {
		t.Fatal(err)
	}

	var id uint64 = 42
	resp, err := rawJSONRPC(addr, "UserService.GetUser", GetUserArgs{ID: ar.ID}, &id)
	if err != nil {
		t.Fatalf("rawJSONRPC: %v", err)
	}
	var parsed struct {
		ID     uint64          `json:"id"`
		Result json.RawMessage `json:"result"`
		Error  any             `json:"error"`
	}
	if err := json.Unmarshal([]byte(resp), &parsed); err != nil {
		t.Fatalf("响应不是合法 JSON: %v\n%s", err, resp)
	}
	if parsed.ID != 42 {
		t.Fatalf("id 应回显 42, got %d", parsed.ID)
	}
	if parsed.Error != nil {
		t.Fatalf("成功调用 error 应为 null, got %v", parsed.Error)
	}
	if !strings.Contains(string(parsed.Result), "alice") {
		t.Fatalf("result 应包含用户名 alice: %s", parsed.Result)
	}
}

func TestWireError(t *testing.T) {
	addr, stop, err := startJSONServer()
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	var id uint64 = 1
	resp, err := rawJSONRPC(addr, "UserService.GetUser", GetUserArgs{ID: 999}, &id)
	if err != nil {
		t.Fatalf("rawJSONRPC: %v", err)
	}
	if !strings.Contains(resp, `"error"`) || !strings.Contains(resp, "user not found") {
		t.Fatalf("错误响应应带 error 字段与错误串: %s", resp)
	}
}

func TestRawParamsArray(t *testing.T) {
	addr, stop, err := startJSONServer()
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	client, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	var ar AddUserReply
	if err := client.Call("UserService.AddUser", &AddUserArgs{Name: "bob"}, &ar); err != nil {
		t.Fatal(err)
	}

	// 手写一个 params 为数组的报文（JSON-RPC 规范要求 params 是数组或对象，net/rpc 用数组包单参数）
	line := `{"method":"UserService.GetUser","params":[{"ID":` + strconv.FormatInt(ar.ID, 10) + `}],"id":3}` + "\n"
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	if _, err := conn.Write([]byte(line)); err != nil {
		t.Fatal(err)
	}
	resp, err := bufio.NewReader(conn).ReadBytes('\n')
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(resp), `"id":3`) || !strings.Contains(string(resp), "bob") {
		t.Fatalf("手写报文响应异常: %s", resp)
	}
}

// TestGoClientRoundTrip 走 jsonrpc.Dial 的完整往返
func TestGoClientRoundTrip(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var ar AddUserReply
	if err := c.Call("UserService.AddUser", &AddUserArgs{Name: "carol", Email: "c@t.dev"}, &ar); err != nil {
		t.Fatalf("AddUser: %v", err)
	}
	var gr GetUserReply
	if err := c.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		t.Fatalf("GetUser: %v", err)
	}
	if gr.User.Name != "carol" || gr.User.Email != "c@t.dev" {
		t.Fatalf("结果异常: %+v", gr.User)
	}
}

func TestUnknownMethodJSON(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var reply struct{}
	err := c.Call("UserService.Nope", &struct{}{}, &reply)
	if err == nil || !strings.Contains(err.Error(), "Nope") {
		t.Fatalf("未知方法应报错并带方法名, got %v", err)
	}
}
