// 来源：ph14-advanced-go 示例 2 —— slice 扩容机制与 map 底层行为实测
// 一句话说明：两个"容器底层机制"实验——① slice 扩容：append 时 cap 的成长序列，
// 验证「<256 翻倍、≥256 按 ~1.25 增长后按分配器 size class 取整」的规则（数字随
// 元素大小与架构变化，实测见 README）；② map：迭代顺序随机（刻意不保证）、扩容
// 分摊、以及最关键的——并发写 map 会怎样（用 -race 实测见 README，本文件演示
// 与 sync.Mutex 保护的对照）。这是"故意出错"演示：race demo 必须单独用
// `go run . -demo=race` 或 `go run -race . -demo=race` 运行，会以
// `fatal error: concurrent map writes` 崩溃退出，勿在测试里调用。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...                     # 正确性测试（不含 race demo）
//	go run .                             # slice 扩容序列 + map 迭代/安全写演示
//	go run . -demo=race                  # 故意出错：并发写 map → fatal error（预期崩溃）
//	go run -race . -demo=race            # 加 -race 复现：DATA RACE 报告 + fatal error
//	go run . -demo=safe                  # 对照：sync.Mutex 保护后并发写正常
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"flag"
	"fmt"
	"sync"
)

// ---- slice 扩容实验 ----

// IntGrowth 返回从 cap=1 开始反复 append 时，[]int 的容量成长序列。
func IntGrowth(n int) []int {
	s := make([]int, 0, 1)
	seq := []int{cap(s)}
	for i := 0; i < n; i++ {
		s = append(s, i)
		if c := cap(s); c != seq[len(seq)-1] {
			seq = append(seq, c)
		}
	}
	return seq
}

// ByteGrowth 同 IntGrowth，但元素只有 1 字节——小元素时初始 cap 会被 size class
// 直接抬到 8，且 256 之后的取整结果与 int 不同（实测：512→896）。
func ByteGrowth(n int) []int {
	s := make([]byte, 0, 1)
	seq := []int{cap(s)}
	for i := 0; i < n; i++ {
		s = append(s, byte(i))
		if c := cap(s); c != seq[len(seq)-1] {
			seq = append(seq, c)
		}
	}
	return seq
}

// BigGrowth 同 IntGrowth，但元素是 [32]byte（32 字节）——同一规则、不同 size class。
func BigGrowth(n int) []int {
	s := make([][32]byte, 0, 1)
	seq := []int{cap(s)}
	for i := 0; i < n; i++ {
		s = append(s, [32]byte{})
		if c := cap(s); c != seq[len(seq)-1] {
			seq = append(seq, c)
		}
	}
	return seq
}

// ---- map 行为实验 ----

// iterOrder 打印同一 map 的多次遍历顺序：每次都可能不同（Go 刻意随机化起点）。
func iterOrder() {
	m := map[string]int{"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
	for round := 1; round <= 2; round++ {
		var keys []string
		for k := range m {
			keys = append(keys, k)
		}
		fmt.Printf("  round %d 顺序: %v\n", round, keys)
	}
}

// safeWrite 用 sync.Mutex 保护并发写：正确写法，-race 无报告。
func safeWrite(wg *sync.WaitGroup, m map[int]int, mu *sync.Mutex, g int) {
	defer wg.Done()
	for i := 0; i < 1000; i++ {
		mu.Lock()
		m[g*1000+i] = i
		mu.Unlock()
	}
}

// raceWrite 故意并发写 map 不加速：数据竞争 → map 内部检测到并发写直接
// `fatal error: concurrent map writes` 崩溃进程（不靠 -race 也能崩，-race 只是先报报告）。
// 教学演示用，正常工程代码绝不允许——并发容器用 sync.Mutex 或 sync.Map。
func raceWrite(wg *sync.WaitGroup, m map[int]int, g int) {
	defer wg.Done()
	for i := 0; i < 1000; i++ {
		m[g*1000+i] = i // 无锁并发写 map：数据竞争
	}
}

func main() {
	demo := flag.String("demo", "", "race=并发写 map 故意出错（预期崩溃）；safe=加锁对照")
	flag.Parse()

	fmt.Println("== 1. slice 扩容序列（cap 从 1 起反复 append 的成长点）==")
	fmt.Println("[]int     :", IntGrowth(2000))
	fmt.Println("[]byte    :", ByteGrowth(2000))
	fmt.Println("[][32]byte:", BigGrowth(2000))

	fmt.Println("== 2. map 遍历顺序（同一 map 两次遍历）==")
	iterOrder()

	switch *demo {
	case "race":
		fmt.Println("== 3. race demo：4 个 goroutine 无锁并发写 map ==")
		fmt.Println("   （预期：fatal error: concurrent map writes，进程崩溃——故意出错示例）")
		m := make(map[int]int)
		var wg sync.WaitGroup
		for g := 0; g < 4; g++ {
			wg.Add(1)
			go raceWrite(&wg, m, g)
		}
		wg.Wait()
		fmt.Println("   map size:", len(m), "（正常不会执行到这里）")
	case "safe":
		fmt.Println("== 3. safe demo：sync.Mutex 保护并发写 ==")
		m := make(map[int]int)
		var mu sync.Mutex
		var wg sync.WaitGroup
		for g := 0; g < 4; g++ {
			wg.Add(1)
			go safeWrite(&wg, m, &mu, g)
		}
		wg.Wait()
		fmt.Println("   map size:", len(m), "（锁保护后并发写正常）")
	default:
		fmt.Println("== 3. 并发写 map 的两种结局 ==")
		fmt.Println("   无锁 → 数据竞争 + fatal error（跑 `go run . -demo=race` 或 `go run -race . -demo=race` 实测）")
		fmt.Println("   加锁 → 正常（跑 `go run . -demo=safe` 实测）")
	}
}
