package main

import (
	"errors"
	"net/rpc"
	"strings"
	"testing"
)

// newTestClient 起一个真实 TCP server（随机端口），返回 client 与清理函数
func newTestClient(t *testing.T) (*rpc.Client, func()) {
	t.Helper()
	addr, stop, err := startServer()
	if err != nil {
		t.Fatalf("startServer: %v", err)
	}
	c, err := rpc.Dial("tcp", addr)
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
		t.Fatalf("AddUser: %v", err)
	}
	var gr GetUserReply
	if err := c.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		t.Fatalf("GetUser: %v", err)
	}
	if gr.User == nil || gr.User.Name != "alice" || gr.User.ID != ar.ID {
		t.Fatalf("GetUser 结果异常: %+v", gr.User)
	}
}

func TestGetUserNotFound(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var gr GetUserReply
	err := c.Call("UserService.GetUser", &GetUserArgs{ID: 999}, &gr)
	if err == nil {
		t.Fatal("查不存在的用户应返回错误")
	}
	if !strings.Contains(err.Error(), "user not found") {
		t.Fatalf("错误信息异常: %v", err)
	}
}

func TestListUsersOrdered(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	for _, name := range []string{"carol", "alice", "bob"} {
		if err := c.Call("UserService.AddUser", &AddUserArgs{Name: name}, &AddUserReply{}); err != nil {
			t.Fatalf("AddUser %s: %v", name, err)
		}
	}
	var lr ListUsersReply
	if err := c.Call("UserService.ListUsers", &ListUsersArgs{}, &lr); err != nil {
		t.Fatalf("ListUsers: %v", err)
	}
	if len(lr.Users) != 3 {
		t.Fatalf("len=%d, want 3", len(lr.Users))
	}
	// 按 ID 升序：carol(1) alice(2) bob(3) —— 验证服务端排序生效（插入顺序是 carol/alice/bob）
	if lr.Users[0].Name != "carol" || lr.Users[2].Name != "bob" {
		t.Fatalf("顺序异常: %+v", lr.Users)
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

func TestAsyncCall(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	// 异步调用：Go 立即返回，done 通道收 *rpc.Call
	var ar AddUserReply
	done := make(chan *rpc.Call, 1)
	c.Go("UserService.AddUser", &AddUserArgs{Name: "async-user"}, &ar, done)
	call := <-done
	if call.Error != nil {
		t.Fatalf("async call: %v", call.Error)
	}
	if ar.ID == 0 {
		t.Fatal("异步调用未回填 reply")
	}
}

func TestUnknownMethod(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var reply struct{}
	err := c.Call("UserService.Nonexistent", &struct{}{}, &reply)
	if err == nil {
		t.Fatal("未知方法应报错")
	}
	if !strings.Contains(err.Error(), "Nonexistent") {
		t.Fatalf("错误应包含方法名, got %v", err)
	}
}

// errors.Is 对 net/rpc 的错误不成立（错误是字符串透传），这里显式验证这一点，
// 防止学习者误用 errors.Is 判断 RPC 错误
func TestErrorsIsNotApplicable(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var gr GetUserReply
	err := c.Call("UserService.GetUser", &GetUserArgs{ID: 1}, &gr)
	if err == nil {
		t.Fatal("空服务应报错")
	}
	if errors.Is(err, errors.New("user not found")) {
		t.Fatal("net/rpc 错误是字符串透传，errors.Is 不应命中")
	}
}
