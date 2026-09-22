# examples —— C 语言 mmap、Page Cache 与可靠文件 IO 阶段完整示例

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64，Apple Silicon 内置 SSD），全部示例统一 `cc -Wall -Wextra -std=c11` 零警告编译，输出为本机实测。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-open-read-write.c` | open/read/write 基础与文件 offset：write 推进 offset、pread/pwrite 不推进、EOF 返回 0 不是错误、错误返回 errno（对 O_WRONLY fd read → -1/EBADF） | `cc -Wall -Wextra -std=c11 ex01-open-read-write.c -o ex01` | `./ex01` | 已验证：零警告，退出码 0；write(5) 返回 5、offset=5，pread 后 offset 仍 5，EOF 返回 0，errno=9（EBADF） |
| `ex02-short-io.c` | 短读短写与 read_full / write_full 循环：用 pipe 制造真实短读（单次 read 15 字节只拿到 3），EINTR 重试，EOF 判定 | `cc -Wall -Wextra -std=c11 ex02-short-io.c -o ex02` | `./ex02` | 已验证：零警告，退出码 0；单次 read 返回 3（"AAA"），read_full(7) 补齐 "BBBBBCC"，对端关闭后返回 0 |
| `ex03-fsync.c` | fsync/fdatasync 语义与耗时实测：64 MiB 写入后各刷一次、20000 条 × 128 字节 record 三种刷盘策略（只结尾/每 200 条/每条）吞吐对比、macOS F_FULLFSYNC 与 fsync 的边界差异 | `cc -Wall -Wextra -std=c11 ex03-fsync.c -o ex03` | `./ex03` | 已验证：零警告，退出码 0；每条 fsync 比只结尾慢约 17 倍（439.7 ms vs 25.5 ms）；F_FULLFSYNC 比 fsync 慢两个数量级（247 vs 31725 次/秒） |
| `ex04-pagecache.c` | Page Cache 存在性与影响实测：write 阶段（进缓存）与刷盘分开计时、热读（缓存命中）vs 冷读（msync(MS_INVALIDATE) 逐出）吞吐对比 | `cc -Wall -Wextra -std=c11 ex04-pagecache.c -o ex04` | `./ex04` | 已验证：零警告，退出码 0；写 256 MiB 进缓存 4431 MiB/s；热读 14472 MiB/s、冷读 6010 MiB/s，缓存命中加速约 2.4 倍 |
| `ex05-mmap.c` | mmap/munmap/msync 与 mmap vs read 对比：只读 mmap 把索引文件当数组解析、MAP_SHARED 写 + msync 刷回、256 MiB 逐页触摸的吞吐对比 | `cc -Wall -Wextra -std=c11 ex05-mmap.c -o ex05` | `./ex05` | 已验证：零警告，退出码 0；mmap 9.9 ms（25864 MiB/s）vs read 15.1 ms（16994 MiB/s）；MAP_SHARED 写 + msync 后 pread 读回一致 |
| `ex06-append-only.c` | append-only 日志：O_APPEND 原子追加 + `[len: u32][crc32: u32][payload]` 大端记录、模拟半写入（3 字节残头部）、回放识别残尾、ftruncate 修复 | `cc -Wall -Wextra -std=c11 ex06-append-only.c -o ex06` | `./ex06` | 已验证：零警告，退出码 0；5 条全部恢复，残尾停在偏移 98，修复后恢复可追加状态 |

## 说明

- 六个示例与主文档第 6 章示例 1~6 一一对应；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以本目录为准）。
- 全部运行产物（`ex01`~`ex06` 可执行文件）一律写 /tmp 或构建临时目录，演示文件运行后自动删除，验证后清理，不入仓库。
- 耗时数字与机器/磁盘/内存压力相关，`ex03`/`ex04`/`ex05` 文件头已注明「本文档引用的一次实测值」——数量级关系与结论稳定，绝对值会随硬件不同。
- `msync(MS_SYNC|MS_INVALIDATE)` 逐出缓存页是 ex04 的演示手段：macOS 上 `fcntl(F_NOCACHE)` 只影响之后的行为、不逐出已缓存页，实测无效；Linux 对应手段是 `posix_fadvise(POSIX_FADV_DONTNEED)` 或 `drop_caches`（见 ex04 内注释）。
- `fdatasync`、`F_FULLFSYNC` 属 POSIX/macOS 扩展而非标准 C：Linux 的 fsync 即真落盘语义，无 fsync/F_FULLFSYNC 之分（见 ex03 第 3 部分与主文档 3.4）。
