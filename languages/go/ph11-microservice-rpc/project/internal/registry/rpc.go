package registry

// 本文件把 Registry 暴露为 JSON-RPC 服务（cmd/registry 用它起独立进程）：
// 服务名 "Registry"，方法 Register/Heartbeat/Deregister/Discover——
// 语义与生产注册中心的客户端协议（etcd gRPC、Consul HTTP API）同构。

import (
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"time"
)

// Service 注册中心的 RPC 服务对象（方法签名满足 net/rpc 约束）
type Service struct {
	R *Registry
}

type RegArgs struct {
	Service string
	Addr    string
}

type EmptyReply struct{}

func (s *Service) Register(args *RegArgs, _ *EmptyReply) error {
	s.R.Register(args.Service, args.Addr)
	return nil
}

func (s *Service) Heartbeat(args *RegArgs, _ *EmptyReply) error {
	s.R.Heartbeat(args.Service, args.Addr)
	return nil
}

func (s *Service) Deregister(args *RegArgs, _ *EmptyReply) error {
	s.R.Deregister(args.Service, args.Addr)
	return nil
}

type DiscoverArgs struct {
	Service string
}

type DiscoverReply struct {
	Addrs []string
}

func (s *Service) Discover(args *DiscoverArgs, reply *DiscoverReply) error {
	reply.Addrs = s.R.Discover(args.Service)
	return nil
}

// ServeTCP 起注册中心的 JSON-RPC 服务（每连接一个 goroutine），返回实际地址与停止函数
func ServeTCP(addr string, ttl time.Duration) (realAddr string, stop func(), err error) {
	lis, err := net.Listen("tcp", addr)
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer()
	if err := server.RegisterName("Registry", &Service{R: New(ttl)}); err != nil {
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

// Client 注册中心的客户端（服务实例与网关用它登记/发现）
type Client struct {
	rc *rpc.Client
}

// Dial 连接注册中心
func Dial(addr string) (*Client, error) {
	rc, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		return nil, err
	}
	return &Client{rc: rc}, nil
}

func (c *Client) Register(service, addr string) error {
	return c.rc.Call("Registry.Register", &RegArgs{Service: service, Addr: addr}, &EmptyReply{})
}

func (c *Client) Heartbeat(service, addr string) error {
	return c.rc.Call("Registry.Heartbeat", &RegArgs{Service: service, Addr: addr}, &EmptyReply{})
}

func (c *Client) Deregister(service, addr string) error {
	return c.rc.Call("Registry.Deregister", &RegArgs{Service: service, Addr: addr}, &EmptyReply{})
}

func (c *Client) Discover(service string) ([]string, error) {
	var reply DiscoverReply
	err := c.rc.Call("Registry.Discover", &DiscoverArgs{Service: service}, &reply)
	return reply.Addrs, err
}

func (c *Client) Close() error { return c.rc.Close() }
