// ex05-cpp-handle.cpp —— C++ 调 session 句柄库：RAII 包装 + 错误码/错误消息
//
// 编译（macOS）：
//   cc  -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
//   c++ -Wall -Wextra -std=c++17 ex05-cpp-handle.cpp -L/tmp/ph14-ex -lsession \
//       -o /tmp/ph14-ex/ex05-cpp
// 运行：/tmp/ph14-ex/ex05-cpp
//
// 要点：C 的 create/destroy 配对是"手动 RAII"，C++ 侧用析构函数把它
//   变成自动的——构造时 create、析构时 destroy，杜绝忘记释放（
//   C++ Core Guidelines R.11：不在裸指针上手动管理资源）。
#include <cstdint>
#include <cstdio>
#include <stdexcept>

#include "session.h"

class Session {
public:
    explicit Session(const char *name) {
        int err = SESSION_OK;
        s_ = session_create(name, &err);
        if (s_ == nullptr) {
            std::printf("Session(%s) 创建失败: %s\n", name,
                        session_strerror(err));
            throw std::runtime_error("session create failed");
        }
    }
    ~Session() {
        session_destroy(s_);          // 谁 create 谁 destroy：RAII 兜底
    }
    Session(const Session &) = delete;             // 句柄不可复制
    Session &operator=(const Session &) = delete;

    void add(std::int32_t v) {
        session_add(s_, v);
    }
    std::int64_t total() const {
        return session_total(s_);
    }
    const char *name() const {
        return session_name(s_);      // 借用内部指针，生命周期随 session
    }

private:
    session_t *s_;                    // 非拥有裸指针，由 RAII 类统一管理
};

int main() {
    Session s("cpp-caller");
    s.add(40);
    s.add(2);
    std::printf("cpp: name=%s total=%lld\n", s.name(),
                static_cast<long long>(s.total()));
    // s 出作用域自动 session_destroy —— 不泄漏
    return 0;
}
