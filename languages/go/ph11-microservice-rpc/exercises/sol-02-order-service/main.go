// 来源：ph11-microservice-rpc 练习 2 参考实现 —— 订单服务（幂等下单 + 超时重试）
// 一句话说明：roadmap「订单服务」练习——服务端按幂等键（IdempotencyKey）去重：
// 同一 key 重复下单返回同一订单、不重复入库；客户端带超时调用 + 瞬时失败自动重试
// （"重试要考虑幂等"必会概念的落地：只有幂等接口才能安全重试）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **70.5%**（go1.25.6，9 个用例全过，含幂等/重试/超时/耗尽）
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

// ---- 订单服务 ----

type Order struct {
	ID             int64 // 订单号（服务端生成）
	UserID         int64
	Amount         int64
	IdempotencyKey string
	Status         string // "created"
}

type CreateOrderArgs struct {
	UserID         int64
	Amount         int64
	IdempotencyKey string // 幂等键：同一 key 重复提交只生效一次
}
type CreateOrderReply struct {
	Order *Order
}

type GetOrderArgs struct{ ID int64 }
type GetOrderReply struct{ Order *Order }

// OrderService 幂等下单：key → 订单 的映射保证"重复请求返回同一结果"
type OrderService struct {
	mu    sync.Mutex
	next  int64
	byID  map[int64]*Order
	byKey map[string]*Order
}

func NewOrderService() *OrderService {
	return &OrderService{
		next:  0,
		byID:  map[int64]*Order{},
		byKey: map[string]*Order{},
	}
}

// CreateOrder 幂等创建：已存在该 key → 直接返回已有订单（不重复入库）
func (s *OrderService) CreateOrder(args *CreateOrderArgs, reply *CreateOrderReply) error {
	if args.Amount <= 0 {
		return errors.New("amount must be positive")
	}
	if args.IdempotencyKey == "" {
		return errors.New("idempotency key required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if o, ok := s.byKey[args.IdempotencyKey]; ok {
		reply.Order = o // 幂等命中：返回第一次创建的订单
		return nil
	}
	s.next++
	o := &Order{
		ID:             s.next,
		UserID:         args.UserID,
		Amount:         args.Amount,
		IdempotencyKey: args.IdempotencyKey,
		Status:         "created",
	}
	s.byID[o.ID] = o
	s.byKey[o.IdempotencyKey] = o
	reply.Order = o
	return nil
}

func (s *OrderService) GetOrder(args *GetOrderArgs, reply *GetOrderReply) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	o, ok := s.byID[args.ID]
	if !ok {
		return errors.New("order not found")
	}
	reply.Order = o
	return nil
}

// ---- 客户端：超时 + 重试 ----

var ErrTimeout = errors.New("rpc call timeout")

// callWithTimeout 在 d 内等待 fn 完成，超时返回 ErrTimeout
// （net/rpc 无原生 deadline 与取消，超时后 fn 的 goroutine 会继续跑完——生产用 gRPC context）
func callWithTimeout(d time.Duration, fn func() error) error {
	done := make(chan error, 1)
	go func() { done <- fn() }()
	select {
	case err := <-done:
		return err
	case <-time.After(d):
		return ErrTimeout
	}
}

// callWithRetry 瞬时失败自动重试 attempts 次（每次退避 backoff）。
// ⚠️ 只有幂等接口才能安全重试——本服务的幂等键让"重试"与"重复提交"等价（见测试）。
func callWithRetry(attempts int, backoff time.Duration, fn func() error) error {
	var err error
	for i := 0; i < attempts; i++ {
		if err = fn(); err == nil {
			return nil
		}
		if i < attempts-1 {
			time.Sleep(backoff)
		}
	}
	return fmt.Errorf("重试 %d 次仍失败: %w", attempts, err)
}

// createOrder 客户端下单：超时 500ms + 最多 3 次重试（幂等键保证重试安全）
func createOrder(client *rpc.Client, args *CreateOrderArgs) (*Order, error) {
	var reply CreateOrderReply
	err := callWithRetry(3, 50*time.Millisecond, func() error {
		return callWithTimeout(500*time.Millisecond, func() error {
			return client.Call("OrderService.CreateOrder", args, &reply)
		})
	})
	if err != nil {
		return nil, err
	}
	return reply.Order, nil
}

// ---- 服务启动 ----

func startServer() (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	server := rpc.NewServer()
	if err := server.RegisterName("OrderService", NewOrderService()); err != nil {
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

	// 同一幂等键下两次下单 → 同一订单
	key := "order-2025-0001"
	o1, err := createOrder(client, &CreateOrderArgs{UserID: 1, Amount: 100, IdempotencyKey: key})
	if err != nil {
		log.Fatal(err)
	}
	o2, err := createOrder(client, &CreateOrderArgs{UserID: 1, Amount: 100, IdempotencyKey: key})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("第一次下单 -> order#%d\n第二次同 key -> order#%d（幂等命中，同一订单）\n", o1.ID, o2.ID)

	var gr GetOrderReply
	if err := client.Call("OrderService.GetOrder", &GetOrderArgs{ID: o1.ID}, &gr); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetOrder(%d) -> 金额=%d 状态=%s\n", gr.Order.ID, gr.Order.Amount, gr.Order.Status)
}
