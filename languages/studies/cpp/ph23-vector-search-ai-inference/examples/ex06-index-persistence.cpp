// ex06-index-persistence.cpp —— 向量索引持久化：不可变快照文件的写入/载入/校验（SSTable 心智平移）
// 对应 ph23 主文档 3.7 与 roadmap §23「向量索引持久化」；兑现 ph22 预告——
//   把 ph22 的 SSTable/Buffer Pool 磁盘形态平移到向量库：这里的"数据集快照"就是
//   向量库的 SSTable：一次 flush 写成的不可变文件，崩溃/重启后原样读回。
// 教学点：
//   ① 文件布局借鉴 ph22 3.3 的 SSTable 骨架：[定长 header] [id 表] [原始 float 矩阵] [尾校验]。
//      header 定长 → 打开先读头就知道"去哪找数据"；id 表让"向量行号"能映射回业务 id；
//      float 矩阵按行主序连续存放 = 距离计算时缓存友好的布局（呼应 3.3 SIMD）；
//   ② 不可变 + 整文件校验：写快照时对全文件算一个校验尾随写；读时先校验再暴露——
//      "不可变文件要么完整可见、要么拒绝服务"，与 ph22 ex02/sol-02 的 block 校验同纪律；
//   ③ 崩溃语义：写快照 = 先写临时文件 + fsync + rename 原子替换（旧文件不可变，
//      新文件写坏大不了删掉重来——不可变文件不需要就地修复）；
//   ④ 与 Buffer Pool 的关系（ph22 3.7 预告兑现点）：本示例"整文件读入内存"是教学简化；
//      换成"页粒度 + LRU 帧缓存 + 只把热页留在内存"即生产形态——文件本身仍不可变，
//      所以缓存里只有干净页、无需写回（SSTable 的三个好处原样继承）；
//   ⑤ 生产向量库的持久化 = 本示例快照文件 × N 代（写路径 WAL/增量段 + 后台合并成新快照，
//      即 ph22 WAL + Compaction 的翻版），见主文档 3.7 的"快照 + 增量日志"两段式。
// 资源管理：RAII（std::ofstream/ifstream 析构关闭，R.1）；读入内存后全用 std::vector（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex06-index-persistence.cpp -o /tmp/ph23-ex06 && /tmp/ph23-ex06
// 验证状态：已验证（零警告、断言全绿、退出码 0；临时文件写 /tmp 退出自删）

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace persist {

// 文件描述符的 RAII 封装（cpp-coding-standards R.1：资源绑定对象生命周期）
class fd_guard {
public:
    explicit fd_guard(int fd) : fd_(fd) {}
    ~fd_guard() {
        if (fd_ >= 0) ::close(fd_);
    }
    fd_guard(const fd_guard&) = delete;
    fd_guard& operator=(const fd_guard&) = delete;
    fd_guard(fd_guard&& other) noexcept : fd_(std::exchange(other.fd_, -1)) {}
    fd_guard& operator=(fd_guard&& other) noexcept {
        if (this != &other) {
            if (fd_ >= 0) ::close(fd_);
            fd_ = std::exchange(other.fd_, -1);
        }
        return *this;
    }
    int get() const { return fd_; }

private:
    int fd_;
};


// —— 快照文件格式（定长 header + 定长元素表 + 行主序 float 矩阵 + 校验尾）——
// 写端与读端共用同一套常量：改布局必须两头同步（ph22 3.1 的"校验范围两头一致"纪律）。
constexpr char k_magic[4] = {'V', 'S', 'R', '1'};
constexpr std::size_t k_header_size = 24;  // magic4 + version4 + dim4 + count8 + reserve4
constexpr std::uint32_t k_version = 1;

struct header {
    std::uint32_t dim{0};
    std::uint64_t count{0};
};

// FNV-1a 32 位：作为整文件校验（教学用，非密码学）
std::uint32_t fnv1a(const std::uint8_t* p, std::size_t n) {
    std::uint32_t h = 2166136261u;
    for (std::size_t i = 0; i < n; ++i) {
        h ^= p[i];
        h *= 16777619u;
    }
    return h;
}

void put_u32(std::uint8_t* p, std::uint32_t v) {  // 本机小端直写（arm64/x86 一致）；
    std::memcpy(p, &v, sizeof v);                  // 跨平台换显式字节序，见 ph22 大端纪律
}
void put_u64(std::uint8_t* p, std::uint64_t v) { std::memcpy(p, &v, sizeof v); }
std::uint32_t get_u32(const std::uint8_t* p) { std::uint32_t v; std::memcpy(&v, p, sizeof v); return v; }
std::uint64_t get_u64(const std::uint8_t* p) { std::uint64_t v; std::memcpy(&v, p, sizeof v); return v; }

// —— 写入：内存快照 → 不可变文件（temp + fsync + rename 原子替换）——
// data: count × dim 行主序 float；ids: 与行对齐的业务 id。
void write_snapshot(const std::string& tmp_path, const std::string& final_path,
                    const std::vector<float>& data, const std::vector<std::uint32_t>& ids,
                    std::uint32_t dim) {
    const std::size_t count = ids.size();
    if (data.size() != count * dim) throw std::invalid_argument("size mismatch");
    const std::size_t id_bytes = count * sizeof(std::uint32_t);
    const std::size_t vec_bytes = count * dim * sizeof(float);
    const std::size_t total = k_header_size + id_bytes + vec_bytes + 4;  // + 校验尾

    std::vector<std::uint8_t> buf(total);
    std::memcpy(buf.data(), k_magic, 4);
    put_u32(buf.data() + 4, k_version);
    put_u32(buf.data() + 8, static_cast<std::uint32_t>(dim));
    put_u64(buf.data() + 12, static_cast<std::uint64_t>(count));
    // id 表
    std::memcpy(buf.data() + k_header_size, ids.data(), id_bytes);
    // float 矩阵（连续行主序）
    std::memcpy(buf.data() + k_header_size + id_bytes, data.data(), vec_bytes);
    // 校验尾：覆盖"magic 之后的整段"（与读端一致）
    const std::uint32_t c = fnv1a(buf.data() + 4, total - 4 - 4);
    put_u32(buf.data() + total - 4, c);

    // 不可变文件的三步写盘纪律：写 temp → fsync → rename（原子）
    {
        std::ofstream out(tmp_path, std::ios::binary | std::ios::trunc);
        if (!out) throw std::runtime_error("cannot open tmp: " + tmp_path);
        out.write(reinterpret_cast<const char*>(buf.data()),
                  static_cast<std::streamsize>(buf.size()));
        out.flush();
        // RAII：异常/提前 return 都由 out 析构关闭文件
    }
    // fsync 落盘（macOS 真落盘需 F_FULLFSYNC，教学用 fsync，见 C 路线 ph13）
    fd_guard fd(::open(tmp_path.c_str(), O_RDONLY));
    if (fd.get() < 0) throw std::runtime_error("cannot open tmp for fsync");
    if (::fsync(fd.get()) != 0) throw std::runtime_error("fsync failed");
    if (::rename(tmp_path.c_str(), final_path.c_str()) != 0)    // 原子替换
        throw std::runtime_error("rename failed");
}

// —— 载入：读头 → 校验 → 读出 id 表与矩阵（返回行主序矩阵，行号即数组下标）——
struct snapshot {
    std::uint32_t dim{0};
    std::vector<std::uint32_t> ids;
    std::vector<float> data;   // ids.size() × dim，行主序
};

snapshot load_snapshot(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open: " + path);
    in.seekg(0, std::ios::end);
    const std::streamoff fsize = in.tellg();
    in.seekg(0, std::ios::beg);
    if (fsize < static_cast<std::streamoff>(k_header_size) + 4)
        throw std::runtime_error("file too short");

    std::vector<std::uint8_t> buf(static_cast<std::size_t>(fsize));
    in.read(reinterpret_cast<char*>(buf.data()), fsize);
    if (!in) throw std::runtime_error("read failed");

    if (std::memcmp(buf.data(), k_magic, 4) != 0)
        throw std::runtime_error("bad magic");
    const std::uint32_t ver = get_u32(buf.data() + 4);
    if (ver != k_version) throw std::runtime_error("version mismatch");
    const std::uint32_t dim = get_u32(buf.data() + 8);
    const std::uint64_t count = get_u64(buf.data() + 12);

    // 校验：范围 = magic 之后到校验尾之前（写端同范围）
    const std::uint32_t expect = get_u32(buf.data() + buf.size() - 4);
    const std::uint32_t got = fnv1a(buf.data() + 4, buf.size() - 8);
    if (got != expect) throw std::runtime_error("checksum mismatch: 文件已损坏");

    snapshot s;
    s.dim = dim;
    const std::size_t id_bytes = static_cast<std::size_t>(count) * sizeof(std::uint32_t);
    const std::size_t vec_bytes = static_cast<std::size_t>(count) * dim * sizeof(float);
    if (k_header_size + id_bytes + vec_bytes + 4 != buf.size())
        throw std::runtime_error("size mismatch: 布局不一致");
    s.ids.resize(static_cast<std::size_t>(count));
    std::memcpy(s.ids.data(), buf.data() + k_header_size, id_bytes);
    s.data.resize(static_cast<std::size_t>(count) * dim);
    std::memcpy(s.data.data(), buf.data() + k_header_size + id_bytes, vec_bytes);
    return s;
}

// —— 载入后的检索（brute force top-k，证明"读回来的数据和写前一致"）——
std::vector<std::pair<std::uint32_t, float>> topk(const snapshot& s,
                                                  const std::vector<float>& q, std::size_t k) {
    std::vector<std::pair<float, std::uint32_t>> all;
    all.reserve(s.ids.size());
    for (std::size_t i = 0; i < s.ids.size(); ++i) {
        const float* row = s.data.data() + i * s.dim;
        float d2 = 0.0f;
        for (std::size_t d = 0; d < s.dim; ++d) {
            const float t = row[d] - q[d];
            d2 += t * t;
        }
        all.push_back({d2, s.ids[i]});
    }
    std::sort(all.begin(), all.end());
    std::vector<std::pair<std::uint32_t, float>> out;
    for (std::size_t j = 0; j < std::min(k, all.size()); ++j) out.push_back({all[j].second, all[j].first});
    return out;
}

}  // namespace persist

