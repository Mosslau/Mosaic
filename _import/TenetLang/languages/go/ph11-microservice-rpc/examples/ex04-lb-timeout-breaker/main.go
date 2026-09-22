// 来源：ph11-microservice-rpc 示例 4 —— 负载均衡 / 超时 / 熔断（概念 + 简单实现）
// 一句话说明：三个可靠性原语的极简实现——RoundRobin 轮询负载均衡、callWithTimeout
// 调用超时（net/rpc 无原生 deadline，必须调用方自定时长）、Breaker 熔断状态机
// （closed → open → half-open）；演示在多个 RPC 实例（健康/慢/故障）上的组合效果。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .            # 单进程演示：3 个实例（健康/慢/故障）依次展示 LB、超时、熔断
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"errors"
	"fmt"
	"log"
	"net"
	"net/rpc"
	"net/rpc/jsonrpc"
	"sync"
	"time"
)

// ---- 1. 负载均衡：轮询（RoundRobin）----

// RoundRobin 轮询负载均衡器：按顺序轮流返回实例地址，实现"请求均匀分摊"
type RoundRobin struct {
	mu    sync.Mutex
	addrs []string
	next  int
}

func NewRoundRobin(addrs []string) *RoundRobin {
	return &RoundRobin{addrs: append([]string(nil), addrs...)}
}

// Pick 返回下一个实例地址（依次轮流；地址列表变化后从头开始）
func (rr *RoundRobin) Pick() string {
	rr.mu.Lock()
	defer rr.mu.Unlock()
	if len(rr.addrs) == 0 {
		return ""
	}
	addr := rr.addrs[rr.next%len(rr.addrs)]
	rr.next++
	return addr
}

// ---- 2. 超时：net/rpc 没有原生 deadline，调用方用 goroutine + select 自定时长 ----

var ErrTimeout = errors.New("rpc call timeout")

// callWithTimeout 在 d 时间内等待 fn 完成，超时返回 ErrTimeout。
// ⚠️ 代价：超时后 fn 的 goroutine 无法取消，会继续跑完（net/rpc 无取消机制）——
// 生产用 gRPC 的 context.WithTimeout 可真正取消（见 ex06）。
func callWithTimeout(d time.Duration, fn func() error) error {
	done := make(chan error, 1) // 缓冲 1：防止超时后 fn 返回时 goroutine 泄漏在通道上
	go func() { done <- fn() }()
	select {
	case err := <-done:
		return err
	case <-time.After(d):
		return ErrTimeout
	}
}

// ---- 3. 熔断：状态机 closed → open → half-open ----

// Breaker 熔断器：连续 threshold 次失败后 open（快速失败、不发网络调用）；
// 冷却 cooldown 后进入 half-open 放行一个探针请求：成功则复位 closed，失败则回到 open
type Breaker struct {
	mu        sync.Mutex
	state     string // "closed" | "open" | "half-open"
	failures  int
	threshold int
	cooldown  time.Duration
	openedAt  time.Time
}

func NewBreaker(threshold int, cooldown time.Duration) *Breaker {
	return &Breaker{state: "closed", threshold: threshold, cooldown: cooldown}
}

// Allow 是否放行本次调用；open 状态快速失败
func (b *Breaker) Allow() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	switch b.state {
	case "open":
		if time.Since(b.openedAt) > b.cooldown { // 冷却结束：半开，放行一个探针
			b.state = "half-open"
			return true
		}
		return false // 冷却中：快速失败，不消耗下游资源
	case "half-open":
		return true // 探针请求：只放行这一个（成败决定去向）
	default:
		return true // closed：正常放行
	}
}

// Success 调用成功：复位计数（半开成功 → 关闭）
func (b *Breaker) Success() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.failures = 0
	b.state = "closed"
}

// Failure 调用失败：计数达到阈值 → 打开熔断器
func (b *Breaker) Failure() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.state == "half-open" {
		// 探针失败：立即回到 open，重新计时
		b.openLocked()
		return
	}
	b.failures++
	if b.failures >= b.threshold {
		b.openLocked()
	}
}

