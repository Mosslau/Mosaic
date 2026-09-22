// 来源：project/ 可替换存储层的 Todo 服务 —— 内存存储实现
// 一句话说明：MemStorage 基于 map，零值可用，Delete 幂等。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run . -backend=mem
// 验证状态：已验证（Go 1.22.2）
package main

// MemStorage 零值可用：data 为 nil 时 Save 惰性初始化 map
type MemStorage struct {
	data map[string]string
}

func (m *MemStorage) Save(key, value string) error {
	if m.data == nil {
		m.data = make(map[string]string)
	}
	m.data[key] = value
	return nil
}

func (m *MemStorage) Load(key string) (string, error) {
	v, ok := m.data[key]
	if !ok {
		return "", ErrNotFound
	}
	return v, nil
}

// Delete 幂等：key 不存在同样成功
func (m *MemStorage) Delete(key string) error {
	delete(m.data, key)
	return nil
}
