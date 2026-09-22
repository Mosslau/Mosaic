# examples —— 结构体与数据结构阶段完整示例

验证环境：Apple clang 17（gcc 兼容），编译命令统一 `gcc -Wall -Wextra -std=c99`。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-linked-list.c` | 单链表：头插/尾插/删除/查找/完整释放（二级指针） | `gcc -Wall -Wextra -std=c99 ex01-linked-list.c -o ex01-linked-list` | `./ex01-linked-list` |
| `ex02-array-stack.c` | 数组栈 + 括号匹配（含 5 组测试用例） | `gcc -Wall -Wextra -std=c99 ex02-array-stack.c -o ex02-array-stack` | `./ex02-array-stack` |
| `ex03-linked-queue.c` | 链表队列：head+tail 双指针 O(1) 入队 | `gcc -Wall -Wextra -std=c99 ex03-linked-queue.c -o ex03-linked-queue` | `./ex03-linked-queue` |
| `ex04-hash-table.c` | 哈希表（链地址法）：词频统计 | `gcc -Wall -Wextra -std=c99 ex04-hash-table.c -o ex04-hash-table` | `./ex04-hash-table` |
| `ex05-bst.c` | 二叉搜索树：插入/查找/中序遍历/后序释放 | `gcc -Wall -Wextra -std=c99 ex05-bst.c -o ex05-bst` | `./ex05-bst` |
| `ex06-min-heap.c` | 二叉堆：push 上浮 / pop 下沉 O(log n) | `gcc -Wall -Wextra -std=c99 ex06-min-heap.c -o ex06-min-heap` | `./ex06-min-heap` |
| `ex07-graph-bfs.c` | 图（邻接表）：BFS 最短跳数 | `gcc -Wall -Wextra -std=c99 ex07-graph-bfs.c -o ex07-graph-bfs` | `./ex07-graph-bfs` |

七个示例均已在 Apple clang 17（gcc 兼容）下编译零警告并运行验证（已验证）。
