// exercises/sol-02-student-mgmt.go —— 练习 2 参考实现：学生管理系统（map[int]Student）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-02-student-mgmt.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"sort"
)

type Student struct {
	ID    int
	Name  string
	Score float64
}

func main() {
	students := make(map[int]Student)

	// 增
	students[1] = Student{ID: 1, Name: "Alice", Score: 88.5}
	students[2] = Student{ID: 2, Name: "Bob", Score: 76.0}
	students[3] = Student{ID: 3, Name: "Carol", Score: 92.0}

	// 查（ok 模式区分「不存在」与「零值」）
	if s, ok := students[2]; ok {
		fmt.Printf("查询 ID=2: %s 分数 %.1f\n", s.Name, s.Score)
	}
	if _, ok := students[99]; !ok {
		fmt.Println("查询 ID=99: 未找到")
	}

	// 改（struct 是值类型，需回写）
	if s, ok := students[1]; ok {
		s.Score = 91.0
		students[1] = s
	}

	// 删
	delete(students, 3)
	if _, ok := students[3]; !ok {
		fmt.Println("删除 ID=3 后查询: 未找到")
	}

	// 按 ID 升序列出
	ids := make([]int, 0, len(students))
	for id := range students {
		ids = append(ids, id)
	}
	sort.Ints(ids)

	fmt.Println("\n=== 学生列表 ===")
	for _, id := range ids {
		s := students[id]
		fmt.Printf("ID=%d %s 分数=%.1f\n", s.ID, s.Name, s.Score)
	}
	fmt.Printf("共 %d 名学生\n", len(students))
}
