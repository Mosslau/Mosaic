// Package lb 负载均衡——轮询（RoundRobin）的最小实现。
// 概念见阶段笔记 3.5：轮询把请求均匀分摊到各实例；生产还有加权（Weighted）、
// 最少连接（Least Connections）、一致性哈希（Consistent Hashing）等策略。
package lb

import "sync"

// RoundRobin 轮询负载均衡器：按顺序轮流返回实例地址
type RoundRobin struct {
	mu    sync.Mutex
	addrs []string
	next  int
}

func New(addrs []string) *RoundRobin {
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

// Size 当前实例数（测试/观测用）
func (rr *RoundRobin) Size() int {
	rr.mu.Lock()
	defer rr.mu.Unlock()
	return len(rr.addrs)
}

// Addrs 返回当前实例列表副本（观测用）
func (rr *RoundRobin) Addrs() []string {
	rr.mu.Lock()
	defer rr.mu.Unlock()
	return append([]string(nil), rr.addrs...)
}
