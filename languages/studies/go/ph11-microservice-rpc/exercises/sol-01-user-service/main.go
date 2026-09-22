// 来源：ph11-microservice-rpc 练习 1 参考实现 —— 用户服务（net/rpc + JSON-RPC）
// 一句话说明：roadmap「用户服务」练习——用标准库 net/rpc 定义用户服务（GetUser/ListUsers/AddUser），
// 用 net/rpc/jsonrpc 编码，自定义服务名注册，覆盖方法签名约束、错误透传与并发安全。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **58.3%**（go1.25.6，5 个用例全过，含错误路径与服务名校验）
package main

import (
	"errors"
	"fmt"
	"log"
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"sort"
	"sync"
)

// User 载荷：字段必须可导出（JSON/Gob 都不序列化小写字段）
type User struct {
	ID    int64
	Name  string
	Email string
}

// 每对方法一组 Args/Reply（可导出）
type GetUserArgs struct{ ID int64 }
type GetUserReply struct{ User *User }

type ListUsersArgs struct{}
type ListUsersReply struct{ Users []*User }

type AddUserArgs struct {
	Name  string
	Email string
}
type AddUserReply struct{ ID int64 }

// UserService 服务对象
type UserService struct {
	mu    sync.Mutex
	next  int64
	users map[int64]*User
}

func NewUserService() *UserService {
	return &UserService{next: 0, users: map[int64]*User{}}
}

// GetUser 签名约束：func (t *T) MethodName(arg T1, reply *T2) error
func (s *UserService) GetUser(args *GetUserArgs, reply *GetUserReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.users[args.ID]
	if !ok {
		return errors.New("user not found") // 错误以字符串透传给客户端
	}
	reply.User = u
	return nil
}

func (s *UserService) ListUsers(args *ListUsersArgs, reply *ListUsersReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
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
	s.users[s.next] = &User{ID: s.next, Name: args.Name, Email: args.Email}
	return nil
}

// startServer 起 JSON-RPC 用户服务（随机端口），注册名为显式指定的 "UserService"
func startServer() (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer()
	if err := server.RegisterName("UserService", NewUserService()); err != nil { // 显式服务名
		lis.Close()
		return "", nil, err
	}
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go server.ServeCodec(jsonrpc.NewServerCodec(conn))
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

	client, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	var ar AddUserReply
	if err := client.Call("UserService.AddUser", &AddUserArgs{Name: "alice", Email: "alice@tenet.dev"}, &ar); err != nil {
		log.Fatal(err)
	}
	var gr GetUserReply
	if err := client.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetUser(%d) -> %+v\n", ar.ID, gr.User)

	var lr ListUsersReply
	if err := client.Call("UserService.ListUsers", &ListUsersArgs{}, &lr); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("ListUsers -> %d 个用户\n", len(lr.Users))

	var nr GetUserReply
	err = client.Call("UserService.GetUser", &GetUserArgs{ID: 999}, &nr)
	fmt.Printf("GetUser(999) -> err=%q\n", err)
}
