# exercises —— C 语言 mmap、Page Cache 与可靠文件 IO 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~4 顺序完成。四题与 roadmap ph13「练习」一一对应：练习 1「用 pread 按 offset 读取 record」、练习 2「实现 append-only log」、练习 3「用 mmap 读取只读数据文件」、练习 4「模拟进程崩溃后的 log replay」。所有题目的共同纪律——**write 成功不代表持久化（fsync 才是刷盘边界）、read/write 返回值必须处理短读短写、访问文件内容前先校验长度**，并保持 `-Wall -Wextra -std=c11` 零警告。参考实现在 `sol-*` 文件中，做完再看。

## 练习 1：用 pread 按 offset 读取 record（★）

- **目标**：写一个 `read_record(fd, index, ...)` 函数，用 pread 按索引随机读定长 record，全程不移动 fd 的 offset
- **要求**：
  - record 布局：定长 32 字节 = `id`(u32 大端， 4) + `name`(28 字节， 不足补 0)；先顺序写入 10 条（id = 100 + i，name = "user\<i\>"）
  - 写完后 `lseek(fd, 0, SEEK_SET)` 归零，之后只允许用 `pread`（禁止 `lseek + read` 组合——为什么？想想两个线程共享同一 fd 时会发生什么）
  - 按索引读第 3、7、0、9 条并打印；每次读前后用 `lseek(fd, 0, SEEK_CUR)` 证明 offset 恒为 0；读第 10 条（不存在）必须返回失败
- **验收**：`cc -Wall -Wextra -std=c11` 零警告；4 条 record 的 id/name 全部正确；offset 恒 0；越界读取被正确拒绝

## 练习 2：实现 append-only log（★★）

- **目标**：实现 `[len: u32 大端][payload]` 格式的 append-only 日志：追加写 + fsync + 顺序回放
- **要求**：
  - 打开标志用 `O_CREAT | O_WRONLY | O_APPEND`（O_APPEND 保证每次 write 原子落到文件末尾，多进程追加互不覆盖）
  - 写入必须走 write_full 循环（处理短写，参考 examples/ex02-short-io.c）；3 条写完后 `fsync` 一次，并想清楚：**不 fsync 就退出，数据在什么情况下会丢？**
  - 回放：顺序读到 EOF，正确处理 read 返回 0（EOF）；payload 长度先校验上限再分配/读取
- **验收**：零警告；追加 3 条（"SET a=1" / "SET b=2" / "DEL a"）后回放 3 条内容一致；文件总字节数 = 3 × (4 + len) 与 `lseek(fd, 0, SEEK_END)` 实测一致

## 练习 3：用 mmap 读取只读数据文件（★★）

- **目标**：用 `mmap(PROT_READ)` 扫描一个二进制索引文件并求和，像访问数组一样访问文件
- **要求**：
  - 文件布局（大端）：`magic`("IDX1", 4) + `count`(u32, 4) + count 个 u32 值（值 = 1..100000，先生成这个文件）
  - 用 `fstat` 取长度后 `mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0)`；映射建立后即可 `close(fd)`
  - 访问前三个检查一个不能少：**空文件/长度 < 8 不许 mmap**（mmap 长度 0 会失败）、magic 必须匹配、`8 + count*4` 必须等于文件实际长度（不信任文件里的长度声明）
  - 求和结果与公式 n(n+1)/2 核对；最后 `munmap` 配对释放
- **验收**：零警告；100000 个值求和 = 5000050000 与公式一致；对空文件调用解析函数必须安全拒绝（不崩溃、不 mmap）

## 练习 4：模拟进程崩溃后的 log replay（★★★）

- **目标**：用 fork + 真实 SIGKILL 模拟「写日志写到一半崩溃的服务」，验证崩溃恢复的两条真理
- **要求**：
  - 记录格式（大端）：`[len: u32][crc32: u32][payload]`（CRC 实现可参考 examples/ex06-append-only.c）
  - 子进程：追加 500 条记录（每 100 条 fsync 一次），然后写半条记录（只写头部的前几个字节），最后 `kill(getpid(), SIGKILL)` 自杀——真实 kill，不是提前 return
  - 父进程：`waitpid` 确认死因是 SIGKILL，然后回放：完整记录全部恢复、残尾被长度/CRC 识别停在准确偏移；最后 `ftruncate` 砍掉残尾修复文件
  - 回答一个问题并打印出来：**kill -9 之后，子进程已 write 但未来得及 fsync 的记录丢了吗？为什么？**（提示：Page Cache 属于内核还是属于进程？真正丢数据的场景是什么？）
- **验收**：零警告；回放恢复 500/500 条完整记录（进程崩溃不丢 Page Cache）；残尾停在准确偏移；ftruncate 修复后文件可继续追加；程序退出码 0

> **提示**：练习 1~4 依次对应主文档 3.3（pread/pwrite）、3.7（append-only）、3.6（mmap）、3.4/3.8（fsync 与崩溃恢复）的知识与 examples/ 对应示例——先独立完成，再对照 `sol-*` 复盘。所有 sol 文件头的「验证环境/编译/运行/验证状态」块里的数字均来自本机（Apple clang 21.0.0, macOS arm64）实测。
