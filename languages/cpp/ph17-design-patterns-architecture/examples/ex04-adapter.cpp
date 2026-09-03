// examples/ex04-adapter.cpp —— 适配器模式教学完整版：让不兼容接口协作
// 教学点：新代码依赖目标接口 ILogSink，老模块（第三方/历史代码，改不得）只有自家接口；
// 对象适配器把 LegacyTextSink 包成 ILogSink（组合优先于继承）；C 风格自由函数也能用
// 函数适配器（std::function）接进来；适配器只转接口不转语义——语义错位是适配器的坑。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 examples/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra ex04-adapter.cpp -o /tmp/ph17cpp-ex04
// 运行：/tmp/ph17cpp-ex04
// 预期输出：三种来源各一行（见 main() 内注释）
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <cstdio>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>

namespace {

// ============ 新代码的目标接口：日志后端。上层只依赖它（依赖方向指向抽象） ============
class ILogSink {
public:
    virtual ~ILogSink() = default;
    virtual void write(const std::string& level, const std::string& message) = 0;
};

// 目标接口的一个原生实现（对照组）
class StreamLogSink final : public ILogSink {
public:
    explicit StreamLogSink(std::ostream& out) : out_(out) {}
    void write(const std::string& level, const std::string& message) override {
        out_ << "[sink] " << level << ": " << message << '\n';
    }

private:
    std::ostream& out_;
};

// 业务层：只依赖 ILogSink，不知道背后是原生实现还是适配器
class BusinessLogger {
public:
    explicit BusinessLogger(std::unique_ptr<ILogSink> sink) : sink_(std::move(sink)) {}
    void log_event(const std::string& message) {
        if (sink_) {
            sink_->write("INFO", message);
        }
    }

private:
    std::unique_ptr<ILogSink> sink_;  // 构造注入：换后端 = 换注入对象（DI 思想，见 3.6）
};

// ============ 老模块：第三方/历史代码，接口改不得（演示用） ============
// 只有 append_line(text)，没有「级别」概念——语义缺口由适配器补齐（补成级别前缀）
class LegacyTextSink {
public:
    explicit LegacyTextSink(std::ostream& out) : out_(out) {}
    void append_line(const std::string& text) { out_ << "[legacy] " << text << '\n'; }

private:
    std::ostream& out_;
};

// ============ 对象适配器：把 LegacyTextSink 适配成 ILogSink ============
class LegacySinkAdapter final : public ILogSink {
public:
    // 适配器不拥有老对象：用引用注入（老对象生命周期由调用方保证——组合根管辖）
    explicit LegacySinkAdapter(LegacyTextSink& legacy) : legacy_(legacy) {}

    void write(const std::string& level, const std::string& message) override {
        // 接口转换：write(level, message) → append_line("level: message")
        legacy_.append_line(level + ": " + message);
    }

private:
    LegacyTextSink& legacy_;  // 组合（持引用）而非继承老类——组合优先于继承
};

// ============ 函数适配器：C 风格自由函数也接进 std::function（单函数接口免建类） ============
// 模拟一段 C API：void legacy_fputs_sink(const char* line, void* ctx)
struct CFileCtx {
    std::FILE* file;
};

void legacy_fputs_sink(const char* line, void* ctx) {
    auto* c = static_cast<CFileCtx*>(ctx);
    std::fputs(line, c->file);
    std::fputc('\n', c->file);
}

// 把 C 回调包成 ILogSink：函数适配器（组合 C 调用点 + 上下文）
class CFunctionAdapter final : public ILogSink {
public:
    explicit CFunctionAdapter(void (*fn)(const char*, void*), void* ctx)
        : fn_(fn), ctx_(ctx) {}

    void write(const std::string& level, const std::string& message) override {
        const std::string line = level + ": " + message;
        fn_(line.c_str(), ctx_);
    }

private:
    void (*fn_)(const char*, void*);
    void* ctx_;  // 非拥有：CFileCtx 由组合根创建并保证存活
};

// ---- 自检小助手 ----
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

}  // namespace

int main() {
    // ---- 场景：业务层换了三种后端，代码零改动（只改注入对象） ----
    BusinessLogger with_native(std::make_unique<StreamLogSink>(std::cout));
    with_native.log_event("native backend");  // [sink] INFO: native backend

    LegacyTextSink legacy(std::cout);
    BusinessLogger with_adapter(std::make_unique<LegacySinkAdapter>(legacy));
    with_adapter.log_event("adapted backend");  // [legacy] INFO: adapted backend

    CFileCtx ctx{stdout};
    BusinessLogger with_c_api(std::make_unique<CFunctionAdapter>(legacy_fputs_sink, &ctx));
    with_c_api.log_event("C function backend");  // INFO: C function backend

    // ---- 自检：捕获输出，验证适配器接口转换的正确性 ----
    std::ostringstream captured;
    LegacyTextSink probe(captured);
    LegacySinkAdapter adapter(probe);
    adapter.write("ERROR", "boom");  // 目标接口调用
    check(captured.str() == "[legacy] ERROR: boom\n",
          "对象适配器：write(level, message) 正确转成 append_line 格式");

    // C 函数适配器版本（见 main 上方演示）：C 回调要断言输出需打开真实文件
    // （fmemopen 非标准），本示例只验证接口形状，故此处不再加断言。

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
