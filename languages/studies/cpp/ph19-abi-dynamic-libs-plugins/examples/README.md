# examples —— C++ ABI、动态库与插件机制阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`clang++`）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`），C++20（libc++）。**6 个示例全部已验证**（双编译器 `-std=c++20 -Wall -Wextra` 本机实测：编译零警告、运行通过、断言自测全绿、退出码 0）。代码写法以零警告为目标：无裸 new/delete（R.11——ex05 插件对象的新建/销毁是**教学主题**，注释已说明为何 C ABI 边界必须由同一侧创建销毁，见主文档 3.8）、RAII（R.1）、`const` 优先（Con.1/ES.25）、无魔法数字（ES.45）。**动态库与可执行产物一律输出到 /tmp，验证后清理，仓库不落二进制**。以下命令均在 examples/ 目录内执行。

| 文件 | 说明 | 编译/运行 | 验证状态 |
|------|------|-----------|----------|
| `ex01-mangling-demangle.cpp` | name mangling：dladdr 取真实符号名 + `__cxa_demangle` 反解；重载/模板/命名空间的 mangled 名对照；签名变化 → mangled 名变化（链接期护栏） | `clang++ -std=c++20 -Wall -Wextra ex01-mangling-demangle.cpp -o /tmp/ph19cpp-ex01 && /tmp/ph19cpp-ex01` | 已验证（双编译器，断言全绿） |
| `ex02-math.h` + `ex02-extern-c-shared.cpp` + `ex02-host.cpp` | extern "C" 动态库：同一源码里 C 链接（`_math_add`）与 C++ 链接（`__ZN4math3addEii`）符号对照；`__cplusplus` 头守卫；宿主链接调用 + `nm`/`otool` 观察 | 见下方 ex02 | 已验证（双编译器 dylib + 宿主 + nm/otool） |
| `ex03-plugin-add.cpp` + `ex03-plugin-mul.cpp` + `ex03-host.cpp` | dlopen/dlsym/dlerror 插件宿主：同一 C ABI 接口两个插件，运行期切换实现；错误路径（dlsym 缺符号 / dlopen 缺文件）演示 | 见下方 ex03 | 已验证（双编译器，两个插件 + 错误路径） |
| `ex04-visibility-lib.cpp` + `ex04-visibility-host.cpp` | 符号可见性：`-fvisibility=hidden` + `__attribute__((visibility("default")))` 白名单导出，与「默认全导出」做 nm 对照 | 见下方 ex04 | 已验证（双编译器，白名单 vs 全导出 nm 对照清晰） |
| `ex05-plugin-object.cpp` + `ex05-lifecycle-host.cpp` | 插件生命周期与所有权：插件侧 new/delete opaque 对象、宿主经 C ABI destroy、RAII 保证「先 destroy 后 dlclose」 | 见下方 ex05 | 已验证（双编译器，打印显示析构先于卸载） |
| `ex06-abi-evolution.cpp` | ABI 演进仿真：尾部追加 vs 头部插入的 offsetof 对照、老宿主读错数据的字节级证据、插件接口 major/minor 版本检查 | `clang++ -std=c++20 -Wall -Wextra ex06-abi-evolution.cpp -o /tmp/ph19cpp-ex06 && /tmp/ph19cpp-ex06` | 已验证（双编译器，断言全绿） |

> 说明：主文档正文与示例代码共享同一套「C ABI 边界」心智——ex02/ex03/ex04/ex05 是真实动态库边界，ex01/ex06 在单翻译单元里仿真「边界两侧的布局/符号差异」，因为布局漂移与 mangling 规则在同一编译器下可以完整复现。

## 示例 1：name mangling 与 demangle（ex01-mangling-demangle.cpp）

对应主文档 3.2 与 roadmap 学习内容「name mangling」。

```bash
# 1. 编译：
clang++ -std=c++20 -Wall -Wextra ex01-mangling-demangle.cpp -o /tmp/ph19cpp-ex01
# 2. 运行：
/tmp/ph19cpp-ex01
# 3. 用 nm 对照观察二进制里的真名（c++filt 反解）：
nm /tmp/ph19cpp-ex01 | c++filt
```

教学要点：① C++ 函数在二进制层面全部被编码为 Itanium mangled 名——重载、命名空间、类、模板都进符号，签名不同符号就不同；② `dladdr` + `__cxa_demangle` 是运行时拿符号名的通用工具（本机实测 `dli_sname` 已是不带 Mach-O 前缀的 `_Z...` 形态）；③ **ABI 护栏**：签名变化 → mangled 名整个变 → 旧调用方在链接期就 undefined symbol，而不是运行时静默错位——这是 C++ 相比 C 在二进制安全上的意外红利（C 链接没有 mangling，签名变了也能链接过去，全靠版本约定兜底）；④ 平台差异：macOS Mach-O 的 `nm` 输出给符号多加一层 `_` 前缀（`__ZN4math3addEii`），Linux ELF 是 `_ZN4math3addEii`——同一 Itanium mangling，两个平台的符号表现不同。

