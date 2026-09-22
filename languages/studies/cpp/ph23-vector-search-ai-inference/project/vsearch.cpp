// vsearch.cpp —— ph23 project：SIMD 加速 brute-force 检索库实现（距离内核 + 快照格式）
// 快照文件格式（写端/读端同源常量；SSTable 心智平移自 ph22 3.3 与 ph23 examples/ex06）：
//   [magic "VSR2" 4B][version u32][dim u32][metric u32][count u64]      ← 定长 header
//   [id 表: count × i64] [范数表: count × f32（仅 cosine）] [float 行主序矩阵]
//   [FNV-1a 校验尾 u32（覆盖 magic 之后的整段）]
// 写盘纪律：temp 写完 → fsync → rename 原子替换（不可变快照，损坏即拒绝服务——不修复）。
// SIMD：arm64 手写 NEON（4 宽 vfmaq 累加 + 标量尾部）；x86 应改 AVX2 内建（见 ex03 注释）。
//   编译期宏 VSEARCH_FORCE_SCALAR=1 强制标量路径 → Makefile `bench_scalar` 目标用同一份
//   源码产出"无 SIMD 构建"，与默认 SIMD 构建对照实测加速比（不虚构数字）。
// 资源管理：pimpl 由头文件 unique_ptr 持有；文件描述符 RAII（fd_guard）；无裸 new/delete。
#include "vsearch.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <utility>

#include <fcntl.h>
#include <unistd.h>

#if defined(__ARM_NEON) && !defined(VSEARCH_FORCE_SCALAR)
#include <arm_neon.h>
#define VSEARCH_HAS_NEON 1
#else
#define VSEARCH_HAS_NEON 0
#endif

namespace vsearch {
namespace {

constexpr char k_magic[4] = {'V', 'S', 'R', '2'};
constexpr std::size_t k_header_size = 24;   // magic4+version4+dim4+metric4+count8
constexpr std::uint32_t k_version = 1;

std::uint32_t fnv1a(const std::uint8_t* p, std::size_t n) {
    std::uint32_t h = 2166136261u;
    for (std::size_t i = 0; i < n; ++i) {
        h ^= p[i];
        h *= 16777619u;
    }
    return h;
}
void put_u32(std::uint8_t* p, std::uint32_t v) { std::memcpy(p, &v, sizeof v); }
void put_u64(std::uint8_t* p, std::uint64_t v) { std::memcpy(p, &v, sizeof v); }
std::uint32_t get_u32(const std::uint8_t* p) { std::uint32_t v; std::memcpy(&v, p, sizeof v); return v; }
std::uint64_t get_u64(const std::uint8_t* p) { std::uint64_t v; std::memcpy(&v, p, sizeof v); return v; }

class fd_guard {
public:
    explicit fd_guard(int fd) : fd_(fd) {}
    ~fd_guard() {
        if (fd_ >= 0) ::close(fd_);
    }
    fd_guard(const fd_guard&) = delete;
    fd_guard& operator=(const fd_guard&) = delete;
    fd_guard(fd_guard&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {}
    fd_guard& operator=(fd_guard&& o) noexcept {
        if (this != &o) {
            if (fd_ >= 0) ::close(fd_);
            fd_ = std::exchange(o.fd_, -1);
        }
        return *this;
    }
    int get() const { return fd_; }

private:
    int fd_;
};

}  // namespace

struct flat_index::impl {
    std::size_t dim;
    metric m;
    std::vector<std::int64_t> ids;
    std::vector<float> rows;    // ids.size() × dim，行主序（缓存友好，Per.19）
    std::vector<float> norms;   // l2/cosine 用：每行 ||v||² 预存（查询时不重扫向量）

    impl(std::size_t d, metric mm) : dim(d), m(mm) {}

    // —— 距离内核：返回 "key"，统一越大越相似 ——
    // 内部一律用 key 排序（bigger = better）；用户面 score 在 search 出口还原：
    //   l2 → key = -d²（score = d²）；ip/cos → key = score = 相似度。
    float row_key(std::size_t row, const float* q, float qn) const {
        const float* a = rows.data() + row * dim;
        const float ipv = ip_kernel(a, q);
        if (m == metric::l2) {
            // d² = |a|² + |q|² - 2·IP(a,q)（na2/qn 都是 ||·||²）
            const float d2 = norms[row] + qn - 2.0f * ipv;
            return -d2;
        }
        if (m == metric::ip) return ipv;
        const float na = std::sqrt(norms[row]);   // cosine：除以范数（norms 存 ||a||²）
        if (na == 0.0f || qn == 0.0f) return -1e30f;
        return ipv / (na * qn);
    }