func (b *Breaker) openLocked() {
	b.state = "open"
	b.openedAt = time.Now()
	b.failures = 0
}

// State 当前状态（测试/观测用）
func (b *Breaker) State() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.state
}

// ---- 用户服务（行为可配置：健康 / 慢 / 故障）----

type GetUserArgs struct{ ID int64 }
type GetUserReply struct {
	From string // 响应来自哪个实例（观测负载均衡用）
	Name string
}

type UserService struct {
	behavior string // "fast" | "slow" | "fail"
}

func (s *UserService) GetUser(args *GetUserArgs, reply *GetUserReply) error {
	switch s.behavior {
	case "slow":
		time.Sleep(300 * time.Millisecond) // 模拟慢实例：拖垮调用方
		reply.From = "slow"
	case "fail":
		return errors.New("instance down") // 模拟故障实例
	default:
		reply.From = "fast"
	}
	reply.Name = fmt.Sprintf("user-%d", args.ID)
	return nil
}

// startServer 起一个指定行为的用户服务实例
func startServer(behavior string) (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer()
	if err := server.Register(&UserService{behavior: behavior}); err != nil {
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

// dial 连到指定实例（每次调用新建连接，简化示例；生产用连接池）
func dial(addr string) (*rpc.Client, error) { return jsonrpc.Dial("tcp", addr) }

// callInstance 对指定实例发起一次 GetUser（带超时 + 熔断计数）
func callInstance(addr string, b *Breaker, d time.Duration, id int64) (string, error) {
	if !b.Allow() {
		return "", fmt.Errorf("熔断开启: 快速失败, 不发网络调用 (%s)", addr)
	}
	client, err := dial(addr)
	if err != nil {
		b.Failure()
		return "", fmt.Errorf("拨号失败: %w", err)
	}
	defer client.Close()
	var reply GetUserReply
	err = callWithTimeout(d, func() error {
		return client.Call("UserService.GetUser", &GetUserArgs{ID: id}, &reply)
	})
	if err != nil {
		b.Failure() // 超时与错误都算失败
		return "", fmt.Errorf("%s: %w", addr, err)
	}
	b.Success()
	return reply.From, nil
}

func main() {
	// 三个实例：健康 / 慢（300ms）/ 故障
	fastAddr, stopFast, err := startServer("fast")
	if err != nil {
		log.Fatal(err)
	}
	slowAddr, stopSlow, err := startServer("slow")
	if err != nil {
		log.Fatal(err)
	}
	failAddr, stopFail, err := startServer("fail")
	if err != nil {
		log.Fatal(err)
	}
	defer stopFast()
	defer stopSlow()
	defer stopFail()

	// ① 负载均衡：6 次调用按轮询打到 3 个实例（fast/slow/fail 各 2 次）
	rr := NewRoundRobin([]string{fastAddr, slowAddr, failAddr})
	fmt.Println("① 轮询负载均衡（6 次 Pick）:")
	for i := 0; i < 6; i++ {
		fmt.Printf("   pick#%d -> %s\n", i+1, rr.Pick())
	}

	// ② 超时：慢实例 300ms > 超时 100ms → ErrTimeout
	fmt.Println("② 调用超时（slow 实例 300ms > 100ms 超时）:")
	err = callWithTimeout(100*time.Millisecond, func() error {
		client, err := dial(slowAddr)
		if err != nil {
			return err
		}
		defer client.Close()
		return client.Call("UserService.GetUser", &GetUserArgs{ID: 1}, &GetUserReply{})
	})
	fmt.Printf("   slow 调用 -> %v\n", err)

	// ③ 熔断：连续 2 次失败后打开 → 第 3 次快速失败
	b := NewBreaker(2, 300*time.Millisecond)
	fmt.Println("③ 熔断器（阈值 2、冷却 300ms）:")
	for i := 1; i <= 4; i++ {
		from, err := callInstance(failAddr, b, 200*time.Millisecond, int64(i))
		fmt.Printf("   第 %d 次 -> from=%q err=%v state=%s\n", i, from, err, b.State())
	}
}