## 示例 2：extern "C" 动态库（ex02-*）

对应主文档 3.3/3.4 与 roadmap 学习内容「extern C」「动态库构建」。

```bash
# 1. 编译动态库（macOS dylib；Linux 对照见文件头，未在本环境验证）：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex02-extern-c-shared.cpp -o /tmp/libmath.dylib
# 2. 看导出符号：extern "C" 是 _math_add/_math_version，C++ 是 __ZN4math3addEii
nm -gU /tmp/libmath.dylib
nm -gU /tmp/libmath.dylib | c++filt
# 3. 编译并运行宿主（链接期绑定 dylib）：
clang++ -std=c++20 -Wall -Wextra ex02-host.cpp -L/tmp -lmath -o /tmp/ph19cpp-ex02-host
/tmp/ph19cpp-ex02-host
# 4. 看宿主的 dylib 依赖与 install_name：
otool -L /tmp/ph19cpp-ex02-host
```

教学要点：① 头文件用 `__cplusplus` 守卫包 `extern "C"` 声明，C 与 C++ 编译器各自读到正确形态（`ex02-math.h`）；② `nm -gU` 能直观看到两类符号：`_math_add`（C 链接、Mach-O 加一层前缀）vs `__ZN4math3addEii`（C++ mangled）；③ `otool -L` 显示宿主依赖 `/tmp/libmath.dylib`——这个记录在 dylib 里的路径叫 **install_name**，dyld 运行时按它找库；Linux 等价物是 soname（未在本环境验证，机制见主文档 3.4）；④ C++ 符号虽然也能跨 dylib 链接，但把它当公共接口会把宿主绑死在 mangled 名 + 编译器/标准库 ABI 上——插件边界的公共函数应走 extern "C"。

## 示例 3：dlopen 加载插件（ex03-*）

对应主文档 3.5 与 roadmap 学习内容「动态库加载」，是「插件机制」的运行时底座。

```bash
# 1. 编译两个插件（同一接口、不同实现）：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-add.cpp -o /tmp/libop_add.dylib
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-mul.cpp -o /tmp/libop_mul.dylib
# 2. 编译宿主：
clang++ -std=c++20 -Wall -Wextra ex03-host.cpp -o /tmp/ph19cpp-ex03-host
# 3. 运行（默认加载两个插件；也支持传自定义插件路径）：
/tmp/ph19cpp-ex03-host
/tmp/ph19cpp-ex03-host /tmp/libop_mul.dylib
```

教学要点：① dlopen 三步曲——`dlopen(path, flag)` 映射 dylib 返回句柄、`dlsym(handle, name)` 按名字找符号地址、`dlclose(handle)` 引用计数减一；失败全部用 `dlerror()` 取可读错误（本示例把句柄包成 RAII `DlHandle`，符号查找失败给带符号名的错误）；② **宿主换插件零重编译**：同一接口约定下 add/mul 两个插件源码不同，宿主一行不改切换实现；③ dlsym 拿 `void*` cast 成函数指针是 POSIX 惯例，签名不一致在编译期无从检查，只能在调用时炸——所以 dlopen 边界的「声明即契约」比链接期更严格，必须配合版本检查（ex06）与可见性白名单（ex04）使用；④ Windows 对照：`LoadLibrary`/`GetProcAddress`/`FreeLibrary`（主文档 3.5 有对照表，未在本环境验证）。

## 示例 4：符号隐藏与可见性（ex04-*）

对应主文档 3.6 与 roadmap 学习内容中「符号兼容」的库侧部分。

```bash
# 1. 用白名单策略编译（-fvisibility=hidden 是默认，EXPORT 逐个放行）：
clang++ -std=c++20 -Wall -Wextra -fvisibility=hidden -dynamiclib ex04-visibility-lib.cpp -o /tmp/libstore.dylib
# 2. 导出表：应只剩 _store_version/_store_touch 两个白名单符号
nm -gU /tmp/libstore.dylib
# 3. 对照：去掉 -fvisibility=hidden 重编，内部函数 ts_internal_impl 也会出现在导出表
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex04-visibility-lib.cpp -o /tmp/libstore_all.dylib
nm -gU /tmp/libstore_all.dylib
# 4. 编译运行宿主：
clang++ -std=c++20 -Wall -Wextra ex04-visibility-host.cpp -L/tmp -lstore -o /tmp/ph19cpp-ex04-host
/tmp/ph19cpp-ex04-host
```