    float ip_kernel(const float* a, const float* b) const {
#if VSEARCH_HAS_NEON
        float32x4_t acc = vdupq_n_f32(0.0f);
        std::size_t i = 0;
        for (; i + 4 <= dim; i += 4)
            acc = vfmaq_f32(acc, vld1q_f32(a + i), vld1q_f32(b + i));
        const float32x2_t lo = vget_low_f32(acc);
        const float32x2_t hi = vget_high_f32(acc);
        const float32x2_t s = vpadd_f32(lo, hi);
        float r = vget_lane_f32(vpadd_f32(s, s), 0);
        for (; i < dim; ++i) r += a[i] * b[i];
        return r;
#else
        float s = 0.0f;
        for (std::size_t i = 0; i < dim; ++i) s += a[i] * b[i];
        return s;
#endif
    }
};

flat_index::flat_index(std::size_t dim, metric m) : p_(std::make_unique<impl>(dim, m)) {}
flat_index::~flat_index() = default;
flat_index::flat_index(flat_index&&) noexcept = default;
flat_index& flat_index::operator=(flat_index&&) noexcept = default;

void flat_index::add(std::int64_t id, const std::vector<float>& v) {
    if (v.size() != p_->dim) throw std::invalid_argument("add: dim mismatch");
    p_->ids.push_back(id);
    p_->rows.insert(p_->rows.end(), v.begin(), v.end());
    if (p_->m == metric::l2 || p_->m == metric::cosine) {
        float s = 0.0f;                 // 预存 ||v||²（l2 恒等式用；cosine 取 sqrt 即范数）
        for (const float x : v) s += x * x;
        p_->norms.push_back(s);
    }
}

std::size_t flat_index::size() const noexcept { return p_->ids.size(); }
std::size_t flat_index::dim() const noexcept { return p_->dim; }
std::size_t flat_index::memory_bytes() const noexcept {
    return p_->rows.capacity() * sizeof(float) + p_->ids.capacity() * sizeof(std::int64_t) +
           p_->norms.capacity() * sizeof(float) + sizeof(*p_);
}
const char* flat_index::metric_name() const noexcept {
    switch (p_->m) {
        case metric::l2: return "l2";
        case metric::ip: return "ip";
        case metric::cosine: return "cosine";
    }
    return "?";
}

std::vector<result> flat_index::search(const std::vector<float>& q, std::size_t k) const {
    if (q.size() != p_->dim) throw std::invalid_argument("search: dim mismatch");
    if (p_->ids.empty() || k == 0) return {};
    const std::size_t kk = std::min(k, p_->ids.size());

    float qn = 0.0f;                    // query 范数平方（l2）或范数（cosine）——一次算好
    for (const float x : q) qn += x * x;
    if (p_->m == metric::l2) {
        // l2 的 q 范数平方直接用于恒等式
    } else if (p_->m == metric::cosine) {
        qn = std::sqrt(qn);
    }

    struct cand {                       // 内部保持 key 越大越好
        std::int64_t id;
        float key;
        float score;                    // 用户面分数（出口还原）
    };
    // top-k 维护：k 很小（≤几十），直接做"有序数组截断"，逻辑透明、k 比较成本可忽略；
    // 每来一条：好于当前最差（back）才替换，替换后保持 key 降序（best 在前）。
    std::vector<cand> top;
    auto emit_key = [&](std::size_t row) {
        const float key = p_->row_key(row, q.data(), qn);
        float score = key;
        if (p_->m == metric::l2) score = -key;   // 还原为平方 L2（正数、越小越近）
        return cand{p_->ids[row], key, score};
    };
    for (std::size_t i = 0; i < p_->ids.size(); ++i) {
        if (top.size() < kk) {
            top.push_back(emit_key(i));
        } else if (top.size() == kk) {
            const float key = p_->row_key(i, q.data(), qn);
            if (key > top.back().key) {
                top.pop_back();                 // 丢最差
                top.push_back({p_->ids[i], key, p_->m == metric::l2 ? -key : key});
            } else {
                continue;
            }
        }
        // 保持 top 内 key 降序（简单插入排序：top 已近乎有序，仅需上浮/下沉一位左右）
        for (std::size_t j = top.size() - 1; j > 0 && top[j].key > top[j - 1].key; --j)
            std::swap(top[j], top[j - 1]);
    }

    std::vector<result> out;
    out.reserve(top.size());
    for (const cand& c : top) out.push_back({c.id, c.score});
    return out;
}

// —— 快照（格式注释见文件头）——
void flat_index::save(const std::string& path) const {
    const std::size_t n = p_->ids.size();
    const bool need_norms = !p_->norms.empty();
    const std::size_t id_bytes = n * sizeof(std::int64_t);
    const std::size_t norm_bytes = need_norms ? n * sizeof(float) : 0;
    const std::size_t vec_bytes = n * p_->dim * sizeof(float);
    const std::size_t total = k_header_size + id_bytes + norm_bytes + vec_bytes + 4;

    std::vector<std::uint8_t> buf(total);
    std::memcpy(buf.data(), k_magic, 4);
    put_u32(buf.data() + 4, k_version);
    put_u32(buf.data() + 8, static_cast<std::uint32_t>(p_->dim));
    put_u32(buf.data() + 12, static_cast<std::uint32_t>(p_->m));
    put_u64(buf.data() + 16, static_cast<std::uint64_t>(n));
    std::size_t off = k_header_size;
    std::memcpy(buf.data() + off, p_->ids.data(), id_bytes);
    off += id_bytes;
    if (need_norms) {
        std::memcpy(buf.data() + off, p_->norms.data(), norm_bytes);
        off += norm_bytes;
    }
    std::memcpy(buf.data() + off, p_->rows.data(), vec_bytes);
    off += vec_bytes;
    const std::uint32_t c = fnv1a(buf.data() + 4, off - 4);
    put_u32(buf.data() + off, c);

    const std::string tmp = path + ".tmp";
    {
        std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
        if (!out) throw std::runtime_error("save: cannot open " + tmp);
        out.write(reinterpret_cast<const char*>(buf.data()),
                  static_cast<std::streamsize>(buf.size()));
        out.flush();
    }
    fd_guard fd(::open(tmp.c_str(), O_RDONLY));
    if (fd.get() < 0 || ::fsync(fd.get()) != 0) throw std::runtime_error("save: fsync failed");
    if (::rename(tmp.c_str(), path.c_str()) != 0) throw std::runtime_error("save: rename failed");
}

flat_index flat_index::load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("load: cannot open " + path);
    in.seekg(0, std::ios::end);
    const std::streamoff fsize = in.tellg();
    in.seekg(0, std::ios::beg);
    if (fsize < static_cast<std::streamoff>(k_header_size) + 4)
        throw std::runtime_error("load: file too short");
    std::vector<std::uint8_t> buf(static_cast<std::size_t>(fsize));
    in.read(reinterpret_cast<char*>(buf.data()), fsize);
    if (!in) throw std::runtime_error("load: read failed");

