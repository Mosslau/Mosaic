// examples/ex01-factory.cpp —— 工厂模式教学完整版：简单工厂 → 注册表工厂
// 教学点：把「怎么创建」从「怎么使用」中拆出去；返回 unique_ptr 明确所有权（R.11/R.20）；
// 注册表工厂让「新增产品类型」不改工厂本体——开闭原则（OCP）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 examples/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra ex01-factory.cpp -o /tmp/ph17cpp-ex01
// 运行：/tmp/ph17cpp-ex01
// 预期输出（节选）：见 main() 内注释
// 测试：无独立测试目标——main 自带断言式自检（check 计数，失败非零退出）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

namespace {

// ---- 产品接口：Shape。接口只声明「能做什么」，不含状态（C.121 纯接口）----
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
    virtual std::string name() const = 0;
};

class Circle final : public Shape {
public:
    explicit Circle(double radius) : radius_(radius) {}
    double area() const override { return 3.141592653589793 * radius_ * radius_; }
    std::string name() const override { return "circle"; }

private:
    double radius_;
};

class Rectangle final : public Shape {
public:
    Rectangle(double width, double height) : width_(width), height_(height) {}
    double area() const override { return width_ * height_; }
    std::string name() const override { return "rectangle"; }

private:
    double width_;
    double height_;
};

// 新类型加入「注册表路线」时无需触碰任何工厂代码：
class Triangle final : public Shape {
public:
    Triangle(double base, double height) : base_(base), height_(height) {}
    double area() const override { return 0.5 * base_ * height_; }
    std::string name() const override { return "triangle"; }

private:
    double base_;
    double height_;
};

// ---- 路线 1：简单工厂——把散落在调用方的 if/switch 集中到一处 ----
class SimpleShapeFactory {
public:
    // 返回 unique_ptr<Shape>：所有权随返回值明确转移，调用方拿到独占对象
    static std::unique_ptr<Shape> make(const std::string& kind, double a, double b) {
        if (kind == "circle") {
            return std::make_unique<Circle>(a);
        }
        if (kind == "rectangle") {
            return std::make_unique<Rectangle>(a, b);
        }
        throw std::invalid_argument("unknown shape kind: " + kind);  // 未知类型：失败要响亮
    }
};

// ---- 路线 2：注册表工厂——产品注册表（名 → 工厂函数），新增类型靠注册不靠改代码 ----
using ShapeMaker = std::function<std::unique_ptr<Shape>(double, double)>;

class ShapeFactoryRegistry {
public:
    // 注意：这里是「工厂表」单例，不是「产品」单例——别把两者混为一谈
    static ShapeFactoryRegistry& instance() {
        static ShapeFactoryRegistry inst;  // 函数内静态：延迟初始化，线程安全（C++11 起）
        return inst;
    }

    void register_kind(const std::string& kind, ShapeMaker maker) {
        makers_[kind] = std::move(maker);  // 覆盖注册也允许（测试时替换实现常用）
    }

    std::unique_ptr<Shape> make(const std::string& kind, double a, double b) const {
        const auto it = makers_.find(kind);
        if (it == makers_.end()) {
            throw std::invalid_argument("unknown shape kind: " + kind);
        }
        return it->second(a, b);  // 调用注册时保存的工厂函数（type erasure：类型被擦进 std::function）
    }

private:
    std::unordered_map<std::string, ShapeMaker> makers_;
};

// 注册引导：匿名命名空间的静态对象在 main 之前完成注册
// （GoogleTest 的 TEST 自动注册是同一技巧——ph16 ex01 已演示过原理）
struct RegistryBootstrap {
    RegistryBootstrap() {
        auto& registry = ShapeFactoryRegistry::instance();
        registry.register_kind("circle", [](double a, double) {
            return std::make_unique<Circle>(a);
        });
        registry.register_kind("rectangle", [](double a, double b) {
            return std::make_unique<Rectangle>(a, b);
        });
        registry.register_kind("triangle", [](double a, double b) {
            return std::make_unique<Triangle>(a, b);  // 新增类型：只加这一个 lambda
        });
    }
};
RegistryBootstrap g_registry_bootstrap;  // 同一翻译单元内先于 main，顺序安全

// 自检小助手：失败时打印并计数（退出码即 CI 信号，与 ph16 同思路）
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

void require_close(double actual, double expected, const char* what) {
    const bool ok = (actual > expected - 1e-9) && (actual < expected + 1e-9);
    check(ok, what);
}

}  // namespace

int main() {
    // ---- 简单工厂用法：调用方不认识 Circle/Rectangle 具体类型，只依赖 Shape ----
    const auto circle = SimpleShapeFactory::make("circle", 2.0, 0.0);
    require_close(circle->area(), 4.0 * 3.141592653589793, "简单工厂: circle 面积");

    // ---- 注册表工厂：同一接口，更多类型，且工厂本体一行未改 ----
    auto& registry = ShapeFactoryRegistry::instance();
    const auto tri = registry.make("triangle", 4.0, 3.0);
    require_close(tri->area(), 6.0, "注册表工厂: triangle 面积");
    check(tri->name() == "triangle", "注册表工厂: name() 正确");

    // ---- 未知类型：异常携带可诊断信息（ph09 必会概念：失败要可诊断）----
    try {
        (void)registry.make("hexagon", 1.0, 1.0);
        check(false, "未知类型应抛异常");
    } catch (const std::invalid_argument& e) {
        check(std::string(e.what()).find("hexagon") != std::string::npos,
              "未知类型抛异常且消息含类型名");
    }

    // ---- 遍历全部已注册类型：注册表可枚举，这是简单工厂做不到的 ----
    for (const char* kind : {"circle", "rectangle", "triangle"}) {
        const auto s = registry.make(kind, 3.0, 4.0);
        std::cout << "  已注册: " << kind << "，面积 " << s->area() << '\n';
    }

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
