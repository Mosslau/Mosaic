// file_sync.cpp —— 目录同步核心实现
#include "file_sync.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

#include "checksum.h"

namespace filesync {

namespace fs = std::filesystem;

// 分块复制 src → dst，返回累计校验和
static bool copy_chunked(const fs::path& src, const fs::path& dst,
                         std::uint32_t* sum_out) {
    std::ifstream in(src, std::ios::binary);
    std::ofstream out(dst, std::ios::binary);
    if (!in || !out) return false;
    char buf[8192];
    std::uint32_t sum = fnv1a(nullptr, 0);
    for (;;) {
        in.read(buf, sizeof(buf));
        const std::streamsize n = in.gcount();
        if (n > 0) {
            out.write(buf, n);
            sum = fnv1a(buf, static_cast<std::size_t>(n), sum);
        }
        if (in.eof()) break;
        if (in.fail() || !out) return false;
    }
    *sum_out = sum;
    return true;
}

// 目标文件是否与源一致：存在 + 大小相同 + 修改时间相同
static bool up_to_date(const fs::path& src, const fs::path& dst) {
    std::error_code ec;
    const auto src_size = fs::file_size(src, ec);
    if (ec) return false;
    const auto dst_size = fs::file_size(dst, ec);
    if (ec) return false;
    if (src_size != dst_size) return false;
    const auto src_mtime = fs::last_write_time(src, ec);
    if (ec) return false;
    const auto dst_mtime = fs::last_write_time(dst, ec);
    return !ec && src_mtime == dst_mtime;
}

SyncStats sync_tree(const fs::path& src, const fs::path& dst,
                    std::string* err_out) {
    SyncStats st;
    std::error_code ec;

    // 源必须存在且是目录
    if (!fs::is_directory(src, ec)) {
        if (err_out) *err_out = "source is not a directory: " + src.string();
        return st;
    }
    fs::create_directories(dst, ec);
    if (ec) {
        if (err_out) *err_out = "cannot create dst: " + ec.message();
        return st;
    }

    // 递归遍历源，逐文件比对
    for (fs::recursive_directory_iterator it(src, ec), end; it != end;
         it.increment(ec)) {
        if (ec) {
            std::cerr << "[warn] " << ec.message() << '\n';
            ec.clear();
            continue;
        }
        if (!it->is_regular_file(ec)) continue;   // 只同步普通文件，目录自动创建
        const fs::path rel = it->path().lexically_relative(src);
        const fs::path out = dst / rel;
        fs::create_directories(out.parent_path(), ec);
        if (ec) {
            if (err_out) *err_out = "cannot create dir: " + ec.message();
            ++st.failed;
            continue;
        }
        ++st.scanned;
        if (up_to_date(it->path(), out)) {        // 无变化：跳过
            ++st.skipped;
            continue;
        }
        std::uint32_t sum = 0;
        if (!copy_chunked(it->path(), out, &sum)) {
            if (err_out) *err_out = "copy failed: " + it->path().string();
            ++st.failed;
            continue;
        }
        // 复制后把目标 mtime 对齐源（rsync 风格），使下次同步按时间戳判定为已同步
        const auto src_mtime = fs::last_write_time(it->path(), ec);
        if (!ec) fs::last_write_time(out, src_mtime, ec);
        // 校验：目标校验和必须与源一致
        std::uint32_t dst_sum = 0;
        if (!file_checksum(out, &dst_sum) || dst_sum != sum) {
            if (err_out) *err_out = "checksum mismatch: " + it->path().string();
            ++st.failed;
            continue;
        }
        ++st.copied;
        st.copied_bytes += static_cast<std::size_t>(it->file_size(ec));
        std::cout << "[sync] " << rel.string() << " (" << it->file_size(ec)
                  << " bytes, checksum 0x" << std::hex << sum << std::dec
                  << ")\n";
    }
    return st;
}

}  // namespace filesync