int main() {
    using namespace persist;
    // —— 构造内存数据集（快照前形态）——
    constexpr std::size_t dim = 32;
    constexpr std::size_t n = 8000;
    std::mt19937 rng(3u);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    std::vector<float> db(n * dim);
    for (auto& x : db) x = uni(rng);
    std::vector<std::uint32_t> ids(n);
    for (std::size_t i = 0; i < n; ++i) ids[i] = static_cast<std::uint32_t>(100000 + i);
    std::vector<float> q(dim);
    for (auto& x : q) x = uni(rng);

    // [1] 写快照（先写内存结果）
    const auto t0 = std::chrono::steady_clock::now();
    const std::string tmp = "/tmp/ph23-ex06-snap.tmp";
    const std::string path = "/tmp/ph23-ex06-snap.bin";
    std::remove(tmp.c_str());
    std::remove(path.c_str());
    write_snapshot(tmp, path, db, ids, static_cast<std::uint32_t>(dim));
    const auto t1 = std::chrono::steady_clock::now();
    std::uint64_t fsize = 0;
    { std::ifstream in(path, std::ios::binary | std::ios::ate); fsize = in.tellg(); }
    std::cout << "[1] 写入快照 " << path << ": " << fsize << " 字节（≈"
              << static_cast<double>(fsize) / (n * dim * 4) << "× 原始向量大小）耗时 "
              << std::chrono::duration<double, std::micro>(t1 - t0).count() << "µs\n";

    // [2] 载入 + 校验 + 检索一致性（关键：行号→业务 id 映射也必须回来）
    const auto s = load_snapshot(path);
    const auto top_before = topk(s, q, 5);
    std::cout << "[2] 载入: n=" << s.ids.size() << " dim=" << s.dim << ", top-5 ids=[";
    for (const auto& [id, d] : top_before) std::cout << id << (d == top_before.back().second ? "" : ",");
    std::cout << "]\n";
    if (s.ids.size() != n || s.data.size() != n * dim) throw std::runtime_error("reload count mismatch");
    for (std::size_t i = 0; i < n * dim; ++i)
        if (s.data[i] != db[i]) throw std::runtime_error("vector bytes differ after reload");

    // [3] 篡改一字节 → 校验必须拦截（SSTable 的"损坏即拒绝服务"纪律）
    bool caught = false;
    try {
        std::fstream in(path, std::ios::binary | std::ios::in | std::ios::out);
        in.seekp(static_cast<std::streamoff>(k_header_size + n * sizeof(std::uint32_t)) + 7);
        char c = 'X';
        in.write(&c, 1);
        in.close();
        (void)load_snapshot(path);
    } catch (const std::runtime_error& e) {
        caught = true;
        std::cout << "[3] 篡改数据区一字节 → 载入抛错: " << e.what() << "\n";
    }
    if (!caught) throw std::runtime_error("corruption was not detected");
    std::remove(path.c_str());   // 清理（篡改过的文件不留）

    std::cout << "ph23-ex06 OK\n";
    return 0;
}
