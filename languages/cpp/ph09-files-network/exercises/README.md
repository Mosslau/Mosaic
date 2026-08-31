# exercises —— 文件、网络与系统编程阶段练习

完成顺序建议：按 1~5 顺序完成。参考实现在 `sol-*` 文件中，做完再看。验证环境：Apple clang 21（g++ 兼容），`c++ -std=c++20 -Wall -Wextra`（练习 2 用线程需加 `-pthread`）。练习 1~4 与 roadmap ph09「练习」小节的四项承诺一一对应，练习 5 对应 roadmap「学习内容」中的 JSON/配置文件（主文档 3.4 与示例 4）。

## 练习 1：日志文件系统（★）

- **目标**：用 fstream 实现追加模式的日志类，写入带时间戳与级别
- **要求**：
  - `LogFile` 类：构造时以 `std::ios::app` 打开，析构自动关闭（RAII）
  - `write(level, msg)` 输出 `时间戳 [级别] 消息`，每次写后检查流状态，失败抛异常
  - 时间戳格式 `YYYY-MM-DD HH:MM:SS`；文件路径写死 `/tmp/ph09_ex1.log` 即可
  - 思考（不必写代码）：为什么追加模式比 `std::ios::trunc` 更适合日志？`'\n'` 与 `std::endl` 有什么区别？
- **验收**：编译零警告；先 `rm -f /tmp/ph09_ex1.log`，运行一次后文件恰好 2 行（`INFO` 被过滤、`WARN`/`ERROR` 落盘）；再运行一次后文件 4 行（追加不丢历史）；退出码 0

## 练习 2：TCP echo server（★★）

- **目标**：用 RAII 封装 socket，实现 echo 服务端与客户端
- **要求**：
  - `Socket` 类：禁拷贝、允移动、析构自动 `close`
  - 服务端 `socket → bind → listen → accept`，`recv` 循环收到什么回显什么，`send` 加 `MSG_NOSIGNAL`
  - `recv` 带超时（`SO_RCVTIMEO`，5 秒）；连接关闭条件 `recv <= 0`
  - 客户端连接 `127.0.0.1`，发送 `hello echo\n`，校验回显一致
  - 进阶（选做）：用 `std::thread` 支持多客户端（thread-per-connection，编译加 `-pthread`）
- **验收**：编译零警告；`./sol-02 server 9000` + 另开终端 `./sol-02 client 9000` 回显一致；服务端超时不挂死

## 练习 3：简单 HTTP server（★★）

- **目标**：解析 HTTP 请求行，返回带 Content-Length 的 200/404 响应
- **要求**：
  - 服务端监听端口，读请求 → 取第一行请求行（`METHOD 路径 版本`）→ 解析路径
  - `GET /` 返回 `HTTP/1.1 200 OK`，其余路径返回 `HTTP/1.1 404 Not Found`
  - 响应必须带 `Content-Length` 头与 `Connection: close`
  - 提示：`req.substr(0, req.find("\r\n"))` 取请求行；`line.find(' ')` 定位路径
- **验收**：编译零警告；`./sol-03 8080` 后浏览器/curl 访问 `/` 得 200、`/nope` 得 404；`Content-Length` 与实际 body 字节数一致

## 练习 4：文件传输工具（★★）

- **目标**：二进制分块读写 + 校验和验证
- **要求**：
  - 两个子命令：`send <src> <dst>` 分块复制（`read` + `gcount()` 处理不满块），`verify <file> <checksum>` 校验文件校验和
  - 校验和用 FNV-1a（初值 `2166136261u`，乘子 `16777619u`），输出十六进制
  - 复制失败（源不存在、磁盘满）返回非零并打印原因
  - 提示：`std::ifstream in(src, std::ios::binary)`；`in.eof()` 判定正常读完
- **验收**：编译零警告；`send` 复制后 `verify` 校验通过；用 `dd` 或随机字节生成 1MB 以上文件测试；损坏场景（手动改一个字节）`verify` 应失败

## 练习 5：配置文件解析（★★）

- **目标**：key=value 配置解析，错误带文件与行号
- **要求**：
  - 支持空行与 `#` 注释；`key = value` 两侧空白裁剪
  - `get_int(key, def)` 与 `get_str(key, def)`：缺键返回默认值，值非整数时抛带行号异常
  - 非法行（不含 `=`）报错格式统一为 `文件:行号: 原因`
  - 提示：错误类继承 `std::runtime_error`，构造时拼 `file + ":" + std::to_string(line)`
- **验收**：编译零警告；正常配置 `port=8080 workers=4` 解析正确；缺键返回默认值；含 `abc` 行的配置报 `xxx.conf:2: expected key=value` 且退出码非零

> **提示**：参考实现仅作对照，先独立完成再复盘；sol-* 与 examples/ 中对应示例的实现思路不同（如级别过滤、超时、校验验证），对比两者是很好的学习材料。进阶玩法（length-prefix 帧协议、JSON 解析、fork/exec 命令执行器）见主文档第 7 章。
