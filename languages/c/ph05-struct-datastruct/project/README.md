# 阶段项目：内存表 / HashMap KV 表（kvstore）

对应 roadmap ph05 推荐项目第一个「内存表 / HashMap KV 表」。用链地址法哈希表实现一个支持字符串键值的内存 KV 存储，附带 `main.c` 用 assert 自测。

## 需求

- `kv_create()` / `kv_destroy()` —— 创建（初始 101 桶）与销毁（释放全部 key/value/节点）
- `kv_put()` —— 写入：键已存在则覆盖值并返回 1，新建返回 0，内存不足返回 -1
- `kv_get()` —— 读取：键存在把值拷入调用者缓冲区并返回 1；不存在返回 0
- `kv_delete()` —— 删除：存在返回 1，不存在返回 0
- `kv_contains()` —— 键是否存在
- `kv_size()` / `kv_keys()` —— 记录数 / 遍历所有键（回调或数组）

## 功能清单

| 功能 | 说明 |
|------|------|
| 链地址法 | 哈希冲突用桶内链表解决，djb2 变体哈希（5381 起手） |
| 值拷贝语义 | 存储动态分配副本，不依赖调用者缓冲区生命周期 |
| 覆盖写入 | 同键重复 put 覆盖旧值并释放旧内存 |
| 内存安全 | 销毁/删除路径先释放 value/key 再释放节点，无泄漏 |
| 自测 | `main.c` 内 assert 覆盖增/改/查/删/覆盖/遍历六条路径 |

## 验收标准

- [ ] `gcc -Wall -Wextra -std=c99 kv.c main.c -o kvstore` 编译零警告
- [ ] 运行 `./kvstore` 全部 assert 通过（输出「全部 assert 通过」）
- [ ] 用 `valgrind --leak-check=full ./kvstore` 检查 `definitely lost` 为 0（本机无 valgrind 时改用 `-fsanitize=address`）
- [ ] 删除键后 `get` 返回 0、`contains` 返回 0

## 扩展方向

- 支持 `int` 值（union 或泛型化），对齐数据库的 value 类型
- 自动扩容：装载因子 > 0.75 时翻倍桶数并 rehash（生产哈希表必做）
- 遍历排序输出（按 key 字典序），做 Top-N 查询

## 验证环境

- Apple clang 17（gcc 兼容），`-Wall -Wextra -std=c99`
- 编译：`gcc -Wall -Wextra -std=c99 kv.c main.c -o kvstore`
- 运行：`./kvstore`
- 验证状态：已验证
