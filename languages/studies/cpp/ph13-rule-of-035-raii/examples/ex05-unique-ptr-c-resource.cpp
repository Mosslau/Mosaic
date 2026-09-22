// ex05-unique-ptr-c-resource.cpp —— unique_ptr 管理 C 资源：FILE* / fd / malloc
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex05-unique-ptr-c-resource.cpp -o /tmp/ph13-ex05
// 运行：/tmp/ph13-ex05（写 /tmp 临时文件，结束时删除）
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <fcntl.h>
#include <unistd.h>

// roadmap §13 示例的完整版：decltype(&fclose) 把释放函数编码进类型
using FilePtr = std::unique_ptr<std::FILE, decltype(&std::fclose)>;

FilePtr open_file(const char* path, const char* mode) {
    FilePtr fp(std::fopen(path, mode), &std::fclose);
    if (fp == nullptr) throw std::runtime_error("无法打开文件");
    std::printf("  fopen 成功（fclose 已绑定为 deleter）\n");
    return fp;
}

// POSIX fd：close 包装成无状态仿函数
struct FdCloser {
    void operator()(int* p) const noexcept {
        std::printf("  close(fd=%d)（deleter 自动调用）\n", *p);
        ::close(*p);
        delete p;
    }
};
using UniqueFdBox = std::unique_ptr<int, FdCloser>;

UniqueFdBox open_fd(const char* path) {
    int fd = ::open(path, O_RDONLY);
    if (fd < 0) throw std::runtime_error("open 失败");
    return UniqueFdBox(new int(fd), FdCloser{});   // fd 装盒，交给 deleter
}

// malloc 内存：free 作为 deleter
using MallocPtr = std::unique_ptr<char, decltype(&std::free)>;

const char* kPath = "/tmp/ph13-ex05-demo.txt";

// 异常路径演示：fd 打开后抛异常，close 是否照常执行？
void throw_with_open_fd() {
    UniqueFdBox fd = open_fd(kPath);
    std::printf("  fd 已打开，即将抛异常…\n");
    throw std::runtime_error("读取中出错");   // 栈展开 → FdCloser 兜底
}

int main() {
    std::printf("[1] unique_ptr 管理 FILE*（roadmap §13 示例的完整版）\n");
    {
        FilePtr fp = open_file(kPath, "w");
        std::fprintf(fp.get(), "via unique_ptr\n");
    }   // 作用域结束自动 fclose

    std::printf("[2] unique_ptr 管理 POSIX fd\n");
    {
        FilePtr fp = open_file(kPath, "a");
        std::fprintf(fp.get(), "second line\n");
    }
    {
        UniqueFdBox fd = open_fd(kPath);
        char buf[64];
        const ssize_t n = ::read(*fd, buf, sizeof buf - 1);
        buf[n > 0 ? n : 0] = '\0';
        std::printf("  read %zd 字节: %s", n, buf);
    }   // 自动 close

    std::printf("[3] 异常路径：fd 打开后抛异常，close 照常执行（E.6）\n");
    try {
        throw_with_open_fd();
    } catch (const std::runtime_error& e) {
        std::printf("  捕获: %s（fd 已在栈展开时关闭）\n", e.what());
    }

    std::printf("[4] unique_ptr 管理 malloc 内存\n");
    {
        MallocPtr p(static_cast<char*>(std::malloc(32)), &std::free);
        std::snprintf(p.get(), 32, "malloc 由 unique_ptr 托管");
        std::printf("  %s\n", p.get());
    }   // 自动 free
    std::remove(kPath);
    std::printf("[5] 临时文件已删除\n");
    return 0;
}
