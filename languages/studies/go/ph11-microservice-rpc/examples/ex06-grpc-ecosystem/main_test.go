package main

import (
	"context"
	"errors"
	"io"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "tenetlang/go/ph11-microservice-rpc/examples/ex06-grpc-ecosystem/proto"
)

// newTestEnv 起真实 gRPC server（随机端口），返回 client 与清理函数
func newTestEnv(t *testing.T) (*grpc.ClientConn, func()) {
	t.Helper()
	addr, stop, err := startGRPCServer("127.0.0.1:0")
	if err != nil {
		t.Fatalf("startGRPCServer: %v", err)
	}
	conn, err := newClient(addr)
	if err != nil {
		stop()
		t.Fatalf("newClient: %v", err)
	}
	return conn, func() { conn.Close(); stop() }
}

func TestGetUserUnary(t *testing.T) {
	conn, cleanup := newTestEnv(t)
	defer cleanup()
	client := pb.NewUserServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	u, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 1})
	if err != nil {
		t.Fatalf("GetUser: %v", err)
	}
	if u.User.Name != "alice" || u.User.Status != 1 {
		t.Fatalf("结果异常: %+v", u.User)
	}
}

func TestGetUserNotFoundCode(t *testing.T) {
	conn, cleanup := newTestEnv(t)
	defer cleanup()
	client := pb.NewUserServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	_, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 999})
	if err == nil {
		t.Fatal("应返回错误")
	}
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code=%v, want NotFound", status.Code(err))
	}
}

func TestListUsersServerStreaming(t *testing.T) {
	conn, cleanup := newTestEnv(t)
	defer cleanup()
	client := pb.NewUserServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	stream, err := client.ListUsers(ctx, &pb.ListUsersRequest{Ids: []int64{1, 2, 3, 99}})
	if err != nil {
		t.Fatalf("ListUsers: %v", err)
	}
	var names []string
	for {
		u, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			break // 流正常结束
		}
		if err != nil {
			t.Fatalf("Recv: %v", err)
		}
		names = append(names, u.Name)
	}
	// 只返回存在的用户（99 不存在被跳过）
	if len(names) != 2 || names[0] != "alice" || names[1] != "bob" {
		t.Fatalf("流内容异常: %v", names)
	}
}

func TestDeadlineExceeded(t *testing.T) {
	conn, cleanup := newTestEnv(t)
	defer cleanup()
	client := pb.NewUserServiceClient(conn)
	// 预热连接：确保下面的超时来自"调用级 deadline"而非"建连超时"
	ctx0, cancel0 := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel0()
	if _, err := client.GetUser(ctx0, &pb.GetUserRequest{Id: 1}); err != nil {
		t.Fatalf("warmup: %v", err)
	}
	// 服务端对 id=100 睡 150ms；客户端 deadline 20ms → 必然 codes.DeadlineExceeded
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	_, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 100})
	if err == nil {
		t.Fatal("超时调用应报错")
	}
	if status.Code(err) != codes.DeadlineExceeded {
		t.Fatalf("code=%v, want DeadlineExceeded", status.Code(err))
	}
}

// TestInterceptorsActive 验证服务端拦截器在链上生效：timeout 拦截器（2s）存在时，
// 正常调用不被误杀（回归保护）；logging 拦截器由日志输出人工观察
func TestInterceptorsActive(t *testing.T) {
	conn, cleanup := newTestEnv(t)
	defer cleanup()
	client := pb.NewUserServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if _, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 2}); err != nil {
		t.Fatalf("拦截器链不应干扰正常调用: %v", err)
	}
}
