package device

// 网关侧弹性客户端：把阶段三个可靠性原语组合成一次调用——
// 服务发现（registry.Discover）→ 负载均衡（lb.RoundRobin，跳过熔断中的实例）→
// 超时（调用级 deadline）→ 熔断记账（breaker）→ 瞬时失败换实例重试。

import (
	"errors"
	"fmt"
	"net/rpc/jsonrpc"
	"strings"
	"sync"
	"time"

	"tenetlang/go/ph11-microservice-rpc/project/internal/breaker"
	"tenetlang/go/ph11-microservice-rpc/project/internal/lb"
	"tenetlang/go/ph11-microservice-rpc/project/internal/registry"
)

// 可重试的瞬时错误
var (
	ErrTimeout     = errors.New("rpc call timeout")
	ErrBreakerOpen = errors.New("熔断开启: 快速失败")
	ErrNoInstance  = errors.New("没有可用实例（全部熔断或未注册）")
)

// Client 弹性客户端：每个实例一个熔断器（状态跨刷新保留）
type Client struct {
	reg      *registry.Client
	timeout  time.Duration
	retries  int
	mu       sync.Mutex
	lb       *lb.RoundRobin
	breakers map[string]*breaker.Breaker
}

// NewClient reg 为注册中心客户端；timeout 单次调用超时；retries 瞬时失败重试次数
func NewClient(reg *registry.Client, timeout time.Duration, retries int) *Client {
	return &Client{
		reg:      reg,
		timeout:  timeout,
		retries:  retries,
		breakers: make(map[string]*breaker.Breaker),
	}
}

// Refresh 重新发现设备服务实例并重建轮询列表；熔断器按地址保留状态
func (c *Client) Refresh() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	addrs, err := c.reg.Discover(ServiceName)
	if err != nil {
		return err
	}
	for _, a := range addrs {
		if _, ok := c.breakers[a]; !ok {
			c.breakers[a] = breaker.New(2, 500*time.Millisecond)
		}
	}
	c.lb = lb.New(addrs)
	return nil
}

// pick 挑一个实例（轮询）；熔断中的实例由 callInstance 的 Allow() 快速失败——
// 不发起网络调用即返回，等价于"把熔断中的实例移出调度"，同时保留半开探针的自愈路径
func (c *Client) pick() string {
	if c.lb == nil {
		return ""
	}
	return c.lb.Pick()
}

// isTransport 传输层失败（拨号失败/连接断开）：服务不可达，计入熔断失败
func isTransport(err error) bool {
	if err == nil {
		return false
	}
	msg := err.Error()
	return strings.Contains(msg, "connection refused") ||
		strings.Contains(msg, "no such host") ||
		strings.Contains(msg, "EOF") ||
		strings.Contains(msg, "connection reset")
}

// callInstance 对指定实例发起一次 JSON-RPC 调用：先过熔断（open 快速失败、不发网络调用），
// 再带超时调用，最后记账。熔断只记"服务不可达"（传输层失败/超时）；服务正常响应但业务报错
// （如限流）不算熔断失败。冷却后半开放行的探针在此自然发生：成功 → closed 自愈。
func (c *Client) callInstance(addr, method string, arg, reply any) error {
	c.mu.Lock()
	b, ok := c.breakers[addr]
	if !ok {
		b = breaker.New(2, 500*time.Millisecond)
		c.breakers[addr] = b
	}
	c.mu.Unlock()
	if !b.Allow() {
		return fmt.Errorf("%w: %s", ErrBreakerOpen, addr)
	}
	done := make(chan error, 1)
	go func() { // ⚠️ net/rpc 无取消机制：超时后本 goroutine 会继续跑完（生产用 gRPC context）
		conn, err := jsonrpc.Dial("tcp", addr)
		if err != nil {
			done <- err
			return
		}
		defer conn.Close()
		done <- conn.Call(method, arg, reply)
	}()
	select {
	case err := <-done:
		if isTransport(err) {
			b.Failure()
		} else {
			b.Success()
		}
		return err
	case <-time.After(c.timeout):
		b.Failure()
		return fmt.Errorf("%w: %s", ErrTimeout, addr)
	}
}

// isTransient 瞬时错误才值得重试（超时/连接失败/熔断中/限流——换实例可能成功）；业务错误不重试
func isTransient(err error) bool {
	return errors.Is(err, ErrTimeout) ||
		errors.Is(err, ErrBreakerOpen) ||
		strings.Contains(err.Error(), "connection refused") ||
		strings.Contains(err.Error(), "no such host") ||
		strings.Contains(err.Error(), "rate limited")
}

// call 完整调用链：挑实例 → 调用 → 瞬时失败换下一个实例重试（最多 retries 次）。
// 注意：重试之间不重建 LB——Refresh 会重置轮询位置，导致每次都打到同一个实例；
// 新实例上线靠调用方周期 Refresh（见 cmd/gateway 的每轮 Refresh）。
func (c *Client) call(method string, arg, reply any) error {
	var lastErr error
	for attempt := 0; attempt <= c.retries; attempt++ {
		c.mu.Lock()
		addr := c.pick()
		c.mu.Unlock()
		if addr == "" {
			if c.lb == nil { // 从未发现过实例：先刷新一次再试
				if err := c.Refresh(); err != nil {
					lastErr = err
					continue
				}
			}
			return ErrNoInstance
		}
		err := c.callInstance(addr, method, arg, reply)
		if err == nil {
			return nil
		}
		lastErr = err
		if !isTransient(err) {
			return err
		}
		// RR 已在 Pick 时前进：下一次循环自然换到下一个实例
	}
	return fmt.Errorf("重试 %d 次仍失败: %w", c.retries, lastErr)
}

// Report 上报设备状态（幂等语义：同一设备重复上报只更新最新值）
func (c *Client) Report(st *Status) error {
	return c.call(MethodReport, &ReportArgs{Status: *st}, &ReportReply{})
}

// GetStatus 查询设备最新状态（经负载均衡落到某一个实例）
func (c *Client) GetStatus(deviceID string) (*Status, error) {
	var reply GetReply
	if err := c.call(MethodGet, &GetArgs{DeviceID: deviceID}, &reply); err != nil {
		return nil, err
	}
	return reply.Status, nil
}

// InstanceStatus 某个实例上的查询结果（跨实例汇总用）
type InstanceStatus struct {
	Addr   string
	Status *Status
}

// GetAll 向全部已发现实例查询设备状态（fan-out 汇总）。
// 意义：本演示各实例各自持有内存状态（无共享存储），LB 把上报分摊到不同实例后，
// "最新状态"可能只存在于某个实例——生产方案是把状态落到共享存储（ph10 数据库）
// 或做数据同步，本方法演示"跨实例查询"这类兜底手段。
func (c *Client) GetAll(deviceID string) ([]InstanceStatus, error) {
	c.mu.Lock()
	addrs := c.lbAddrs()
	c.mu.Unlock()
	var results []InstanceStatus
	for _, addr := range addrs {
		var reply GetReply
		if err := c.callInstance(addr, MethodGet, &GetArgs{DeviceID: deviceID}, &reply); err != nil {
			continue // 该实例无此设备/不可达：跳过（不可达已计入其熔断器）
		}
		results = append(results, InstanceStatus{Addr: addr, Status: reply.Status})
	}
	if len(results) == 0 {
		return nil, ErrNotFound
	}
	return results, nil
}

// lbAddrs 当前负载均衡列表里的全部地址（仅观测用）
func (c *Client) lbAddrs() []string {
	if c.lb == nil {
		return nil
	}
	return c.lb.Addrs()
}
