// 来源：project/ 可替换存储层的 Todo 服务 —— Storage 接口定义
// 一句话说明：消费侧定义的存储接口，MemStorage / FileStorage 均隐式满足。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run . -backend=mem|file
// 验证状态：已验证（Go 1.22.2）
package main

import "errors"

// ErrNotFound 哨兵错误：Load 未命中时返回，调用方用 errors.Is 判断
var ErrNotFound = errors.New("storage: key not found")

// Storage 接口由使用方 TodoService 定义——实现方无需显式声明 implements
type Storage interface {
	Save(key, value string) error
	Load(key string) (string, error)
	Delete(key string) error
}
