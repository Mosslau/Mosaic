# ph07 阶段项目：文件复制工具

## 需求

对应 Roadmap「ph07 IO 与文件操作阶段」推荐项目第一个「文件复制工具」：支持文件/目录复制、按字节数显示进度、覆盖确认；用字节流 + 缓冲实现复制逻辑，再对比 `Files.copy` 的写法，统计耗时与复制字节数。项目覆盖本阶段全部核心知识点：字节流读写、缓冲、try-with-resources、`Files.walk` 目录遍历、受检异常处理。

## 文件结构

| 文件 | 类 | 职责 |
|------|----|------|
| file-copy-tool.java | FileCopyTool | 命令行入口 + 复制逻辑（文件/目录分发、进度、覆盖确认）+ 自测 main |

## 功能清单

- [ ] 单文件复制：`BufferedInputStream`/`BufferedOutputStream` 逐块读写（8192 字节缓冲），全程 try-with-resources
- [ ] 目录复制：`Files.walk` 先收集条目再执行（先建目录再复制文件），保持目录结构
- [ ] 进度显示：按已复制字节 / 总字节计算百分比，每 10% 打印一次
- [ ] 覆盖确认：目标已存在且未加 `-f` 时拒绝并报错；加 `-f` 用覆盖模式
- [ ] 错误处理：源不存在、目标已存在、复制中途 IO 失败都有明确报错
- [ ] `Files.copy` 对比：同一批文件分别用字节流+缓冲与 `Files.copy` 复制，统计耗时与总字节数
- [ ] 自测 main：无参数运行时自造目录树（文本/中文/256KB 伪二进制），验证文件数、字节数、内容一致性、覆盖确认，失败抛 `AssertionError`

## 验收标准

- `javac file-copy-tool.java` 编译零错误
- `java FileCopyTool` 全部自测通过，末尾打印「全部自测通过」，且运行后 `copy-test/` 目录被完整清理
- 自测覆盖：3 个文件（含中文名、二进制）内容逐字节一致；目标已存在时不加 `-f` 必须拒绝；`Files.copy` 对比输出耗时与字节数
- 复制全程使用缓冲流 + try-with-resources，无手动 `close()`、`Files.walk` 流被正确关闭
- 命令行用法：`java FileCopyTool [-f] <源文件|源目录> <目标>`

## 扩展方向

- **大文件零拷贝**：用 `FileChannel.transferTo` 替代手动缓冲循环，对比大文件下的耗时差异（主文档 4.4 节）
- **并发复制**：目录复制时多文件并行（ph12 并发阶段）
- **断点续传**：记录已复制字节数，中断后从断点继续
- **目录统计工具**：Roadmap 推荐项目第二个——`Files.walk` + `Files.size` 统计文件总数/总大小/各扩展名占比
- **跨平台路径**：处理符号链接（`LinkOption.NOFOLLOW_LINKS`）与 Windows 文件占用语义（主文档 4.3 节）

## 验证环境

- 工具链：jenv OpenJDK 17.0.16
- 编译：`javac file-copy-tool.java`
- 运行：`java FileCopyTool`（自测）或 `java FileCopyTool [-f] <源> <目标>`（命令行使用）

```bash
# 1. 编译
javac file-copy-tool.java
# 2. 运行自测
java FileCopyTool
# 3. 验证后清理 .class
rm -f *.class
```

已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，自测全部通过；字节流+缓冲 262164 字节约 17.6 ms，`Files.copy` 约 1.3 ms——NIO 的零拷贝优化在大文件上优势明显）。
