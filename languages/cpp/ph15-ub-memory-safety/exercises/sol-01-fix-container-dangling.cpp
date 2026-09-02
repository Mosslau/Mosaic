// sol-01-fix-container-dangling.cpp —— 练习 1 参考实现：修复“缓存容器元素指针/引用”的悬空
// 练习 1 要求：坏版本类 Registry 在构造时缓存 &names_.front()，随后的 add() 可能触发
//   vector 扩容重分配，缓存的指针悬空（heap-use-after-free）。请修复为不悬空版本并说明
//   修复思路（roadmap 练习 1「修复悬空引用示例」）。
//
// 坏版本（有 bug，勿这样写）：
//   class Registry {
//   public:
//       explicit Registry(std::vector<std::string> names)
//           : names_(std::move(names)) { first_ = &names_.front(); }  // 缓存元素指针
//       void add(std::string name) { names_.push_back(std::move(name)); } // 可能扩容
//       const std::string& first() const { return *first_; }
//   private:
//       std::vector<std::string> names_;
//       const std::string* first_;        // ← 扩容后指向已释放的旧缓冲区
//   };
//
// 本机实测（坏版本，Apple clang 21.0.0，-O0 -g -fsanitize=address，add 至扩容后调 first()）：
//   ERROR: AddressSanitizer: heap-use-after-free on address ...
//   READ of size 4 at ... thread T0          （退出码 134，与 examples/ex02 扩容失效同源）
//
// 修复思路：
//   1. 不缓存“指向容器内部”的指针/引用——容器的每次结构性修改（扩容/erase/clear/析构）
//      都可能让它们失效（std 标准保证：重分配使全部引用、指针、迭代器失效）；
//   2. 需要元素时“现取”：按下标访问（引用只活到本次调用结束）或按值返回（值语义，
//      后续容器变化不影响拿到的副本）；
//   3. 类若确实要长期持有“某个名字”，用值成员（std::string）而不是容器元素指针。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-01-fix-container-dangling.cpp -o /tmp/ph15-sol-01
// 运行：    /tmp/ph15-sol-01
// 验证状态：已验证（两种编译器零警告、输出一致；加 -fsanitize=address,undefined 运行零报告）
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

// 修复版：不缓存容器元素指针，全部访问“现取”
class Registry {
public:
    explicit Registry(std::vector<std::string> names) : names_(std::move(names)) {}

    void add(std::string name) { names_.push_back(std::move(name)); }
    void clear() { names_.clear(); }

    std::size_t size() const { return names_.size(); }

    // 现取模式 A：下标访问，返回的引用只活到本次调用结束（调用方不得跨容器修改持有）
    const std::string& name_at(std::size_t i) const { return names_.at(i); }

    // 现取模式 B：按值返回（值语义），拿到的副本与容器后续变化无关
    std::string first_copy() const { return names_.front(); }

private:
    std::vector<std::string> names_;
};

int main() {
    std::printf("[A] 修复前（坏版本）：缓存 &names_.front()，add 扩容后 first() 悬空\n");
    std::printf("    ASan 实测 heap-use-after-free + READ of size 4，退出码 134（见文件头）\n");

    std::printf("[B] 修复后：不缓存容器元素指针，需要时现取\n");
    Registry reg({"motor", "pump"});
    reg.add("valve");                       // 触发扩容（cap 2 → 4，实测）——不再有旧指针可悬空
    std::printf("    names: ");
    for (std::size_t i = 0; i < reg.size(); ++i) {
        std::printf("%s%s", i == 0 ? "" : " ", reg.name_at(i).c_str());
    }
    std::printf("\n");

    std::printf("[C] 扩容后逐元素访问正常：name_at(0..2) = %s / %s / %s\n",
                reg.name_at(0).c_str(), reg.name_at(1).c_str(), reg.name_at(2).c_str());

    std::printf("[D] 按值返回与容器解耦：first_copy() 拿到副本后 clear() 不影响它\n");
    std::string snapshot = reg.first_copy();
    reg.clear();
    std::printf("    clear() 后 first_copy() 的副本仍为 \"%s\"（值语义，无悬空）\n",
                snapshot.c_str());

    std::printf("[E] 结论：引用/迭代器是“借来的眼睛”，随容器结构变化失效——\n");
    std::printf("    现取（下标/按值）代替长期持有；确需长期持有用值成员\n");
    return 0;
}
// 本机实测（两种编译器一致，零警告；+ASan+UBSan 零报告）：
//   [B] names: motor pump valve
//   [C] name_at(0..2) = motor / pump / valve
//   [D] clear() 后 first_copy() 的副本仍为 "motor"
