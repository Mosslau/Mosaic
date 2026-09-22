// 来源：ph11-microservice-rpc 示例 6 —— gRPC / protobuf 生态（一元 + 服务端流 + 拦截器）
// 一句话说明：生产级 RPC 生态的落地——.proto 定义接口契约 → protoc 生成 Go 代码 →
// gRPC server/client（一元 + 服务端流）→ 拦截器挂日志与超时。
// 与示例 1~5 的 net/rpc 是同一套用户服务语义，方便对照"标准库最小实现 vs 生产生态"。
// 验证环境：go1.25.6（darwin/arm64），工具链：protoc 29.3 + protoc-gen-go v1.36.6 +
// protoc-gen-go-grpc v1.5.1，依赖：grpc-go v1.72.0 + protobuf v1.36.6（GOPROXY=goproxy.cn 拉取）
// 运行：
//
//	go test -v ./...          # 进程内起 server + client，覆盖一元/流式/错误码/超时/拦截器
//	go run .                  # 单进程演示：起 server 于 127.0.0.1:52051，client 调用并打印
//
// 验证状态：已验证（本机实际生成 pb 代码并跑通全部测试，测完端口已清理）
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
	pb "tenetlang/go/ph11-microservice-rpc/examples/ex06-grpc-ecosystem/proto"
)

// ---- 服务端 ----

// userServer 实现 pb.UserServiceServer 接口；必须嵌入 UnimplementedUserServiceServer，
// proto 后续新增方法时旧实现不会编译失败（这是 gRPC 的兼容设计）
type userServer struct {
	pb.UnimplementedUserServiceServer
	users map[int64]*pb.User
}

func newUserServer() *userServer {
	return &userServer{users: map[int64]*pb.User{
		1: {Id: 1, Name: "alice", Email: "alice@tenet.dev", Status: 1},
		2: {Id: 2, Name: "bob", Email: "bob@tenet.dev", Status: 2},
	}}
}

// GetUser 一元 RPC：错误用 status.Error 携带 gRPC 标准错误码（跨服务可编程语义）
func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
	if req.Id == 100 {
		// 模拟慢业务逻辑（测试超时用：150ms 远大于测试的 20ms 客户端 deadline）
		time.Sleep(150 * time.Millisecond)
	}
	u, ok := s.users[req.Id]
	if !ok {
		return nil, status.Error(codes.NotFound, "user not found")
	}
	return &pb.GetUserResponse{User: u}, nil
}

// ListUsers 服务端流式 RPC：stream.Send 逐条推送，遍历完 return nil 即正常结束
func (s *userServer) ListUsers(req *pb.ListUsersRequest, stream pb.UserService_ListUsersServer) error {
	for _, id := range req.Ids {
		if u, ok := s.users[id]; ok {
			if err := stream.Send(u); err != nil {
				return err
			}
		}
	}
	return nil
}

// ---- 拦截器（与 ph09 HTTP middleware 同构的 gRPC 中间件）----

// loggingUnary 服务端拦截器：记录方法名、耗时与错误
func loggingUnary(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
	start := time.Now()
	resp, err := handler(ctx, req) // 放行到下一层（下一个拦截器 / 真正的 handler）
	log.Printf("[server] %s 耗时=%v err=%v", info.FullMethod, time.Since(start), err)
	return resp, err
}

// timeoutUnary 服务端拦截器：给请求 context 强加 deadline（必会概念"RPC 必须有超时"）
func timeoutUnary(d time.Duration) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		ctx, cancel := context.WithTimeout(ctx, d)
		defer cancel()
		return handler(ctx, req)
	}
}

// startGRPCServer 在指定地址起 gRPC server，返回实际监听地址与停止函数
// （addr 传 "127.0.0.1:0" 时由内核分配随机端口，测试用）
func startGRPCServer(addr string) (realAddr string, stop func(), err error) {
	lis, err := net.Listen("tcp", addr)
	if err != nil {
		return "", nil, err
	}
	// ChainUnaryInterceptor：按传入顺序包裹（logging 在外、timeout 在内）
	s := grpc.NewServer(grpc.ChainUnaryInterceptor(loggingUnary, timeoutUnary(2*time.Second)))
	pb.RegisterUserServiceServer(s, newUserServer())
	go func() { _ = s.Serve(lis) }()
	return lis.Addr().String(), s.Stop, nil
}

// newClient 建 gRPC 客户端连接（本地调试用 insecure 凭据，生产必须 TLS——属 ph12）
func newClient(addr string) (*grpc.ClientConn, error) {
	return grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
}

func main() {
	const addr = "127.0.0.1:52051"
	_, stop, err := startGRPCServer(addr)
	if err != nil {
		log.Fatal(err)
	}
	defer stop()
	time.Sleep(100 * time.Millisecond) // 等服务就绪

	conn, err := newClient(addr)
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()
	client := pb.NewUserServiceClient(conn)

	// ① 一元 RPC：调用级超时用 context.WithTimeout（超时返回 codes.DeadlineExceeded）
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	u, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 1})
	if err != nil {
		log.Fatalf("GetUser: %v", err)
	}
	fmt.Printf("① GetUser(1) -> id=%d name=%s status=%d\n", u.User.Id, u.User.Name, u.User.Status)

	// ② 错误码：status.Code(err) 取 gRPC 错误码做决策（重试/降级/报错）
	_, err = client.GetUser(ctx, &pb.GetUserRequest{Id: 999})
	fmt.Printf("② GetUser(999) -> code=%v msg=%q\n", status.Code(err), status.Convert(err).Message())

	// ③ 服务端流式 RPC：stream.Recv 循环读到 io.EOF 即流结束
	stream, err := client.ListUsers(ctx, &pb.ListUsersRequest{Ids: []int64{1, 2, 3}})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Print("③ ListUsers([1,2,3]) -> ")
	for {
		msg, err := stream.Recv()
		if err != nil { // 流结束 = io.EOF（errors.Is 判断）
			break
		}
		fmt.Printf("%s ", msg.Name)
	}
	fmt.Println()
}
