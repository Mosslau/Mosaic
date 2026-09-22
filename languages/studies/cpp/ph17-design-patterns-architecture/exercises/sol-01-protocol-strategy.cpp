// exercises/sol-01-protocol-strategy.cpp —— 练习 1 参考实现：用策略模式封装协议解析
// 思路：分帧规则 = 可替换策略（分隔符 / 长度前缀）；上下文 FrameDecoder 持策略、运行期可换，
// 换协议不改解析器本体；长度前缀帧头越界抛可诊断异常。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 exercises/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra sol-01-protocol-strategy.cpp -o /tmp/ph17cpp-sol01
// 运行：/tmp/ph17cpp-sol01
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 预期输出：两个策略的解析演示 + 断言行 + 全部通过，退出码 0
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <cstdint>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

// ============ 策略接口：从字节流中提取消息帧 ============
class IFramingStrategy {
public:
    virtual ~IFramingStrategy() = default;
    virtual std::vector<std::string> extract(std::string_view data) const = 0;
};

// ---- 策略 1：分隔符分帧。简单直观，但不适合 payload 内含分隔符的二进制 ----
class DelimiterFraming final : public IFramingStrategy {
public:
    explicit DelimiterFraming(char delimiter = '\n') : delimiter_(delimiter) {}

    std::vector<std::string> extract(std::string_view data) const override {
        std::vector<std::string> frames;
        std::size_t start = 0;
        while (true) {
            const std::size_t pos = data.find(delimiter_, start);
            const std::size_t end = (pos == std::string_view::npos) ? data.size() : pos;
            if (end > start) {  // 丢弃空帧（语义选择：空消息无意义）
                frames.emplace_back(data.substr(start, end - start));
            }
            if (pos == std::string_view::npos) {
                break;  // 尾部无分隔符的数据也作为最后一帧收下
            }
            start = pos + 1;
        }
        return frames;
    }

private:
    char delimiter_;
};

// ---- 策略 2：长度前缀分帧（4 字节大端长度 + payload）。二进制安全，需诊断越界 ----
class LengthPrefixFraming final : public IFramingStrategy {
public:
    std::vector<std::string> extract(std::string_view data) const override {
        std::vector<std::string> frames;
        std::size_t offset = 0;
        while (offset < data.size()) {
            if (data.size() - offset < 4) {
                throw std::runtime_error("长度前缀分帧: 帧头不足 4 字节");
            }
            const std::uint32_t length = be32(data.substr(offset, 4));
            offset += 4;
            if (data.size() - offset < length) {
                throw std::runtime_error("长度前缀分帧: 帧体长度越界(声明 " +
                                         std::to_string(length) + " 字节)");
            }
            frames.emplace_back(data.substr(offset, length));
            offset += length;
        }
        return frames;
    }

private:
    static std::uint32_t be32(std::string_view bytes) {
        return (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[0])) << 24) |
               (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[1])) << 16) |
               (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[2])) << 8) |
               static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[3]));
    }
};

// ============ 上下文：持有策略，向上层暴露统一入口 ============
class FrameDecoder {
public:
    explicit FrameDecoder(std::unique_ptr<IFramingStrategy> strategy)
        : strategy_(std::move(strategy)) {}

    void set_strategy(std::unique_ptr<IFramingStrategy> strategy) {
        strategy_ = std::move(strategy);  // 运行期换协议
    }

    std::vector<std::string> decode(std::string_view data) const {
        if (!strategy_) {
            throw std::logic_error("FrameDecoder: 未设置分帧策略");
        }
        return strategy_->extract(data);
    }

private:
    std::unique_ptr<IFramingStrategy> strategy_;
};

// ============ 编码辅助（仅测试数据构造用，不属于策略） ============
std::string delimiter_blob(const std::vector<std::string>& messages) {
    std::string out;
    for (const std::string& m : messages) {
        out += m;
        out.push_back('\n');
    }
    return out;
}

