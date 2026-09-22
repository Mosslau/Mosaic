# examples —— 文件、网络与系统编程阶段完整示例

验证环境：Apple clang 21（g++ 兼容），`-Wall -Wextra -std=c++20`（网络与文件示例均只用标准库 + POSIX 系统 API，无需第三方库）。本目录示例与主文档第 6 章示例 1~6 一一对应。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-logfs.cpp` | 日志文件系统：fstream 追加写 + 时间戳 + 错误处理 | `c++ -std=c++20 -Wall -Wextra ex01-logfs.cpp -o ex01` | `./ex01` |
| `ex02-echo.cpp` | TCP echo server：RAII socket + 阻塞收发 + 超时（selftest / server / client 三模式） | `c++ -std=c++20 -Wall -Wextra ex02-echo.cpp -o ex02` | `./ex02 selftest` 或 `./ex02 server 9000` + 另开终端 `./ex02 client 9000` |
| `ex03-http.cpp` | 简单 HTTP server：解析请求行 + 200/404 响应（Content-Length） | `c++ -std=c++20 -Wall -Wextra ex03-http.cpp -o ex03` | `./ex03 selftest` 或 `./ex03 8080` 后浏览器访问 |
| `ex04-config.cpp` | key=value 配置解析：可诊断错误（文件:行号） | `c++ -std=c++20 -Wall -Wextra ex04-config.cpp -o ex04` | `./ex04`（或 `./ex04 <配置文件>`） |
| `ex05-filexfer.cpp` | 文件传输工具：二进制分块读写 + FNV-1a 校验和 | `c++ -std=c++20 -Wall -Wextra ex05-filexfer.cpp -o ex05` | `./ex05 selftest` 或 `./ex05 <src> <dst>` |
| `ex06-fswalk.cpp` | std::filesystem 目录遍历：递归统计 + 目录树复制 | `c++ -std=c++20 -Wall -Wextra ex06-fswalk.cpp -o ex06` | `./ex06 selftest` 或 `./ex06 <dir>` |

## 说明

- ex01 追加 3 条日志到 `/tmp/ph09_app.log` 并回读显示；重复运行不丢历史（追加模式）
- ex02 的 `selftest` 模式 fork 子进程连本机回环（127.0.0.1），父进程 accept 后回显并校验一致性；`server` 模式监听任意端口，`recv` 带 5 秒超时（`SO_RCVTIMEO`），`send` 用 `MSG_NOSIGNAL` 防 SIGPIPE
- ex03 的 `selftest` 模式依次请求 `GET /` 与 `GET /nope`，分别校验 `HTTP/1.1 200 OK` 与 `HTTP/1.1 404 Not Found`；手动模式访问 `http://127.0.0.1:<port>/`
- ex04 解析 `key=value` 配置，错误消息带 文件:行号（如 `/tmp/ph09_bad.conf:2: expected key=value`）；JSON 解析依赖第三方头文件，本仓库不引入，配置解析教学以 key=value 为准（见主文档 3.4）
- ex05 的 `selftest` 生成 256KB 随机二进制文件 → 分块复制 → 校验源/目标 FNV-1a 校验和一致；`gcount()` 处理读不满块
- ex06 的 `selftest` 在 `/tmp` 建 3 层目录树（3 文件 2 子目录）→ 递归统计 → 复制到目标 → 逐项比对；单条错误经 `error_code` 容忍不中断整体
- ex02/ex03/ex05/ex06 的 `selftest` 均在 `/tmp` 下运行、无仓库产物残留；手动模式产生的文件也在 `/tmp`

全部 6 个示例均已在本环境以 `-std=c++20 -Wall -Wextra` 编译零警告并运行通过（已验证）。
