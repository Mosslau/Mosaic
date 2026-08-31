// 来源：ph11-microservice-rpc 示例 2 —— JSON-RPC 编解码（net/rpc/jsonrpc）
// 一句话说明：把示例 1 的用户服务换成 JSON-RPC 编码——wire 上是可读的 JSON 文本：
// 请求 {"method":"UserService.GetUser","params":[{...}],"id":N}，响应回显 id 并带 result/error；
// 本示例同时用"裸 TCP 手写 JSON-RPC 报文"演示 wire 格式本身（无需 Go client 也能调）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .            # 单进程演示：打印 JSON-RPC wire 报文 + Go client 调用结果
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"sort"
	"sync"
)

// ---- 与示例 1 相同的用户服务（载荷、参数/返回值类型完全复用）----

type User struct {
	ID     int64
	Name   string
	Email  string
	Status int32
}

type GetUserArgs struct{ ID int64 }
type GetUserReply struct{ User *User }

type ListUsersArgs struct{}
type ListUsersReply struct{ Users []*User }

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

func (s *UserService) GetUser(args *GetUserArgs, reply *GetUserReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.users[args.ID]
	if !ok {
		return errors.New("user not found")
	}
	reply.User = u
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

type AddUserArgs struct {
	Name  string
	Email string
}
type AddUserReply struct{ ID int64 }

// startJSONServer 起一个 JSON-RPC server：每个连接用 jsonrpc.NewServerCodec 服务
func startJSONServer() (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer()
	if err := server.Register(NewUserService()); err != nil {
		lis.Close()
		return "", nil, err
	}
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go server.ServeCodec(jsonrpc.NewServerCodec(conn)) // 与示例 1 的唯一区别：换编码器
		}
	}()
	return lis.Addr().String(), func() { lis.Close() }, nil
}

// rawJSONRPC 用裸 TCP 发送一行 JSON-RPC 报文并读回响应，展示 wire 格式本身
func rawJSONRPC(addr, method string, params any, id *uint64) (string, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return "", err
	}
	defer conn.Close()

	req := map[string]any{"method": method, "params": []any{params}}
	if id != nil {
		req["id"] = *id
	} // id 缺省 = JSON-RPC 通知（notification）：服务端不回复
	line, err := json.Marshal(req)
	if err != nil {
		return "", err
	}
	line = append(line, '\n')
	if _, err := conn.Write(line); err != nil {
		return "", err
	}
	resp, err := bufio.NewReader(conn).ReadBytes('\n')
	if err != nil {
		return "", err
	}
	return string(resp), nil
}

func main() {
	addr, stop, err := startJSONServer()
	if err != nil {
		log.Fatal(err)
	}
	defer stop()

	// ① Go client 先造数据，再用裸 TCP 看 JSON-RPC wire 格式（不依赖 Go client 也能调）
	client, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()
	var ar AddUserReply
	if err := client.Call("UserService.AddUser", &AddUserArgs{Name: "alice"}, &ar); err != nil {
		log.Fatal(err)
	}

	var id uint64 = 7
	resp, err := rawJSONRPC(addr, "UserService.GetUser", GetUserArgs{ID: ar.ID}, &id)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("wire 请求   : {\"method\":\"UserService.GetUser\",\"params\":[{\"ID\":%d}],\"id\":7}\n", ar.ID)
	fmt.Printf("wire 响应   : %s", resp)

	// ② Go client 走 jsonrpc.Dial（内部用同一 wire 协议）
	var gr GetUserReply
	if err := client.Call("UserService.GetUser", &GetUserArgs{ID: ar.ID}, &gr); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Go client   : GetUser(%d) -> %+v\n", ar.ID, gr.User)

	// ③ 错误响应：error 字段携带错误字符串
	resp, err = rawJSONRPC(addr, "UserService.GetUser", GetUserArgs{ID: 999}, &id)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("错误响应    : %s", resp)
}
