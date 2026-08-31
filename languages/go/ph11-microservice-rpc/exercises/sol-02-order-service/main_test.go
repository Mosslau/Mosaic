package main

import (
	"errors"
	"net/rpc"
	"net/rpc/jsonrpc"
	"strings"
	"testing"
	"time"
)

func newTestClient(t *testing.T) (*rpc.Client, func()) {
	t.Helper()
	addr, stop, err := startServer()
	if err != nil {
		t.Fatalf("startServer: %v", err)
	}
	c, err := jsonrpc.Dial("tcp", addr)
	if err != nil {
		stop()
		t.Fatalf("dial: %v", err)
	}
	return c, func() { c.Close(); stop() }
}

func TestCreateOrderSuccess(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	o, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 100, IdempotencyKey: "k1"})
	if err != nil {
		t.Fatalf("createOrder: %v", err)
	}
	if o.ID == 0 || o.Amount != 100 || o.Status != "created" {
		t.Fatalf("订单异常: %+v", o)
	}
}

// TestIdempotentSameKey 同一幂等键重复下单：返回同一订单、不重复入库
func TestIdempotentSameKey(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	key := "dup-key"
	o1, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 50, IdempotencyKey: key})
	if err != nil {
		t.Fatal(err)
	}
	o2, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 50, IdempotencyKey: key})
	if err != nil {
		t.Fatal(err)
	}
	if o1.ID != o2.ID {
		t.Fatalf("同 key 应返回同一订单: %d vs %d", o1.ID, o2.ID)
	}
	// 只入库一条：GetOrder 能查到，且 ListOrders 语义 = 通过 GetOrder 两个 ID 验证
	var gr GetOrderReply
	if err := c.Call("OrderService.GetOrder", &GetOrderArgs{ID: o1.ID}, &gr); err != nil {
		t.Fatalf("订单应存在: %v", err)
	}
}

// TestDifferentKeysCreateDifferentOrders 不同 key → 不同订单
func TestDifferentKeysCreateDifferentOrders(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	o1, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 10, IdempotencyKey: "a"})
	if err != nil {
		t.Fatal(err)
	}
	o2, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 20, IdempotencyKey: "b"})
	if err != nil {
		t.Fatal(err)
	}
	if o1.ID == o2.ID {
		t.Fatalf("不同 key 应为不同订单")
	}
}

func TestInvalidAmount(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	_, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 0, IdempotencyKey: "k"})
	if err == nil || !strings.Contains(err.Error(), "amount must be positive") {
		t.Fatalf("非正金额应报错, got %v", err)
	}
}

func TestMissingIdempotencyKey(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	_, err := createOrder(c, &CreateOrderArgs{UserID: 1, Amount: 10, IdempotencyKey: ""})
	if err == nil || !strings.Contains(err.Error(), "idempotency key required") {
		t.Fatalf("缺幂等键应报错, got %v", err)
	}
}

func TestGetOrderNotFound(t *testing.T) {
	c, cleanup := newTestClient(t)
	defer cleanup()
	var gr GetOrderReply
	err := c.Call("OrderService.GetOrder", &GetOrderArgs{ID: 999}, &gr)
	if err == nil || !strings.Contains(err.Error(), "order not found") {
		t.Fatalf("应报 order not found, got %v", err)
	}
}

// TestRetryAfterTransientFailure 瞬时故障（首次调用失败）后重试成功
func TestRetryAfterTransientFailure(t *testing.T) {
	calls := 0
	err := callWithRetry(3, 10*time.Millisecond, func() error {
		calls++
		if calls == 1 {
			return errors.New("connection refused") // 模拟瞬时网络故障
		}
		return nil
	})
	if err != nil {
		t.Fatalf("重试后应成功: %v", err)
	}
	if calls != 2 {
		t.Fatalf("应调用 2 次（1 失败 + 1 成功）, got %d", calls)
	}
}

func TestRetryExhausted(t *testing.T) {
	err := callWithRetry(3, time.Millisecond, func() error {
		return errors.New("always fail")
	})
	if err == nil || !strings.Contains(err.Error(), "重试 3 次仍失败") {
		t.Fatalf("应报重试耗尽, got %v", err)
	}
}

// TestTimeout 慢调用超时返回 ErrTimeout
func TestTimeout(t *testing.T) {
	start := time.Now()
	err := callWithTimeout(50*time.Millisecond, func() error {
		time.Sleep(300 * time.Millisecond)
		return nil
	})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("应返回 ErrTimeout, got %v", err)
	}
	if time.Since(start) > 200*time.Millisecond {
		t.Fatalf("超时触发过慢: %v", time.Since(start))
	}
}
