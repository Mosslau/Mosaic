// raii/c_file.h —— FILE* 的 RAII 封装（move-only，构造失败抛异常）
#ifndef PH13_RAII_C_FILE_H
#define PH13_RAII_C_FILE_H

#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>

namespace raii {

class CFile {
public:
    CFile(const char* path, const char* mode) : fp_(std::fopen(path, mode)) {
        if (fp_ == nullptr) {
            throw std::runtime_error(std::string("fopen 失败: ") + path);
        }
    }
    ~CFile() {
        if (fp_ != nullptr) std::fclose(fp_);
    }
    CFile(const CFile&) = delete;
    CFile& operator=(const CFile&) = delete;
    CFile(CFile&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {}
    CFile& operator=(CFile&& o) noexcept {
        if (this != &o) {
            if (fp_ != nullptr) std::fclose(fp_);
            fp_ = std::exchange(o.fp_, nullptr);
        }
        return *this;
    }

    std::size_t read(void* buf, std::size_t n) {
        return std::fread(buf, 1, n, fp_);
    }
    void write(const void* buf, std::size_t n) {
        if (std::fwrite(buf, 1, n, fp_) != n) {
            throw std::runtime_error("fwrite 失败");
        }
    }
    bool eof() const { return std::feof(fp_) != 0; }

private:
    std::FILE* fp_;
};

}  // namespace raii

#endif  // PH13_RAII_C_FILE_H
