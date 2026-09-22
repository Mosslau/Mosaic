// 来源：ph11-microservice-rpc 示例 1 —— net/rpc 基础（Gob 编码）
// 一句话说明：标准库 net/rpc 的最小完整闭环：服务端 Register + 真实 TCP 监听 + Gob 二进制编码，
// 客户端 Dial 后同步 Call 与异步 Go 两种调用方式；覆盖方法签名约束、error 语义与并发安全。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .            # 单进程演示：程序内起 server，client 同步/异步调用并打印
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"errors"
	"fmt"
	"log"
	"net"
	"net/rpc"
	"sort"
	"sync"
)

// User 是 RPC 的载荷类型：字段必须可导出（Gob 编码不序列化小写字段）
type User struct {
	ID     int64
	Name   string
	Email  string
	Status int32 // 1=在线 2=离线
}

// 参数与返回值类型：每个 RPC 方法一对 Args/Reply 结构体（可导出）
type GetUserArgs struct{ ID int64 }
type GetUserReply struct{ User *User }

type ListUsersArgs struct{}
type ListUsersReply struct{ Users []*User }

type AddUserArgs struct {
	Name  string
	Email string
}
type AddUserReply struct{ ID int64 }

// UserService 是 RPC 服务对象：方法需满足 net/rpc 的签名约束（见下）
type UserService struct {
	mu    sync.Mutex
	next  int64
	users map[int64]*User
}

func NewUserService() *UserService {
	return &UserService{
		next:  0,
		users: map[int64]*User{},
	}
}

// GetUser 签名约束：func (t *T) MethodName(arg T1, reply *T2) error
// 方法名与参数/返回值类型都必须可导出；reply 必须是结构体指针；返回 error 表示调用失败
func (s *UserService) GetUser(args *GetUserArgs, reply *GetUserReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.users[args.ID]
	if !ok {
		// net/rpc 的错误只会以"字符串"传回客户端——没有 gRPC 那种状态码
		return errors.New("user not found")
	}
	reply.User = u // 通过指针回填结果，函数本身返回 nil 表示成功
	return nil
}

func (s *UserService) ListUsers(args *ListUsersArgs, reply *ListUsersReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	reply.Users = reply.Users[:0]
	for _, u := range s.users {
		reply.Users = append(reply.Users, u)
	}
	sort.Slice(reply.Users, func(i, j int) bool { return reply.Users[i].ID < reply.Users[j].ID })
	return nil
}

func (s *UserService) AddUser(args *AddUserArgs, reply *AddUserReply) error {
	if args.Name == "" {
		return errors.New("name required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.next++
	reply.ID = s.next
	s.users[s.next] = &User{ID: s.next, Name: args.Name, Email: args.Email, Status: 1}
	return nil
}

// startServer 在 127.0.0.1 的随机端口起一个 rpc server，返回地址与停止函数
func startServer() (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer() // 独立 server 实例：rpc.Register 注册到全局默认 server，
	// 测试里多次起 server 会冲突；显式实例便于控制生命周期
	svc := NewUserService()
	if err := server.Register(svc); err != nil { // 默认服务名 = 类型名 "UserService"
		lis.Close()
		return "", nil, err
	}
	go func() { // 每来一个连接，起一个 goroutine 用 Gob 编解码服务
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go server.ServeConn(conn) // ServeConn 默认 Gob 编码（二进制、不可读）
		}
	}()
	return lis.Addr().String(), func() { lis.Close() }, nil
}

func main() {
	addr, stop, err := startServer()
	if err != nil {
		log.Fatal(err)
	}
	defer stop()

	client, err := rpc.Dial("tcp", addr) // Dial = 建连接 + Gob 客户端
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	// ① 同步调用：Call 阻塞直到返回（内部转 Go + 等 done）
	var ar AddUserReply
	if err := client.Call("UserService.AddUser", &AddUserArgs{Name: "alice", Email: "alice@tenet.dev"}, &ar); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("AddUser -> id=%d\n", ar.ID)

	var gr GetUserReply
	if err := client.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetUser -> %+v\n", gr.User)

	// ② 异步调用：Go 立即返回 *Call，done 通道收结果
	done := make(chan *rpc.Call, 1)
	client.Go("UserService.ListUsers", &ListUsersArgs{}, &ListUsersReply{}, done)
	call := <-done // 等异步调用完成
	if call.Error != nil {
		log.Fatal(call.Error)
	}
	fmt.Printf("ListUsers -> %d 个用户\n", len(call.Reply.(*ListUsersReply).Users))

	// ③ 错误路径：错误字符串原样传回（net/rpc 无状态码，只能按字符串/类型判断）
	var nr GetUserReply
	err = client.Call("UserService.GetUser", &GetUserArgs{ID: 999}, &nr)
	fmt.Printf("GetUser(999) -> err=%q\n", err)
	fmt.Println("演示结束")
}
