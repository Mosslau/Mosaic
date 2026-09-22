# exercises —— C++ ABI、动态库与插件机制阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~3 顺序完成。练习 1~3 与 roadmap §19「练习」小节一一对应（写一个动态库 / 用 dlopen/LoadLibrary 加载插件 / 设计插件版本检查）。参考实现在 `sol-*` 文件中，做完再看。

> ⚠️ 每题都要求 `clang++ -std=c++20 -Wall -Wextra` 零警告、退出码语义正确（0 全过 / 非 0 有失败）。参考实现**已验证**（Apple clang 21.0.0 本机实测：编译零警告、运行自测通过）。动态库/可执行产物一律输出到 /tmp，验证后清理。需要「同一接口、不同实现」时，接口约定就是几行注释——这是 dlopen 边界的常态，请习惯没有共享头文件的世界。

## 练习 1：写一个动态库（★★★）

- **目标**：从零构建一个 C ABI 动态库（extern "C"），宿主**链接期**调用它，并用 `nm` 观察导出符号的 C 链接形态
- **要求**：
    - 库提供 2~3 个几何函数（如 `rect_area(double, double)`、`rect_perimeter(double, double)`），全部 `extern "C"`，头文件用 `__cplusplus` 守卫（C/C++ 双编译器都能 include）
    - 用 `-dynamiclib`（macOS）/ `-fPIC -shared`（Linux）编译到 /tmp
    - 宿主 include 同一份头、链接调用，输入（宽 4、高 5）应输出面积 20、周长 18
    - 附加观察：库里放一个**非** extern "C" 的 C++ 函数，`nm -gU` 对比它与 extern "C" 函数符号形态差异
- **验收**：运行输出面积/周长正确、退出码 0；`nm -gU` 能看到 `_rect_area` 这类未 mangling 符号与 mangled 的 C++ 符号并存；能口头解释 extern "C" 的作用与 C++ 符号为何带名字编码（主文档 3.2/3.3）
- **提示**：库实现处不需要重复写 `extern "C"`，头文件里声明一次即可；宿主调用 C++ 函数需要与库完全一致的声明，链接器才找得到 mangled 符号（参考实现 `sol-01-geometry-lib.cpp` + `sol-01-host.cpp`）

## 练习 2：用 dlopen 加载插件（★★★）

- **目标**：写一个插件（独立 dylib，extern "C" 导出算子）与一个运行期加载它的宿主，宿主不链接插件也能调用其函数
- **要求**：
    - 插件导出 C ABI 接口，如 `extern "C" const char* op_name(void)` 与 `extern "C" long long op_sum(const long long* xs, long long n)`（对数组求和）
    - 宿主用 `dlopen`（写注释对照 Windows `LoadLibrary`）加载插件路径，`dlsym` 逐个取函数指针，`dlclose` 收尾；所有失败走 `dlerror` 输出可诊断错误
    - 宿主接收命令行参数指定插件路径；对数组 `{1,2,3,4,5,6}` 调用 op_sum，输出结果与 op_name
    - 至少演示一个错误路径：给宿主传一个不存在路径或 dlsym 一个不存在的符号，宿主应报错且退出码非 0
- **验收**：正常路径输出 op_name 与和 21、退出码 0；错误路径打印含原因的错误、退出码非 0；能说明 dlopen 三步曲与句柄的生命周期归属（谁负责 dlclose）
- **提示**：符号查找的 `void*` 到函数指针的转换是 dlopen 边界的惯例写法；把句柄与函数指针包进 RAII 类能让错误路径也自动收尾（参考实现 `sol-02-operator-plugin.cpp` + `sol-02-host.cpp`）

## 练习 3：设计插件版本检查（★★★）

- **目标**：给插件接口加版本号，宿主加载后先校验再使用；对版本不足的插件给出可诊断错误而非静默错乱
- **要求**：
    - 插件导出 `extern "C" int plugin_version_major(void)` 与 `extern "C" int plugin_version_minor(void)`，外加一个 `plugin_behavior()`（可返回 1 或 2，版本差异演示用）
    - 同一个插件源用宏（如 `-DPLUGIN_MAJOR=1` / `-DPLUGIN_MAJOR=2`）编译成 v1、v2 两个库，v1 代表「老版本插件」
    - 宿主声明自己的要求（如 major 必须 ≥2），加载后先取版本再判断：不合格 → 打印明确错误（含宿主需求与插件实况）并拒绝调用，退出码非 0；合格 → 正常调用
- **验收**：对 v1 库，宿主输出「版本不兼容：宿主需 major≥2，插件提供 major=1」类信息且退出码非 0；对 v2 库正常输出、退出码 0；能解释为什么版本检查必须在 dlsym 业务函数**之前**做（避免拿到旧布局/旧签名还继续跑）
- **提示**：major/minor 语义可参考主文档 3.7：major 不同=二进制不兼容（拒绝）；major 相同=尾部追加式演进（放行，必要时叠加 minor 门槛）；把「取版本→校验→用业务」三步按顺序想清楚（参考实现 `sol-03-versioned-plugin.cpp` + `sol-03-host.cpp`）

> **提示**：练习 1 的模板在 examples/ex02（extern "C" + __cplusplus 守卫 + nm 观察）；练习 2 的模板在 examples/ex03（dlopen 三步曲 + RAII 句柄）；练习 3 的版本约定与「拒绝旧版本」的判定思路在 examples/ex06。卡住先看 examples/ 的手法，不是抄答案，是学边界纪律。
