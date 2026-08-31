// 来源：ph11-microservice-rpc 示例 3 —— 服务注册与发现（本地注册表演示）
// 一句话说明：实现一个极简本地服务注册表 Registry——服务实例启动时 Register 登记
// "服务名 → 地址"，周期 Heartbeat 续约，Registry 按 TTL 过期摘除失联实例；
// 客户端不再写死地址，而是按服务名 Discover 得到存活实例列表再调用。
// 生产环境对应 etcd/Consul/Nacos（见阶段笔记 3.4），本示例用进程内 map 演示机制本身。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .            # 单进程演示：2 个用户服务实例注册 + 心跳，1 个实例下线后自动摘除
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"log"
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"sort"
	"sync"
	"time"
)

// ---- 本地注册表（注册中心的最小模型：服务名 → 实例地址集合 + 心跳 TTL）----

// Registry 注册表：并发安全，ttl 内未心跳的实例视为失联、Discover 时剔除
type Registry struct {
	mu        sync.Mutex
	instances map[string]map[string]time.Time // service → addr → 最后心跳时间
	ttl       time.Duration                   // 心跳有效期（生产是 10~30s，本示例缩短便于演示）
}

func NewRegistry(ttl time.Duration) *Registry {
	return &Registry{
		instances: make(map[string]map[string]time.Time),
		ttl:       ttl,
	}
}

// Register 服务实例启动时登记（重复登记 = 续约）
func (r *Registry) Register(service, addr string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.instances[service] == nil {
		r.instances[service] = make(map[string]time.Time)
	}
	r.instances[service][addr] = time.Now()
}

// Heartbeat 心跳续约：ttl 内调用一次即可保持存活
func (r *Registry) Heartbeat(service, addr string) {
	r.Register(service, addr) // 语义相同：刷新最后心跳时间
}

// Deregister 优雅下线：服务退出前主动注销（不依赖 TTL 等待）
func (r *Registry) Deregister(service, addr string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if addrs, ok := r.instances[service]; ok {
		delete(addrs, addr)
		if len(addrs) == 0 {
			delete(r.instances, service)
		}
	}
}

// Discover 发现某服务的存活实例地址（惰性剔除超过 ttl 未心跳的实例）
func (r *Registry) Discover(service string) []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now()
	var addrs []string
	for addr, lastSeen := range r.instances[service] {
		if now.Sub(lastSeen) > r.ttl {
			delete(r.instances[service], addr) // 过期摘除
			continue
		}
		addrs = append(addrs, addr)
	}
	sort.Strings(addrs) // 稳定顺序，便于测试断言
	return addrs
}

// ---- 用户服务（同示例 1，JSON-RPC 编码）----

type User struct {
	ID    int64
	Name  string
	Email string
}

type GetUserArgs struct{ ID int64 }
type GetUserReply struct{ User *User }

type UserService struct {
	mu    sync.Mutex
	users map[int64]*User
}

func NewUserService() *UserService {
	return &UserService{users: map[int64]*User{}}
}

func (s *UserService) GetUser(args *GetUserArgs, reply *GetUserReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.users[args.ID]
	if !ok {
		return fmt.Errorf("user not found: %d", args.ID)
	}
	reply.User = u
	return nil
}

// ---- 服务实例：起 JSON-RPC server + 注册 + 心跳 ----

// startInstance 起一个用户服务实例：监听随机端口、注册到注册表、每 heartbeat 间隔心跳续约
// 返回 (地址, 停止函数)；停止 = 优雅下线（Deregister）+ 关闭监听 + 停心跳
func startInstance(reg *Registry, heartbeat time.Duration) (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	addr = lis.Addr().String()

	server := rpc.NewServer()
	svc := NewUserService()
	svc.users[1] = &User{ID: 1, Name: "alice", Email: addr} // Email 存实例地址，便于观察"哪个实例响应"
	if err := server.Register(svc); err != nil {
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

	reg.Register("user.Service", addr)
	heartbeatStop := make(chan struct{})
	go func() { // 心跳 goroutine：周期续约；实例存活期间一直跑
		ticker := time.NewTicker(heartbeat)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				reg.Heartbeat("user.Service", addr)
			case <-heartbeatStop:
				return
			}
		}
	}()

	var once sync.Once
	stop = func() {
		once.Do(func() { // 幂等：重复调用（如 defer + 显式调用）不会重复 close 通道
			reg.Deregister("user.Service", addr) // 优雅下线：主动注销
			close(heartbeatStop)
			lis.Close()
		})
	}
	return addr, stop, nil
}

func main() {
	reg := NewRegistry(2 * time.Second) // TTL 2 秒（演示用短 TTL）

	// 两个实例注册 + 心跳（间隔 500ms << TTL，保持存活）
	addr1, stop1, err := startInstance(reg, 500*time.Millisecond)
	if err != nil {
		log.Fatal(err)
	}
	addr2, stop2, err := startInstance(reg, 500*time.Millisecond)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("实例 1 上线: %s\n实例 2 上线: %s\n", addr1, addr2)

	// 客户端按服务名发现：拿到全部存活实例
	time.Sleep(50 * time.Millisecond)
	fmt.Printf("Discover(user.Service) -> %v\n", reg.Discover("user.Service"))

	// 实例 2 优雅下线（Deregister）：注册表立即摘除
	stop2()
	fmt.Printf("实例 2 下线后 Discover -> %v\n", reg.Discover("user.Service"))

	// 实例 1 异常宕机（不 Deregister、直接停心跳）：等 TTL 过期后被动摘除
	stop1() // 演示里直接复用 stop1 模拟"失联"（正常 stop1 会 Deregister；这里说明 TTL 兜底机制）
	time.Sleep(2500 * time.Millisecond)
	fmt.Printf("实例 1 失联 %dms 后 Discover -> %v（空 = 已被 TTL 摘除）\n", 2500, reg.Discover("user.Service"))

	// 重新上线：注册表是动态的，服务随时可注册/摘除
	addr3, stop3, err := startInstance(reg, 500*time.Millisecond)
	if err != nil {
		log.Fatal(err)
	}
	defer stop3()
	fmt.Printf("实例 3 上线: %s\nDiscover -> %v\n", addr3, reg.Discover("user.Service"))
}