std::string length_blob(const std::vector<std::string>& messages) {
    std::string out;
    for (const std::string& m : messages) {
        out.push_back(static_cast<char>(0));
        out.push_back(static_cast<char>(0));
        out.push_back(static_cast<char>(0));
        out.push_back(static_cast<char>(static_cast<unsigned char>(m.size())));
        out += m;
    }
    return out;
}

// ---- 自检小助手 ----
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

template <typename T>
bool vector_eq(const std::vector<std::string>& a, const std::vector<T>& b) {
    if (a.size() != b.size()) {
        return false;
    }
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) {
            return false;
        }
    }
    return true;
}

}  // namespace

int main() {
    // ---- 场景 1：同一帧集，两种策略各自解析各自的字节流 ----
    const std::vector<std::string> messages{"hello", "world"};
    const std::string delim_bytes = delimiter_blob(messages);
    const std::string len_bytes = length_blob(messages);

    FrameDecoder decoder(std::make_unique<DelimiterFraming>());
    const auto by_delim = decoder.decode(delim_bytes);
    check(vector_eq(by_delim, messages), "分隔符分帧: hello/world 两帧");

    decoder.set_strategy(std::make_unique<LengthPrefixFraming>());  // 换协议 = 换策略
    const auto by_len = decoder.decode(len_bytes);
    check(vector_eq(by_len, messages), "长度前缀分帧: hello/world 两帧");

    // ---- 场景 2：同一段字节换策略，解析语义跟着变（协议选择 = 策略选择） ----
    decoder.set_strategy(std::make_unique<DelimiterFraming>());
    const auto junk = decoder.decode(len_bytes);  // 拿长度前缀流按分隔符解析
    check(junk.size() == 1 && junk[0].size() == len_bytes.size(),
          "同一字节流换策略结果不同: 分隔符把长度前缀流读成 1 帧垃圾");
    std::cout << "  [演示] 分隔符策略把 " << len_bytes.size()
              << " 字节的长度前缀流读成 1 帧（流内无 \\n 可切）\n";

    // ---- 场景 3：二进制 payload 含分隔符 → 分隔符分帧失真（教学核心） ----
    const std::string binary{"line1\nline2"};  // payload 内部带 '\n'
    decoder.set_strategy(std::make_unique<DelimiterFraming>());
    const auto split = decoder.decode(delimiter_blob({binary}));
    check(split.size() == 2 && split[0] == "line1" && split[1] == "line2",
          "分隔符分帧被 payload 内的 \\n 切开 → 帧损坏（二进制协议须用长度前缀）");

    decoder.set_strategy(std::make_unique<LengthPrefixFraming>());
    const auto intact = decoder.decode(length_blob({binary}));
    check(intact.size() == 1 && intact[0] == "line1\nline2",
          "长度前缀分帧保住含 \\n 的二进制 payload");

    // ---- 场景 4：畸形流要抛可诊断异常 ----
    // 注意：不能写 std::string{"\x00\x00\x00\x0Aab"} —— C 字符串构造遇 NUL 截断；
    // 必须显式给长度（string_view 或 (ptr, len) 构造）才能保留二进制内容。
    const std::string truncated("\x00\x00\x00\x0A"
                                "ab",
                                6);  // 声明 10 字节，只剩 2 字节
    try {
        (void)decoder.decode(truncated);
        check(false, "帧体越界应抛异常");
    } catch (const std::runtime_error& e) {
        check(std::string(e.what()).find("越界") != std::string::npos,
              "帧体越界抛异常且消息含诊断信息");
    }

    // ---- 场景 5：空帧丢弃语义 ----
    decoder.set_strategy(std::make_unique<DelimiterFraming>());
    const auto no_empty = decoder.decode("\n\nhello\n\n");
    check(vector_eq(no_empty, std::vector<std::string>{"hello"}),
          "分隔符分帧丢弃空帧");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
