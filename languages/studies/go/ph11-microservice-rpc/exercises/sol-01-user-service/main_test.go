package main

import (
	"net/rpc"
	"net/rpc/jsonrpc"
	"strings"
	"testing"
)

func newTestClient(t *testing.T) (*rpc.Client, func()) {
	t.Helper()
	addr, stop, err := startServer()
	if err != nil {
		t.Fatalf("startServer: %v", err)
	}
	c, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		stop()
		t.Fatalf("dial: %v", err)
	}
	return c, func() { c.Close(); stop() }
}

func TestGetUserFound(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var ar AddUserReply
	if err := c.Call("UserService.AddUser", &AddUserArgs{Name: "alice", Email: "a@t.dev"}, &ar); err != nil {
		t.Fatal(err)
	}
	var gr GetUserReply
	if err := c.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		t.Fatal(err)
	}
	if gr.User == nil || gr.User.Name != "alice" || gr.User.ID != ar.ID {
		t.Fatalf("结果异常: %+v", gr.User)
	}
}

func TestGetUserNotFound(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var gr GetUserReply
	err := c.Call("UserService.GetUser", &GetUserArgs{ID: 999}, &gr)
	if err == nil || !strings.Contains(err.Error(), "user not found") {
		t.Fatalf("应返回 user not found, got %v", err)
	}
}

func TestListUsersSorted(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	for _, name := range []string{"c", "a", "b"} {
		if err := c.Call("UserService.AddUser", &AddUserArgs{Name: name}, &AddUserReply{}); err != nil {
			t.Fatal(err)
		}
	}
	var lr ListUsersReply
	if err := c.Call("UserService.ListUsers", &ListUsersArgs{}, &lr); err != nil {
		t.Fatal(err)
	}
	if len(lr.Users) != 3 {
		t.Fatalf("len=%d, want 3", len(lr.Users))
	}
	// 插入顺序 c(1) a(2) b(3) → 按 ID 升序 c,a,b
	if lr.Users[0].Name != "c" || lr.Users[2].Name != "b" {
		t.Fatalf("排序异常: %+v", lr.Users)
	}
}

func TestAddUserValidation(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var ar AddUserReply
	err := c.Call("UserService.AddUser", &AddUserArgs{Name: ""}, &ar)
	if err == nil || !strings.Contains(err.Error(), "name required") {
		t.Fatalf("空 name 应报错, got %v", err)
	}
}

func TestRegisteredName(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	// 服务名应为显式注册的 "UserService"；错名调用应失败
	var reply struct{}
	if err := c.Call("WrongService.GetUser", &GetUserArgs{ID: 1}, &reply); err == nil {
		t.Fatal("未注册的服务名应调用失败")
	}
	if err := c.Call("UserService.ListUsers", &ListUsersArgs{}, &ListUsersReply{}); err != nil {
		t.Fatalf("正确服务名应可调用: %v", err)
	}
}
