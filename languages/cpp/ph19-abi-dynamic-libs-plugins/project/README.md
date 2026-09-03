# ph19 阶段项目：C ABI 插件式存储引擎 demo

对应 roadmap §19「推荐项目」第一个「C ABI 插件式存储引擎 demo」（另两个——查询执行算子插件 demo、TensorRT plugin 接口阅读 demo——前者与本项目共享全部插件边界手法、可把 engine_api 换成 IExecutor 再落一遍，后者是阅读类任务留作自选）。**边界声明：本项目是「稳定 C ABI + 插件式后端」的机制 demo，不是真存储引擎**——无 WAL、无索引、无缓存、无并发控制、无 B+Tree/LSM 分层，文件后端连压缩都没有（那些属于 roadmap 第 22 节存储引擎与数据库内核专项阶段，目录待建）；本项目只回答一件事：**宿主如何通过一份稳定的 C ABI 功能表，在运行期加载能力不同的存储后端，并安全地管理它们的生命周期**。

## 需求

宿主（store_host）通过 dlopen 加载存储引擎插件，插件向宿主交出一张 `engine_api` 功能表（函数指针 + 接口版本号），宿主经它完成 KV 的 put/get/del。两个后端插件实现同一接口但能力不同：

| 插件 | 实现 | 教学点 |
|------|------|--------|
| `mem_store` | 进程内 `unordered_map`，支持完整 put/get/del | 完整能力后端；get 的返回缓冲生命周期约定（unordered_map 引用在 rehash 后会失效，必须拷贝进 scratch） |
| `file_store` | append-only 日志文件，put 追加一行、get 线性扫描取最后匹配 | 能力差异后端：del 返回 `ENGINE_ERR_UNSUPPORTED`（append-only 的物理删除要 compaction）；get 是真实 IO |

## 功能清单

- [x] 共享 C ABI 头 `storage_api.h`：`extern "C"` + opaque 句柄 + 函数指针表 + 显式错误码枚举（C/C++ 双编译器可 include）
- [x] 插件唯一入口 `engine_get_api()`，返回含 `api_major/api_minor` 的功能表；宿主加载后先校验版本再使用
- [x] 宿主端 RAII（EngineSession）：`destroy(engine)` 严格先于 `dlclose`（成员声明顺序保证析构逆序）
- [x] 能力探测：del 对 mem 是 OK、对 file 是 UNSUPPORTED，宿主按错误码分支而非按插件名特判
- [x] 确定性操作序列与自检断言（put/get/覆盖/缺失 key/del），`make test` 一键跑两个引擎
- [x] 产物全部落在 `build/`，`make clean` 清理

## 验收标准

- [ ] `make clean && make test` 退出码 0：mem_store 与 file_store 两引擎的断言全部 [PASS]；file_store 的 del 以 `ENGINE_ERR_UNSUPPORTED` 分支输出
- [ ] `make run` / `make run-file` 分别跑两个后端，输出 describe 能看出各自能力差异
- [ ] 双编译器 `clang++ -std=c++20 -Wall -Wextra` 编译零警告（Apple clang 21.0.0 / Homebrew clang 21.1.8）
- [ ] 运行输出中 `[host] 引擎已销毁，随后 dlclose 卸载库` 证明 destroy 先于 dlclose（顺序纪律可观察）
- [ ] 代码无裸 new/delete（R.11）——create/destroy 里的 new/delete 是插件边界「谁创建谁销毁」主题，注释已说明；常量用 `constexpr`/枚举（Con.5/Enum.3）、无魔法数字散落（ES.45）
- [ ] 能口头说清：为什么接口必须 C ABI（mangling/vtable/标准库 ABI 三样都不稳定）；为什么宿主不能直接 delete opaque 句柄；为什么 get 返回的指针只保证有效到下一次引擎调用

## 扩展方向（可选）

- **查询执行算子插件**：把本项目 `engine_api` 换成算子接口（`open/next/close` + 行批量语义），实现 scan/filter 两个算子插件——ph17 IExecutor 抽象越过动态库边界的样子，衔接 roadmap 第 23 节向量化执行（roadmap 第 22/23 节，目录待建）
- **版本演进实战**：给 `engine_api` 尾部追加一个 `clear()` 函数指针、`api_minor` 递增，重编 mem 插件后用不升级的旧宿主加载——观察行为并配合 minor 门槛的宿主新版本做正反实验（主文档 3.7 的落地版）
- **file_store 升级**：补 tombstone + compaction，del 从不支持变成真正可用——这正好跨进 roadmap 第 22 节存储引擎内核的门口
- **多插件同时加载**：宿主同时持有 mem + file 两个引擎、按 key 前缀路由——同一进程内多后端共存正是数据库多存储引擎架构（RocksDB/内存引擎并存）的雏形
- **稳定性深挖**：让宿主用 ASan/UBSan 构建（ph16 手法）跑完整操作序列，验证跨 dylib 边界的内存错误能被捕获到——顺带回答「跨库越界到底能不能被 sanitizer 抓到」

## 验证环境

- 实测环境：macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8，C++20（libc++）
- 构建：`make`；运行：`make run`（mem）/ `make run-file`（file）；测试：`make test`；清理：`make clean`
- 验证状态：**已验证**（双编译器 `make test` 全绿退出码 0：两引擎断言 [PASS]、destroy 先于 dlclose 的输出顺序正确、编译零警告）
