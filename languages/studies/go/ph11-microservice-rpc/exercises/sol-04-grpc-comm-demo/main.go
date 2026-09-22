// 来源：ph11-microservice-rpc 练习 4 参考实现 —— gRPC 通信 demo（两个服务互相调用）
// 一句话说明：roadmap「gRPC 通信 demo」练习——订单服务（A）与用户服务（B）各自独立进程，
// A 的 GetOrder 内部以 gRPC client 调用 B 的 GetUser 组装 user_name；用 status.Code 处理
// B 的 NotFound（用户已删）并把错误码透传给上层调用方。
// 验证环境：go1.25.6（darwin/arm64），工具链：protoc 29.3 + protoc-gen-go v1.36.6 +
// protoc-gen-go-grpc v1.5.1，依赖：grpc-go v1.72.0 + protobuf v1.36.6（GOPROXY=goproxy.cn 拉取）
// 运行：
//
//	go test -v ./...          # 进程内起 A、B 两个服务，验证组装与错误码透传
//	go run .
//
// 验证状态：已验证（本机实际生成 pb 代码并跑通全部测试）
// 覆盖率：go test -cover 实测 **41.7%**（go1.25.6，main 包 4 个用例全过；proto 为生成代码不计量）
package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	pb "tenetlang/go/ph11-microservice-rpc/exercises/sol-04-grpc-comm-demo/proto"
)

// ---- 服务 B：用户服务 ----

type userServer struct {
	pb.UnimplementedUserServiceServer
	users map[int64]*pb.User
}

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.User, error) {
	u, ok := s.users[req.Id]
	if !ok {
		return nil, status.Error(codes.NotFound, "user not found")
	}
	return u, nil
}

// ---- 服务 A：订单服务（内部调用用户服务 B）----

type orderServer struct {
	pb.UnimplementedOrderServiceServer
	orders map[int64]*pb.Order
	// 对服务 B 的客户端（依赖注入，测试可替换/指向任意地址）
	userClient pb.UserServiceClient
}

// GetOrder 组装响应：查订单 → 调用户服务 B 拿用户名 → 组装完整 Order
func (s *orderServer) GetOrder(ctx context.Context, req *pb.GetOrderRequest) (*pb.Order, error) {
	o, ok := s.orders[req.Id]
	if !ok {
		return nil, status.Error(codes.NotFound, "order not found")
	}
	// 服务间调用：RPC 必须有超时（必会概念）——调用级 context.WithTimeout
	uctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	u, err := s.userClient.GetUser(uctx, &pb.GetUserRequest{Id: o.UserId})
	if err != nil {
		// B 的 NotFound 原样透传：上层客户端用 status.Code(err) 就能区分"订单没有"与"用户没有"
		return nil, err
	}
	return &pb.Order{
		Id:       o.Id,
		UserId:   o.UserId,
		UserName: u.Name,
		Amount:   o.Amount,
	}, nil
}

// ---- 服务启动 ----

func startGRPCServer(addr string, register func(s *grpc.Server)) (realAddr string, stop func(), err error) {
	lis, err := net.Listen("tcp", addr)
	if err != nil {
		return "", nil, err
	}
	s := grpc.NewServer()
	register(s)
	go func() { _ = s.Serve(lis) }()
	return lis.Addr().String(), s.Stop, nil
}

func main() {
	// 服务 B（用户服务，随机端口）
	bAddr, stopB, err := startGRPCServer("127.0.0.1:0", func(s *grpc.Server) {
		pb.RegisterUserServiceServer(s, &userServer{users: map[int64]*pb.User{
			1: {Id: 1, Name: "alice", Email: "alice@tenet.dev"},
			2: {Id: 2, Name: "bob", Email: "bob@tenet.dev"},
		}})
	})
	if err != nil {
		log.Fatal(err)
	}
	defer stopB()

	// 服务 A（订单服务），注入指向 B 的客户端
	bConn, err := grpc.NewClient(bAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatal(err)
	}
	defer bConn.Close()
	aAddr, stopA, err := startGRPCServer("127.0.0.1:0", func(s *grpc.Server) {
		pb.RegisterOrderServiceServer(s, &orderServer{
			orders: map[int64]*pb.Order{
				100: {Id: 100, UserId: 1, Amount: 200},
				101: {Id: 101, UserId: 99, Amount: 300}, // UserId 99 在用户服务中不存在
			},
			userClient: pb.NewUserServiceClient(bConn),
		})
	})
	if err != nil {
		log.Fatal(err)
	}
	defer stopA()

	// 客户端只与订单服务 A 交互
	aConn, err := grpc.NewClient(aAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatal(err)
	}
	defer aConn.Close()
	client := pb.NewOrderServiceClient(aConn)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	o, err := client.GetOrder(ctx, &pb.GetOrderRequest{Id: 100})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetOrder(100) -> 订单#%d 用户#%d(%s) 金额=%d（A 调 B 组装）\n", o.Id, o.UserId, o.UserName, o.Amount)

	_, err = client.GetOrder(ctx, &pb.GetOrderRequest{Id: 101})
	fmt.Printf("GetOrder(101) -> code=%v msg=%q（B 的 NotFound 透传）\n", status.Code(err), status.Convert(err).Message())
}