教学要点：① 不控制时动态库「默认全导出」，内部实现细节暴露给全世界（对照步骤 3 能看到 mangled 的内部函数）；② 工程标准姿势是**默认隐藏 + 白名单导出**：`-fvisibility=hidden` 收掉默认可见性，公共接口逐个加 `__attribute__((visibility("default")))`；③ 收益：符号撞名概率下降（宿主侧两个库各导出同名内部函数时会冲突）、加载器符号解析负担变小、**公共接口清单一眼可见**（`nm -gU` 就是你的 API 快照）；④ 隐藏不是安全机制——符号仍可被 `nm`/逆向找到，它管的是「让宿主编译/链接期依赖不到它们」。

## 示例 5：插件生命周期与所有权纪律（ex05-*）

对应主文档 3.8 与 roadmap 必会概念「谁创建谁销毁要约定清楚」「能避免跨库释放错误」。**本示例的 new/delete 是教学主题而非规范违例**：插件对象在插件侧 `new`、也由插件导出的 `ts_destroy` 在插件侧 `delete`——宿主绝不直接 delete（opaque 不完整类型让编译器直接禁止），这正是「跨边界释放红线」的正确解法。

```bash
# 1. 编译插件：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex05-plugin-object.cpp -o /tmp/libtextstats.dylib
# 2. 编译宿主：
clang++ -std=c++20 -Wall -Wextra ex05-lifecycle-host.cpp -o /tmp/ph19cpp-ex05-host
# 3. 运行（注意打印顺序：ts_destroy 发生在 dlclose 之前）：
/tmp/ph19cpp-ex05-host
```

教学要点：① **谁创建谁销毁**——`new` 在插件侧，`delete` 必须回到插件侧；两侧若来自不同 runtime/堆（Windows 跨 CRT 最典型；macOS/Linux 共享 libc++ 时「碰巧能活」但没有保证），跨侧 delete 是未定义行为；② opaque 前向声明是编译期护栏：宿主对不完整类型既不能 delete 也不能访问成员，销毁的唯一合法路径是插件导出的 `ts_destroy`；③ **销毁必须先于卸载**：dlclose 卸载的是代码，若对象还活着而析构函数代码已被卸载，析构调用就是跳到已卸载内存；本示例用「成员声明顺序 → 逆序析构」的语言保证把 destroy 排在 dlclose 前，输出顺序可验证；④ 宿主侧 RAII 包装持有 dlsym 来的 destroy 函数指针，等价于 `unique_ptr<T, Deleter>` 思路——RAII 越过动态库边界依然有效，只是 deleter 从编译期符号变成运行期查来的函数指针。

## 示例 6：ABI 演进仿真（ex06-abi-evolution.cpp）

对应主文档 3.7 与 roadmap 学习内容「版本兼容」。

```bash
# 1. 编译：
clang++ -std=c++20 -Wall -Wextra ex06-abi-evolution.cpp -o /tmp/ph19cpp-ex06
# 2. 运行：
/tmp/ph19cpp-ex06
```

教学要点：① 动态库升级的接口改法分两类——**尾部追加字段/新增函数**：老字段偏移不变，老宿主照常工作（二进制兼容，只需 minor 递增）；**头部/中间插入字段、改字段类型、改签名**：后续字段全部移位，老宿主按老偏移读到脏数据（本示例 `api=2` 被读成 `1432778632` 的字节级证据）；② C++ 侧有双重护栏：mangling 让「改签名」在链接期暴露（ex01），布局规则让「改 struct」在运行期暴露（本示例）——但**都没有编译器替你检查跨库的旧宿主**，所以必须自己约定接口版本；③ 版本检查的通用模式：导出 `major/minor`，宿主加载后先校验——major 不同 = 二进制不兼容必须拒绝，major 相同 = 尾部追加式演进可直接使用；④ 更细一层的 Linux 机制是 ELF symbol versioning（version script 给符号编版本，见主文档 3.7，**未在本环境验证**——那是 Linux 链接器特性，本机是 macOS）。

## 平台对照备忘

| 主题 | macOS（本环境实测） | Linux ELF（机制一致，未在本环境验证） | Windows（未在本环境验证） |
|------|--------------------|--------------------------------------|--------------------------|
| 动态库格式 | `.dylib`，编译用 `-dynamiclib` | `.so`，编译用 `-fPIC -shared` | `.dll`，需要 `__declspec(dllexport/dllimport)` |
| 库标识 | install_name（`otool -L` 可查） | soname（`readelf -d` 可查） | 文件名即身份，无内嵌路径 |
| 运行期加载 | `dlopen`/`dlsym`/`dlerror`/`dlclose` | 同左 | `LoadLibrary`/`GetProcAddress`/`FreeLibrary` |
| 导出表查看 | `nm -gU` | `nm -D` | `dumpbin /exports` |
| 符号版本 | 无内建机制 | version script（`ld --version-script`） | 无内建机制（靠 DLL 名 + 注册表兼容策略） |

动态库产物只在 /tmp 存活；同一编译命令在 Linux/Windows 上的未验证标注都写在各文件头的「Linux .so 对照」与主文档 3.4/3.5 对照表中。