    if (std::memcmp(buf.data(), k_magic, 4) != 0) throw std::runtime_error("load: bad magic");
    if (get_u32(buf.data() + 4) != k_version) throw std::runtime_error("load: version mismatch");
    const std::uint32_t dim = get_u32(buf.data() + 8);
    const std::uint32_t mm = get_u32(buf.data() + 12);
    const std::uint64_t n = get_u64(buf.data() + 16);
    const std::uint32_t expect = get_u32(buf.data() + buf.size() - 4);
    if (fnv1a(buf.data() + 4, buf.size() - 8) != expect)
        throw std::runtime_error("load: checksum mismatch (文件损坏)");
    if (mm > 2 || dim == 0 || n > buf.size()) throw std::runtime_error("load: bad header");

    flat_index idx(dim, static_cast<metric>(mm));
    const bool need_norms = (mm == 0u || mm == 2u);   // l2/cosine 存 ||a||² 表
    const std::size_t id_bytes = static_cast<std::size_t>(n) * sizeof(std::int64_t);
    const std::size_t norm_bytes = need_norms ? static_cast<std::size_t>(n) * sizeof(float) : 0;
    const std::size_t vec_bytes = static_cast<std::size_t>(n) * dim * sizeof(float);
    if (k_header_size + id_bytes + norm_bytes + vec_bytes + 4 != buf.size())
        throw std::runtime_error("load: layout size mismatch");

    idx.p_->ids.resize(static_cast<std::size_t>(n));
    std::size_t off = k_header_size;
    std::memcpy(idx.p_->ids.data(), buf.data() + off, id_bytes);
    off += id_bytes;
    if (need_norms) {
        idx.p_->norms.resize(static_cast<std::size_t>(n));
        std::memcpy(idx.p_->norms.data(), buf.data() + off, norm_bytes);
        off += norm_bytes;
    }
    idx.p_->rows.resize(static_cast<std::size_t>(n) * dim);
    std::memcpy(idx.p_->rows.data(), buf.data() + off, vec_bytes);
    return idx;
}

}  // namespace vsearch
