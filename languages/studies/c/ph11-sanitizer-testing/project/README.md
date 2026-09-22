# ph11 阶段项目：带测试的 append-only buffer 库

对应 roadmap ph11「推荐项目」第三个「带测试的 WAL / buffer 库」：实现一个 append-only 字节 buffer（只追加、自动扩容、全部接口带边界检查与错误路径），配自测套件与 Makefile（普通构建 / 一键测试 / Sanitizer 构建 / 覆盖率），把本阶段"工具固化进构建"的流程完整落地。append-only 语义为 ph12 length-prefix frame 与 ph16 WAL 的"顺序写"预演（编码细节属 ph12，本库只做字节存储原语）。

## 需求

实现 `Buffer`（`buffer.h`/`buffer.c`）：`buf_init`（初始容量，0 退化为 1）/ `buf_destroy`（释放并重置）/ `buf_append`（追加 n 字节，容量不足自动翻倍扩容，失败原数据不丢）/ `buf_get`（按字节读，越界返回 -1）/ `buf_len`。所有接口对 `NULL` 参数返回 -1（或 0），不产生 UB。`test_buffer.c` 用零依赖断言宏覆盖边界输入（空 / 恰好填满 / 越界 / 远界）与错误路径（NULL 参数、扩容失败防护）。Makefile 提供 `make test` / `make asan` / `make coverage` 三档，`make check` 一键跑 test + asan。

## 功能清单

- [x] `Buffer` 类型与五个 API（init/destroy/append/get/len），全部带边界检查与错误路径
- [x] append-only 语义：不提供按位置改写接口，为顺序写服务
- [x] 扩容溢出防护：`cap` 翻倍/求和前检查 `SIZE_MAX`，`realloc` 失败不丢原数据
- [x] 自测套件 7 组用例、30 个断言：边界输入 + 错误路径全覆盖（实测全过）
- [x] `make`：普通构建（`-Wall -Wextra -std=c11 -O1 -g` 零警告）
- [x] `make test`：一键跑测试，全过退出码 0（CI 入口）
- [x] `make asan`：`-fsanitize=address,undefined -fno-sanitize-recover=all` 构建并跑同一套测试，零报告
- [x] `make coverage`：`--coverage` 插桩构建 + gcov 文本报告（行/分支两级）
- [x] `make check`：test + asan 一键全过
- [x] `make clean`：清空全部产物

## 验收标准

- [ ] `make clean && make test`：构建零警告，输出 `自测通过: 30 个断言全部通过`，退出码 0
- [ ] `make asan`：同一套测试在 ASan+UBSan 构建下零报告、退出码 0（"行为正确 + 内存无错"双证明）
- [ ] `make coverage`：`buffer.c` 行覆盖 100%、`Branches executed` 100%；`test_buffer.c` 行覆盖 ≥ 98%（实测 98.55%）
- [ ] `make check` 一次跑通 test + asan
- [ ] `make clean` 后目录内无 `.o`/可执行文件/`.gcda`/`.gcno`/`.gcov` 残留

## 关于故意出错的代码

本项目**全部是正常工程代码**，没有"故意写错"的演示——错误通过测试用例断言（越界请求返回 -1 而非崩溃）体现，不是靠 Sanitizer 中止。测试刻意保留两类"工具盲区"作为教学点：**防御性分支**（`malloc`/`realloc` 失败、扩容溢出防护——`buffer.c` 的 `Taken at least once` 81.25% 就是这些很难在测试中触发的分支）与 **CHECK 宏的 FAIL 分支**（`test_buffer.c` 的 `Taken at least once` 50%——全过时它永不被取）。覆盖率指引补测，但"防御性盲区"是接受的代价，不是必须 100% 的负担。

## 验证环境

- Apple clang 21.0.0（`cc`），macOS（Darwin arm64），`-Wall -Wextra -std=c11 -O1 -g`
- 构建：`make`；测试：`make test`；Sanitizer：`make asan`；覆盖率：`make coverage`；清理：`make clean`
- 验证状态：已验证（`make test` 30 断言全过、退出码 0；`make asan` 零报告；覆盖率数字见上；`make clean` 零残留）。注意 macOS 的 `.gcda` 名带可执行名前缀（`test_buffer_cov-buffer.gcda`），Linux gcc 直接是源码名，Makefile 的 coverage 目标已兼容两者。

## 扩展方向（可选）

- 追加"长度前缀"写读原语（`buf_append_u32be` / 读长度后按长度读 payload）——**length-prefix frame 的编码细节属 ph12 字节序、内存对齐与二进制格式解析阶段（roadmap 第 12 节）**，本库的 append/get 已备好原语
- 接入第三方框架（Unity/CMocka）替换自测壳，比较"自测模式 vs 框架"的取舍（主文档 3.7）
- 加一个把 `Buffer` 顺序写进文件的 `buf_flush`（衔接 ph06 文件 IO 与 ph13 可靠刷盘），并把 `make coverage` 的门槛（如 `buffer.c` 行覆盖 ≥ 95%）写进 CI
- 用 `-fsanitize=thread` 跑并发写同一 buffer 的版本，验证"append 加锁"后零竞争——锁设计本身属并发专题，本阶段只验证工具能检测
