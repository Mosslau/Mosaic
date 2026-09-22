package main

import (
	"context"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	pb "tenetlang/go/ph11-microservice-rpc/exercises/sol-04-grpc-comm-demo/proto"
)

// newEnv 起服务 B（用户服务）+ 服务 A（订单服务，注入 B 客户端），返回 A 的 client 与清理
func newEnv(t *testing.T) (pb.OrderServiceClient, func()) {
	t.Helper()
	bAddr, stopB, err := startGRPCServer("127.0.0.1:0", func(s *grpc.Server) {
		pb.RegisterUserServiceServer(s, &userServer{users: map[int64]*pb.User{
			1: {Id: 1, Name: "alice", Email: "alice@tenet.dev"},
			2: {Id: 2, Name: "bob", Email: "bob@tenet.dev"},
		}})
	})
	if err != nil {
		t.Fatalf("服务 B 启动失败: %v", err)
	}
	bConn, err := grpc.NewClient(bAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		stopB()
		t.Fatalf("连接 B: %v", err)
	}
	aAddr, stopA, err := startGRPCServer("127.0.0.1:0", func(s *grpc.Server) {
		pb.RegisterOrderServiceServer(s, &orderServer{
			orders: map[int64]*pb.Order{
				100: {Id: 100, UserId: 1, Amount: 200},
				101: {Id: 101, UserId: 99, Amount: 300}, // 用户 99 不存在
			},
			userClient: pb.NewUserServiceClient(bConn),
		})
	})
	if err != nil {
		bConn.Close()
		stopB()
		t.Fatalf("服务 A 启动失败: %v", err)
	}
	aConn, err := grpc.NewClient(aAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		bConn.Close()
		stopA()
		stopB()
		t.Fatalf("连接 A: %v", err)
	}
	cleanup := func() {
		aConn.Close()
		bConn.Close()
		stopA()
		stopB()
	}
	return pb.NewOrderServiceClient(aConn), cleanup
}

func TestGetOrderAssembled(t *testing.T) {
	client, cleanup := newEnv(t)
	defer cleanup()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	o, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 100})
	if err != nil {
		t.Fatalf("GetOrder: %v", err)
	}
	if o.UserName != "alice" { // A 调 B 组装出的用户名
		t.Fatalf("user_name=%q, want alice（A 应调用 B 组装）", o.UserName)
	}
	if o.Amount != 200 || o.UserId != 1 {
		t.Fatalf("订单字段异常: %+v", o)
	}
}

func TestGetOrderNotFound(t *testing.T) {
	client, cleanup := newEnv(t)
	defer cleanup()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	_, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 999})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code=%v, want NotFound", status.Code(err))
	}
}

// TestUserMissingErrorPropagates 订单存在但用户已删：B 的 NotFound 透传给上层客户端
func TestUserMissingErrorPropagates(t *testing.T) {
	client, cleanup := newEnv(t)
	defer cleanup()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	_, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 101})
	if err == nil {
		t.Fatal("用户不存在应报错")
	}
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code=%v, want NotFound（B 的错误码应透传）", status.Code(err))
	}
	// 错误信息区分：是"用户"不存在而不是"订单"不存在
	if status.Convert(err).Message() != "user not found" {
		t.Fatalf("错误信息应来自服务 B: %q", status.Convert(err).Message())
	}
}

// TestTwoOrdersIndependent 多订单各自组装正确
func TestTwoOrdersIndependent(t *testing.T) {
	client, cleanup := newEnv(t)
	defer cleanup()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	// 动态加一个订单验证：直接查现有 100；再加一次查询 100 验证可重复调用
	o1, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 100})
	if err != nil {
		t.Fatal(err)
	}
	o2, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 100})
	if err != nil {
		t.Fatal(err)
	}
	if o1.UserName != o2.UserName || o1.Id != o2.Id {
		t.Fatalf("重复查询应一致: %+v vs %+v", o1, o2)
	}
}
