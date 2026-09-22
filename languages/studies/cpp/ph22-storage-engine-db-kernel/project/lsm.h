// lsm.h —— Mini LSM KV：引擎层（header-only）
// 把 WAL + ph21 skip_list MemTable + SSTable(Bloom) 串成一台能重启恢复的 mini KV：
//   写路径：put/del → 先写 WAL（append+fsync）→ 再写 MemTable → 超过阈值自动 flush
//   读路径：get → MemTable（最新）→ SSTable 从新到旧，每层先过 bloom；“删除=tombstone”
//           在新层里即遮挡旧层值，无需扫到最旧层才知道答案；
//   range scan：把各层按“旧 → 新”顺序应用到有序结果（tombstone erase、新值覆盖），
//           返回跨 MemTable + 全部 SSTable 一致的活数据视图；
//   恢复路径：open 时 replay WAL 重建 MemTable（残尾自动修复），按编号升序载入全部 SSTable。
// 教学简化（注明）：单线程；flush 后 WAL 作废重建（不保留历史归档）；SSTable 只增不并
// （compaction 属主文档 3.5 的进阶）；tombstone 会在 flush 时进入 SSTable、在 get/scan 时遮挡。
// 结构复用：MemTable = ph21::skip_list_map（本目录 skip_list.h，复制自 ph21 project）。
#ifndef PH22_PROJECT_LSM_H
#define PH22_PROJECT_LSM_H

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#include "sstable.h"
#include "skip_list.h"
#include "wal.h"

namespace minilsm {

// MemTable 的值形态：deleted 标志 + 值。删除 = tombstone 写入，不是 erase 节点
// （erase 节点会让“删除”无法跨 flush 持久化）。
struct mem_value {
    bool deleted{false};
    std::string value;
};

using mem_table = ph21::skip_list_map<std::string, mem_value>;

class kvdb {
public:
    // flush_bytes：MemTable 估算字节超阈值自动 flush（0 = 关闭自动 flush）
    kvdb(std::string dir, std::size_t flush_bytes)
        : dir_{std::move(dir)}, flush_bytes_{flush_bytes} {
        ::mkdir(dir_.c_str(), 0755);  // 已存在则 EEXIST，忽略
        wal_path_ = dir_ + "/mini.wal";
        wal_.reset(new wal::log{wal_path_});
        open_existing_sstables();
        replay_wal_into_mem();
    }

    // —— 写路径：先日志后内存 ——
    void put(const std::string& key, const std::string& value) {
        wal_->append_sync(wal::op_type::k_put, key, value);
        mem_->put(key, mem_value{false, value});
        mem_est_ += 16 + key.size() + value.size();
        maybe_flush();
    }

    void del(const std::string& key) {
        wal_->append_sync(wal::op_type::k_del, key, "");
        mem_->put(key, mem_value{true, ""});
        mem_est_ += 16 + key.size();
        maybe_flush();
    }

    // 手动 flush（测试与调优用）
    void flush() {
        std::vector<sst::rec> snapshot;
        snapshot.reserve(mem_->size());
        for (auto it = mem_->begin(); it != mem_->end(); ++it) {  // 有序扫描 = flush 读面
            snapshot.push_back(sst::rec{std::string(it.key()), it.value().value, it.value().deleted});
        }
        if (snapshot.empty()) {
            return;  // 空 MemTable 无物可 flush
        }
        const std::string path = sstable_path(next_id_);
        sst::write_sstable(path, snapshot);
        ++next_id_;
        auto r = std::make_unique<sst::reader>();
        r->open(path);
        sstables_.push_back(std::move(r));
        // flush 完成后旧 WAL 作废（其中的 op 已全部固化进 SSTable）
        wal_->reset();
        mem_ = std::make_unique<mem_table>();
        mem_est_ = 0;
    }

    // —— 点查：MemTable → SSTable（新 → 旧），遇 tombstone 即判不存在 ——
    std::optional<std::string> get(const std::string& key) {
        if (const mem_value* v = mem_->find_value(key)) {
            if (v->deleted) {
                return std::nullopt;  // 删除标记遮挡旧层
            }
            return v->value;
        }
        for (auto it = sstables_.rbegin(); it != sstables_.rend(); ++it) {
            const auto r = (*it)->find(key);
            if (r.state == sst::reader::find_state::value) {
                return r.value;
            }
            if (r.state == sst::reader::find_state::deleted) {
                return std::nullopt;  // 这一层是 tombstone → 更旧层不可能“复活”
            }
            // none：该层 bloom/索引都说没有，看更旧层
        }
        return std::nullopt;
    }

