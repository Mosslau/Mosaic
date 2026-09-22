# ph09 阶段项目：文件同步工具

对应 roadmap ph09 推荐项目第二个「文件同步工具」（第一个「配置中心客户端」依赖第三方 HTTP/JSON 库，本阶段不引入，作为扩展方向）。工具用 `std::filesystem` 递归扫描 + 大小/修改时间比对 + 分块复制 + FNV-1a 校验，覆盖本阶段文件系统、二进制读写、校验与错误处理几乎全部知识点，也是存储引擎数据搬迁的雏形。

## 需求

- `file_sync.h` / `file_sync.cpp` —— 同步核心：递归扫描源目录，目标缺失或大小/修改时间变化则分块复制并校验校验和，未变化跳过
- `checksum.h` / `checksum.cpp` —— FNV-1a 校验和（滚动 + 整文件）
- `main.cpp` —— CLI 入口 + `--selftest` 自测（/tmp 建测试树 → 同步 → 校验 → 篡改后重同步）
- `Makefile` —— 多文件增量构建

## 功能清单

| 功能 | 说明 |
|------|------|
| 递归扫描 | `recursive_directory_iterator` + `error_code`，单条错误（权限等）容忍继续 |
| 差异比对 | 目标文件存在且大小、修改时间都相同 → 跳过；否则复制 |
| 分块复制 | 8KB 块 `read` + `gcount()` 处理不满块，`ofstream` 二进制写 |
| 校验验证 | 复制后重读目标算 FNV-1a，与源校验和不一致判失败 |
| 目录自动创建 | `create_directories` 递归建目标父目录 |
| 统计输出 | `scanned / copied / skipped / failed / copied_bytes` |
| 自测模式 | `--selftest` 三阶段：首同步全复制 → 再同步全跳过 → 篡改后重同步重新复制 |

## 验收标准

- [ ] `make` 构建成功（增量：`touch file_sync.cpp && make` 只重编对应目标）
- [ ] `./file_sync --selftest` 全部断言通过、退出码 0
- [ ] 首次同步 3 个文件全复制、第二次全跳过、篡改 1 个文件后重同步恰好复制 1 个
- [ ] `-std=c++20 -Wall -Wextra` 编译零警告
- [ ] 仅用标准库 + 系统 API，无第三方依赖；无裸 new/delete，文件全部 RAII
- [ ] 测试产物只在 /tmp（`/tmp/ph09_filesync_test`、`/tmp/ph09_filesync_dst`），仓库无 .o/二进制残留

## 扩展方向

- 加删除同步（目标多余文件 `remove_all`，注意安全确认）
- 加 `--dry-run` 预览模式（只比对不复制）
- 加文件监听（ph08 并发 + 本阶段文件系统结合，变化即同步）
- 换 CRC32 或 SHA-256 校验（更强但更慢）
- **配置中心客户端**（roadmap 另一个推荐项目）：需 HTTP 客户端 + JSON 解析，本阶段不引入第三方库未落地——可用 ex03 的 socket 手写 HTTP、用 key=value 或自研极简 JSON 替代后自行实现

## 验证环境

- Apple clang 21（g++ 兼容），`-std=c++20 -Wall -Wextra`
- 构建：`make`
- 自测：`make selftest`（或 `./file_sync --selftest`）
- 清理：`make clean`
- 验证状态：已验证（编译零警告 + selftest 三阶段断言通过）
