# ph12 阶段项目：WAL record 解析器

> 对应 roadmap ph12「推荐项目」第一个「WAL record 解析器」（其余推荐项目由 examples/ex04、ex05 与练习 3/5 覆盖）。一个带 magic + 版本 + length-prefix + CRC32 的 WAL 文件工具：写入、回放校验、损坏/截断/magic 检测——把本阶段"先校验长度再读字段、绝不强转结构体指针、格式契约（magic/版本/checksum）"三条核心纪律落地成可运行代码。

## 需求

实现一个 WAL（Write-Ahead Log）文件格式与命令行工具：

- **文件头（8 字节，大端）**：`magic`（u32 = "WAL1"，识别"这是不是我们的文件"）+ `version`（u16 = 1，版本演进）+ `reserved`（u16，必须为 0）
- **每条 record（11 + len 字节，大端）**：`magic`（u32）+ `type`（u8，1=PUT 2=DEL）+ `len`（u16，payload 长度）+ `payload[len]` + `crc32`（u32，覆盖 magic+type+len+payload）
- **写**：`write <file> <n>` 生成文件头 + n 条 record
- **读**：`read <file> [offset]` 把文件读入内存后安全回放——先校验文件头，再逐条解析；`offset` 参数模拟损坏（翻转 1 位），验证 CRC 拦截
- **自测**：`test` 用 CHECK 宏自测往返 / 损坏 / 截断 / magic 四类，退出码 0 = 全过（可进 CI）

解析路径的顺序即 roadmap 必会概念：**先校验长度 → magic → type → payload 总长 → CRC → 才返回字段**；损坏与截断各自报出可区分的错误码（`WAL_ERR_CRC` / `WAL_ERR_TRUNC` / `WAL_ERR_MAGIC`）。

## 功能清单

- [x] `wal_write_header` / `wal_read_header`：文件头写入与校验（magic + 版本 + reserved）
- [x] `wal_append_record`：按显式大端字节序组装 record，CRC32 覆盖全字段后落盘
- [x] `wal_parse_record`：内存中安全解析（长度先校验、逐字段读取、CRC 校验）
- [x] `wal_tool write <file> <n>`：写新 WAL 文件
- [x] `wal_tool read <file> [offset]`：回放校验 + 可选损坏模拟
- [x] `wal_tool test`：自测套件（往返 / 损坏 / 截断 / magic，退出码即结果）
- [x] Makefile：`make`（构建）/ `make test`（一键自测）/ `make demo`（写+读+损坏演示）/ `make clean`

## 验收标准

- [x] `make` 零警告（`-Wall -Wextra -std=c11`，Apple clang 21.0.0 实测）
- [x] `make test` 全部断言通过、退出码 0（实测 21 个 [PASS]，含往返 5 条、损坏→`WAL_ERR_CRC`、截断→`WAL_ERR_TRUNC`、magic→`WAL_ERR_MAGIC`）
- [x] `make demo`：写 8 条 → 正常回放全过；`read <file> 43` 翻转 record 1 的 payload 一位 → 报 `checksum 不匹配`、退出码 1（CRC 拦截生效）
- [x] `make clean` 零残留（仓库内无 .o / 可执行文件；演示文件写 /tmp）
- [x] 解析器对"长度不足 / 损坏 / 非本格式文件"给出可区分的错误码，不崩溃、不越界（ASan/UBSan 复跑零报告，见下方验证命令）

## 验证

```bash
make            # 1. 构建（-Wall -Wextra -std=c11, 零警告）
make test       # 2. 自测（全过退出码 0）
make demo       # 3. 演示（正常回放 + 损坏拦截）
# 4. Sanitizer 复跑（行为正确 + 内存无错, 衔接 ph11 工具链）
cc -Wall -Wextra -std=c11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all wal.c main.c -o /tmp/wal_tool_san && /tmp/wal_tool_san test
make clean      # 5. 清理
```

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64），C11。全部实测输出见 `main.c` 文件尾注释。

## 扩展方向

- 加 `fsync` 落盘与崩溃恢复语义（半写入 record 通过 CRC/长度检测被跳过）——衔接 [ph13 mmap、Page Cache 与可靠文件 IO 阶段](../../ph13-mmap-page-cache/13-mmap-page-cache.md)（roadmap 第 13 节）
- 加 record 序号（seqno）支持回放去重；加 checksum 强度更高的校验（如 xxHash）对照
- 把 payload 的"key=value"文本改成真正的 key/value 双字段 + varint 长度编码（varint 见 examples/ex06，本阶段练习 4）
- 实现"读到损坏 record 后跳过剩余、按最新完好状态恢复"的 WAL 恢复流程——ph16 数据库存储引擎基础阶段（roadmap 第 16 节，目录待建）的 WAL replay 预演
