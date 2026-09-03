# exercises —— 内存布局、零拷贝与协议解析阶段练习

五题与 roadmap 第 19 节练习一一对应：练习 1 =「解析固定头部二进制协议（含大端/小端字段）」，练习 2 =「用切片返回借用数据」，练习 3 =「解析 WAL record」，练习 4 =「解析 SSTable block header」，练习 5 =「实现 length-prefix frame parser」。完成顺序建议按 1~5（由易到难）。参考实现在 `sol-*.rs`，**先自己做，做完再看**。每题标注难度（★~★★★）。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理）；全部基于 `std` 单文件，离线可用。每个 sol 的验证命令一致（以 sol-01 为例）：

```bash
# 编译并运行演示
rustc --edition 2021 -D warnings sol-01-fixed-header.rs -o /tmp/ph19-sol01 && /tmp/ph19-sol01
# 编译并跑内嵌单元测试
rustc --edition 2021 -D warnings --test sol-01-fixed-header.rs -o /tmp/ph19-sol01-t && /tmp/ph19-sol01-t
```

**验证说明**：sol-01~sol-05 已在 rustc 1.92.0 本机实测 —— 演示输出符合注释预期、全部单元测试通过，标注「已验证」。通读提示：主文档 3.3/3.7 的 BeReader 与安全纪律三件套是所有题的地基；练习 2 需要 ph18 的「返回借用还是返回拥有值」判断（主文档 3.4/4.2）。

## 练习 1：固定头部二进制协议解析（★★）

- **目标**：解析一个**同时含大端与小端字段**的固定头部，体会「每个字段按格式规范选 from_be_bytes/from_le_bytes」（roadmap 练习「解析固定头部二进制协议（含大端/小端字段）」；对应主文档 3.3）
- **要求**：自定一份混合字节序格式，至少含 magic + 一个 BE 字段 + 一个 LE 字段 + 一个长度字段 + payload；写 `parse_packet(buf) -> Result<Header, Err>` 类函数，**逐字段 get + try_into**，长度不足返回错误不 panic；payload 以借用切片返回
- **验收**：合法包各字段值正确；截断（砍在不同字段中间）与坏魔数各返回明确错误；能说明「为什么不能把整块字节直接转成一个 repr(C) 结构体来读」（提示：字节序要对齐的不是对齐，是字节排列——见主文档 3.7 三条红线）
- 参考实现：`sol-01-fixed-header.rs`（4 条测试）

## 练习 2：用切片返回借用数据（★★）

- **目标**：写一个「不拥有数据」的查询函数：从多条记录组成的缓冲里按索引取一条，返回它的 key 与 value 的**借用切片**（roadmap 练习「用切片返回借用数据」；对应主文档 3.4/4.2，呼应 ph18 的 E0597/E0515）
- **要求**：自定记录格式（如 `[klen: u16][key][vlen: u16][value]` 重复）；函数签名含生命周期，`返回值的生命周期绑定输入`；**不许返回函数内新建数据的引用**（想想为什么编不过）；尾截断返回 None/Err 而非 panic
- **验收**：取任意索引返回正确键值；用指针算术证明返回切片落在输入缓冲内部（无复制）；两个返回的借用切片能同时存活；写出「若想在函数里造数据再返回，签名该改成什么」的一句话答案
- 参考实现：`sol-02-borrow-slice.rs`（5 条测试）

## 练习 3：解析 WAL record（★★★）

- **目标**：解析带 checksum 与**分片类型**的 WAL record，并明确零拷贝的适用边界（roadmap 练习「解析 WAL record」；对应主文档 3.8）
- **要求**：采用 LevelDB log record 骨架：`[checksum: u32 LE][length: u16 LE][type: u8][payload]`，type ∈ {FULL/FIRST/MIDDLE/LAST}；**FULL 直接借用 payload**（零拷贝）；FIRST+MIDDLE…+LAST 的跨段逻辑记录需拼装（为什么不能借用？）；先校验 checksum 再信任内容；逻辑记录设总长上限
- **验收**：单条 FULL 与一条切成 3 段的逻辑记录都能解析且内容正确；篡改任意 payload 字节被 checksum 拦下；对「FIRST 后接 FULL」「MIDDLE 前无 FIRST」「链未收尾」等协议错误返回明确错误
- 参考实现：`sol-03-wal-record.rs`（7 条测试，含 crc32c 标准向量自检）

## 练习 4：解析 SSTable block header（★★★）

- **目标**：解析 SSTable 的 block handle 与索引，安全地按 offset/size 切出数据块视图（roadmap 练习「解析 SSTable block header」；对应主文档 3.8，正文内联片段与本练习同构）
- **要求**：handle 为 `[offset: u32 LE][size: u32 LE]`；提供 `parse_block_handle(file, handle_pos)` 返回 `(offset, size, block 借用切片)`；**双闸门**：`offset + size` 先 `checked_add`（防溢出），再 `file.get` 落界，之后才借用；文件头含 magic/count，索引区长度也要校验
- **验收**：能读出索引并逐个返回各块零拷贝视图；伪造越界/超大 size/超大 offset 的句柄均返回错误且**绝不 panic**；视图指针偏移 = offset（证明是借用不是复制）
- 参考实现：`sol-04-sstable-header.rs`（5 条测试）

## 练习 5：length-prefix frame parser（★★★）

- **目标**：实现可应对网络分块的 length-prefix 帧解析器（roadmap 练习「实现 length-prefix frame parser」；对应主文档 3.7/ex04 的流式形态）
- **要求**：帧 = `[len: u32 BE][type: u8][payload]`；解析器支持 `feed(分块)` + 解出当前全部完整帧；帧头/载荷不足 → 等待下一块；`len > 上限` → 明确错误；粘连多帧逐条吐出
- **验收**：**逐切分点验证**——把同一段双帧字节流按 0..=总长 的每一个切分点拆成两段喂入，结果必须与整段一次喂入完全一致（这正是 ph20 proptest 想自动化的那类检查）；半帧等待、超大长度两条路径各自覆盖
- 参考实现：`sol-05-frame-parser.rs`（4 条测试，含逐切分点一致性用例）

做完五题后，你对「安全 + 零拷贝」解析的肌肉记忆就建起来了：练习题 1 练逐字段读数、2 练借用生命周期、3 练校验与零拷贝边界、4 练偏移闸门、5 练流式与边界切分——去 project/ 把它们合进一个带完整测试的 WAL record 解析器。