    // —— range scan：跨 MemTable + 全部 SSTable。闭开区间 [lo, hi)；lo/hi 为空串表两端 ——
    std::vector<std::pair<std::string, std::string>> range_scan(const std::string& lo,
                                                                const std::string& hi) {
        // 归并规则：从最旧到最新应用；删除 = erase，真实 put = 覆盖。
        // 旧层先落、新层覆盖 → 结果 = 每 key 最新的活值；tombstone 把旧值从结果里擦掉。
        std::map<std::string, std::string> acc;
        const auto in_range = [&](const std::string& k) {
            return (lo.empty() || k >= lo) && (hi.empty() || k < hi);
        };
        const auto apply = [&](const std::string& k, bool deleted, const std::string& value) {
            if (!in_range(k)) {
                return;
            }
            if (deleted) {
                acc.erase(k);
            } else {
                acc[k] = value;
            }
        };
        for (const auto& s : sstables_) {          // 旧 → 新
            for (const auto& r : s->collect_all()) {
                apply(r.key, r.deleted, r.value);
            }
        }
        for (auto it = mem_->begin(); it != mem_->end(); ++it) {  // MemTable 最新
            apply(std::string(it.key()), it.value().deleted, it.value().value);
        }
        std::vector<std::pair<std::string, std::string>> out;
        out.reserve(acc.size());
        for (auto it = acc.lower_bound(lo); it != acc.end() && (hi.empty() || it->first < hi);
             ++it) {
            out.emplace_back(it->first, it->second);
        }
        return out;
    }

    std::size_t sstable_count() const { return sstables_.size(); }
    std::size_t mem_size() const { return mem_->size(); }
    std::string dir() const { return dir_; }

    // bloom 统计（聚合各 SSTable reader 的计数；点查 miss 在层间累积）
    std::size_t bloom_negatives_total() const {
        std::size_t n = 0;
        for (const auto& s : sstables_) {
            n += s->bloom_negatives();
        }
        return n;
    }

private:
    std::string dir_;
    std::string wal_path_;
    std::size_t flush_bytes_;
    std::unique_ptr<wal::log> wal_;
    std::unique_ptr<mem_table> mem_{std::make_unique<mem_table>()};
    std::vector<std::unique_ptr<sst::reader>> sstables_;  // 按 id 升序（旧 → 新）
    std::uint64_t next_id_{1};
    std::size_t mem_est_{0};

    std::string sstable_path(std::uint64_t id) const {
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%s/mini-%06llu.sst", dir_.c_str(),
                      static_cast<unsigned long long>(id));
        return buf;
    }

    void open_existing_sstables() {
        DIR* d = ::opendir(dir_.c_str());
        if (!d) {
            throw std::runtime_error("opendir failed: " + dir_);
        }
        std::vector<std::uint64_t> ids;
        while (dirent* e = ::readdir(d)) {
            std::uint64_t id = 0;
            if (std::sscanf(e->d_name, "mini-%llu.sst",
                            reinterpret_cast<unsigned long long*>(&id)) == 1) {
                ids.push_back(id);
            }
        }
        ::closedir(d);
        std::sort(ids.begin(), ids.end());
        for (const std::uint64_t id : ids) {
            auto r = std::make_unique<sst::reader>();
            r->open(sstable_path(id));
            sstables_.push_back(std::move(r));
            if (id >= next_id_) {
                next_id_ = id + 1;
            }
        }
    }

    void replay_wal_into_mem() {
        std::optional<std::uint64_t> torn;
        auto ops = wal_->replay(&torn);
        if (torn.has_value()) {
            wal_->truncate_to(torn.value());  // 残尾修复后继续可用
        }
        for (const auto& op : ops) {
            if (op.type == wal::op_type::k_put) {
                mem_->put(op.key, mem_value{false, op.value});
            } else {
                mem_->put(op.key, mem_value{true, ""});
            }
            mem_est_ += 16 + op.key.size() + op.value.size();
        }
    }

    void maybe_flush() {
        if (flush_bytes_ > 0 && mem_est_ >= flush_bytes_) {
            flush();
        }
    }
};

}  // namespace minilsm

#endif  // PH22_PROJECT_LSM_H
