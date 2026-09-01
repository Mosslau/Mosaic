# examples —— C 语言字节序、内存对齐与二进制格式解析阶段完整示例

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64），全部示例统一 `cc -Wall -Wextra -std=c11` 零警告编译，输出为本机实测。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-endian.c` | 大小端检测（编译期宏 + 运行期 memcpy 判读）+ 显式大端/小端读写函数（read_be16/be32、read_le16/le32、write_be32）+ 与 POSIX `htonl`/`ntohl` 对照（网络字节序 = 大端） | `cc -Wall -Wextra -std=c11 ex01-endian.c -o ex01` | `./ex01` | 已验证：零警告，退出码 0；`write_be32(0x01020304)` 落线字节固定为 `01 02 03 04`；`htonl` 首字节 `01`（网络序 = 大端） |
| `ex02-align.c` | 结构体对齐与 padding：`sizeof`/`offsetof`/`_Alignof` 实测 S1（12 字节）/S2（8 字节）/packed（6 字节）/`aligned(16)`，字段重排省空间的对比，字节流 → 已对齐本地对象的 `memcpy` 安全解析示范 + 强转指针反例 | `cc -Wall -Wextra -std=c11 ex02-align.c -o ex02` | `./ex02` | 已验证：零警告，退出码 0；本机 `_Alignof(int32_t)=4`、`_Alignof(uint64_t)=8` |
| `ex03-bits.c` | 位运算、掩码、移位：flags 单 bit 置位/清位/翻转/提取、4+12 位打包字段的显式掩码读写、位域（bit-field）对比（布局实现定义、不可跨平台）、无符号移位边界 | `cc -Wall -Wextra -std=c11 ex03-bits.c -o ex03` | `./ex03` | 已验证：零警告，退出码 0；packed=0x3abc → type=3 len=2748 往返一致 |
| `ex04-record.c` | **安全解析二进制 record（重点）**：magic + 版本 + type + key/value 长度 + CRC32 尾校验；先校验长度再逐字段显式读取（绝不强转结构体指针）；演示损坏检测（翻转 payload 一位 → `PARSE_CRC`）与截断检测（→ `PARSE_TRUNC`） | `cc -Wall -Wextra -std=c11 ex04-record.c -o ex04` | `./ex04` | 已验证：零警告，退出码 0；2 条 record 解析通过，损坏/截断各被对应错误码拦截 |
| `ex05-frame.c` | length-prefix frame 增量式流式解析：`FrameReader` 状态机按 5 字节分块喂入仍能正确拆帧，处理"还差数据"、截断与长度超上限（0xFFFF > 4096 直接判非法） | `cc -Wall -Wextra -std=c11 ex05-frame.c -o ex05` | `./ex05` | 已验证：零警告，退出码 0；25 字节流分 5 块喂入解出 3 个 frame |
| `ex06-varint.c` | varint（LEB128）编码/解码：7 位一组 + 续位标记，边界值往返一致；截断 varint（0x80 0x80）判非法；magic（"NV01"）+ 版本 + varint 记录数的文件头校验演示 | `cc -Wall -Wextra -std=c11 ex06-varint.c -o ex06` | `./ex06` | 已验证：零警告，退出码 0；8 组边界值往返一致，0xFFFFFFFF 编码为 5 字节 |

## 说明

- 六个示例与主文档第 6 章示例 1~6 一一对应；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以本目录为准）。
- 全部运行产物（`ex01`~`ex06` 可执行文件）一律写 /tmp 或构建临时目录，验证后清理，不入仓库。
- 字节序演示基于本机（Apple Silicon，小端）实测；`htonl`/`ntohl` 是 POSIX 函数（`arpa/inet.h`），不属于标准 C——跨平台代码用本目录的显式读写函数或标准库提供的等价物（见主文档 3.2）。
- `ex02` 的 `__attribute__((packed))` / `__attribute__((aligned(16)))` 是 GCC/Clang 扩展（MSVC 用 `#pragma pack` / `__declspec(align)`）；`_Alignas(16)` 作用于对象（变量）是 C11 标准。位域布局是实现定义的，`ex03` 用它做对照演示，跨平台协议请用显式掩码 + 移位。
