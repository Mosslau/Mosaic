// Package registry 本地服务注册表——"服务注册与发现"的最小可运行模型。
// 生产环境对应 etcd / Consul / Nacos（见阶段笔记 3.4）：本包用进程内 map + TTL 心跳
// 实现"服务名 → 存活实例地址"的登记/续约/摘除/发现，并以 JSON-RPC（net/rpc/jsonrpc，
// 零第三方依赖）暴露成独立服务，供服务实例注册、网关发现使用。
package registry

import (
	"sort"
	"sync"
	"time"
)

// Registry 注册表：并发安全；ttl 内未心跳的实例视为失联，Discover 时剔除
type Registry struct {
	mu        sync.Mutex
	instances map[string]map[string]time.Time // service → addr → 最后心跳时间
	ttl       time.Duration
}

func New(ttl time.Duration) *Registry {
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
	r.Register(service, addr)
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
			delete(r.instances[service], addr)
			continue
		}
		addrs = append(addrs, addr)
	}
	sort.Strings(addrs) // 稳定顺序，便于测试与轮询的可预期性
	return addrs
}

// Count 某服务的实例数（测试/观测用）
func (r *Registry) Count(service string) int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.instances[service])
}
