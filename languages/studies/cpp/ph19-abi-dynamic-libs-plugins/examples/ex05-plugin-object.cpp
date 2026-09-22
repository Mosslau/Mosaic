// examples/ex05-plugin-object.cpp —— 提供 opaque 对象的插件（生命周期教学）
// 教学点：roadmap 必会概念「谁创建谁销毁要约定清楚」。插件向宿主暴露一个
// opaque（不透明）对象 text_stats：
//   - 对象由插件侧 new 出来，也必须由插件侧 delete——两侧若来自不同
//     runtime/分配器（Windows 上尤其危险：各 CRT 各有各的堆；macOS/Linux
//     共享 libc++ + libsystem 的 malloc 时"碰巧"能活，但没有任何保证），
//     跨侧 delete 是未定义行为。所以销毁永远走 ts_destroy() 而不是宿主 delete。
//   - 宿主把 text_stats 当前向声明成不完整类型，编译器直接从语法上禁止
//     宿主对它做 delete/取成员——opaque 指针 + 工厂/销毁函数是 C ABI 边界
//     的标准形状。
//   - 宿主侧 RAII 包装（ex05-lifecycle-host.cpp）绑定「析构时调 ts_destroy」，
//     保证销毁与 dlclose 的顺序正确（先 destroy 对象、再卸载库）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib ex05-plugin-object.cpp -o /tmp/libtextstats.dylib
// 验证状态：已验证（双编译器实测：编译零警告）

#include <cstddef>
#include <string>
#include <vector>

// opaque 类型：完整定义只存在于插件这一侧
struct text_stats {
    std::vector<std::string> words;
    std::size_t total_len = 0;
};

extern "C" text_stats* ts_create(void) {
    // 在插件侧分配——同一个 operator new，将来也必须是同一侧的 operator delete
    return new text_stats;
}

extern "C" void ts_destroy(text_stats* s) {
    // 销毁责任回到插件侧：delete 与上面的 new 配对（R.11 的边界例外，
    // 见文件头注释——这正是"谁创建谁销毁"纪律的落点）
    delete s;
}

extern "C" void ts_add(text_stats* s, const char* word) {
    if (s == nullptr || word == nullptr) {
        return;
    }
    const std::string w(word);  // 立刻拷贝：word 是宿主侧的临时缓冲，只在调用期有效
    s->total_len += w.size();
    s->words.push_back(std::move(w));
}

extern "C" const char* ts_summary(const text_stats* s) {
    // 返回指向插件内部缓冲的指针：只在下一次 ts_add/ts_destroy 前有效。
    // C ABI 边界上无法返回 std::string，只能返回裸指针 + 约定生命周期。
    static thread_local std::string buffer;  // thread_local：避免反复分配又保持线程安全
    buffer.clear();
    if (s == nullptr) {
        buffer = "(null)";
    } else {
        buffer = std::to_string(s->words.size()) + " words, " +
                 std::to_string(s->total_len) + " chars";
    }
    return buffer.c_str();
}
