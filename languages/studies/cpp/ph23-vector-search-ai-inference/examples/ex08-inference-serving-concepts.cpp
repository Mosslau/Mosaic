// ex08-inference-serving-concepts.cpp —— 推理服务基础：KV Cache / batching / 内存布局的 CPU 账本演示
// 对应 ph23 主文档 3.9 与 roadmap §23「KV Cache / batching / serving runtime 概念」。
// 教学点：
//   ① KV Cache 是什么：自回归解码每生成一个 token 都要重算"此前所有 token 的注意力"，
//      把每层每头的 K/V 投影结果缓存下来，用内存换重复计算。它的大小由模型结构唯一决定：
//      bytes = 2(K与V) × 层数 × (kv头数 × 每头维度) × token 数 × 每元素字节数；
//   ② 预填充（prefill）与解码（decode）两阶段的内存-算力形态完全不同：
//      prefill 是"长序列并行算一次"（算力密集），decode 是"每步只算一个 token、
//      但要顺序读全量 KV Cache + 权重"（带宽密集）——serving 的一切优化都围绕这个差异；
//   ③ batching 把多个请求的 decode 步合并成一批（同一个矩阵形状里多一行 = 多一个请求），
//      提高吞吐；代价是延迟（要等批攒够）与内存（每个请求的 KV Cache 都要留在显存）；
//   ④ continuous batching：不等整批做完才收新请求，而是"做完一个就补一个新"，
//      让槽位（KV 空间）不空转——本示例用 CPU 事件模拟演示槽位占用曲线与完成延迟；
//   ⑤ 定位声明：本文件是**确定性账本模型**（公式算术 + 简化调度模拟），不是 GPU 基准——
//      FLOPs/带宽数字需在真实 GPU 上测（本机无 GPU），这里给的是"结构如何决定账目"
//      的工程直觉，所有输出数字均可由代码中的公式手工复核。
// 资源管理：纯 std::vector/无资源（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex08-inference-serving-concepts.cpp -o /tmp/ph23-ex08 && /tmp/ph23-ex08
// 验证状态：已验证（零警告、断言全绿、退出码 0）——验证的是"账本公式与调度模拟的确定性输出"，
//   不涉及 GPU 实测数字。

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <random>
#include <stdexcept>
#include <vector>

namespace serve {

// —— 模型结构参数（示意 Llama-7B 量级的经典取值；改成你自己的模型即是通用公式）——
struct model_config {
    std::size_t layers{32};
    std::size_t kv_heads{32};    // 32 = MHA；8 = GQA（Llama2-70B 式）
    std::size_t head_dim{128};
    std::size_t dtype_bytes{2};  // FP16 = 2B
};

// KV Cache 每 token 每层字节数 = 2 × (kv_heads × head_dim) × dtype_bytes
std::size_t kv_bytes_per_token_per_layer(const model_config& m) {
    return 2 * m.kv_heads * m.head_dim * m.dtype_bytes;
}
// 每 token 总字节数（跨全部层）
std::size_t kv_bytes_per_token(const model_config& m) {
    return kv_bytes_per_token_per_layer(m) * m.layers;
}
// 一个长度为 seq 的请求占用的 KV Cache
std::size_t kv_bytes_for_seq(const model_config& m, std::size_t seq) {
    return kv_bytes_per_token(m) * seq;
}

}  // namespace serve

int main() {
    using namespace serve;
    // [1] 公式账本：结构 → 每 token / 每条序列的 KV Cache 占用
    {
        const model_config mha{32, 32, 128, 2};   // 多头注意力 MHA
        const model_config gqa{32, 8, 128, 2};    // 分组查询注意力 GQA（8 个 KV 头）
        for (const auto& [name, m] :
             {std::pair{"MHA(kv=32)", mha}, std::pair{"GQA(kv=8)", gqa}}) {
            const std::size_t per_tok = kv_bytes_per_token(m);
            std::printf("[1] %s: KV cache = %zu B/token = %.0f KiB/token；"
                        "一条 seq=2048 请求占 %.1f MiB；\n"
                        "    seq=4096 时占 %.1f MiB（4096 并发条 ≈ %.1f GiB）\n",
                        name, per_tok, per_tok / 1024.0,
                        kv_bytes_for_seq(m, 2048) / 1048576.0,
                        kv_bytes_for_seq(m, 4096) / 1048576.0,
                        kv_bytes_for_seq(m, 4096) * 4096 / 1073741824.0);
        }
    }

    // [2] batching 的内存账本：batch×seq 决定 KV 总占用（推理吞吐的"显存上限"）
    {
        const model_config m{32, 8, 128, 2};
        const std::size_t kv_gb_budget = 40;   // 假设的 KV 专用预算（显存 - 权重 - 激活）
        std::printf("[2] GQA-7B 量级：KV 预算 %zu GiB 时各 (batch,seq) 组合的占用/余量:\n",
                    kv_gb_budget);
        for (const std::size_t batch : {1u, 8u, 32u, 64u}) {
            for (const std::size_t seq : {512u, 2048u, 8192u}) {
                const double total_gib =
                    kv_bytes_for_seq(m, seq) * batch / 1073741824.0;
                const int can_fit =
                    total_gib <= static_cast<double>(kv_gb_budget) ? 1 : 0;
                std::printf("    batch=%2zu seq=%5zu → %7.1f GiB %s\n", batch, seq,
                            total_gib, can_fit ? "✓" : "✗ 超预算");
            }
        }
        // 断言：账本自洽——GQA 的 KV/token 应为 MHA 的 kv_heads 之比
        const model_config mha{32, 32, 128, 2};
        if (kv_bytes_per_token(m) * 4 != kv_bytes_per_token(mha))
            throw std::runtime_error("GQA(kv=8) 应为 MHA(kv=32) 的 1/4");
    }

    // [3] 简化 continuous batching 调度模拟（CPU 事件模拟，展示"槽位占用 + 完成延迟"）
    {
        struct req {
            std::size_t seq;      // 生成长度（含 prefill 的一次性 + decode 步数）
            double arrive_us;     // 到达时刻（相对 0）
            double fin_us{0};     // 完成时刻
            std::size_t done_steps{0};
        };
        // 简化规则：decode 每步耗时与"当前批内总待解码 token 数"成正比（带宽受限直觉）
        //  + 每完成一个请求立刻补入队首新请求（continuous batching 的本质）
        constexpr std::size_t max_conc = 16;      // 并发槽位上限（KV 预算折算的简化）
        constexpr double k_step_scale_us = 0.4;   // 每 token 步 0.4µs 的"教学标定"，非硬件实测
        constexpr double k_prefill_us = 200.0;    // prefill 一次性成本（教学标定）

        std::mt19937 rng(11u);
        std::uniform_int_distribution<int> seq_uni(64, 512);
        std::uniform_real_distribution<double> gap_uni(50.0, 400.0);  // 到达间隔 µs

        std::vector<req> in;
        std::size_t n_req = 0;
        for (double t = 0; t < 2e6 && n_req < 3000; ) {   // 模拟 2 秒窗口
            req r;
            r.seq = static_cast<std::size_t>(seq_uni(rng));
            r.arrive_us = t;
            in.push_back(r);
            ++n_req;
            t += gap_uni(rng);
        }
        // 到达队列按时间已有序；CPU 事件主循环
        std::vector<req> q(in.begin(), in.end());
        std::vector<req> running, done;
        double t = 0.0;
        std::size_t qi = 0;
        double peak_tokens = 0.0;
        while (qi < q.size() || !running.empty()) {
            // 先收纳已到达且有空槽的请求（batch 大小 ≤ max_conc）
            while (running.size() < max_conc && qi < q.size() &&
                   q[qi].arrive_us <= t) {
                running.push_back(q[qi++]);
            }
            // 若队首还没到，时间快进
            if (running.empty() && qi < q.size()) {
                t = q[qi].arrive_us;
                continue;
            }
            // 步进：decode 一步 = 批内每请求 1 token
            const double batch_tokens =
                static_cast<double>(running.size());
            peak_tokens = std::max(peak_tokens, batch_tokens);
            double step_us = 0.0;
            for (auto& r : running) {
                r.done_steps += 1;
                step_us = std::max(step_us, k_step_scale_us * batch_tokens);  // 取本步耗时
            }
            const double prefill_us = k_prefill_us;
            step_us += prefill_us / running.size();  // 平摊的 prefill 成本（简化）
            t += step_us;
            // 完成检查：每请求还剩 0 步? 简单模型：seq 步即完成
            for (auto it = running.begin(); it != running.end();) {
                if (it->done_steps >= it->seq) {
                    it->fin_us = t;
                    done.push_back(*it);
                    it = running.erase(it);
                } else {
                    ++it;
                }
            }
        }
        // 统计
        std::sort(done.begin(), done.end(),
                  [](const req& a, const req& b) { return a.fin_us < b.fin_us; });
        const std::size_t completed = done.size();
        const double total_win = t;
        const double qps = completed / (total_win / 1e6);
        // 延迟取 P50/P95/P99
        std::vector<double> lats;
        lats.reserve(completed);
        for (const auto& r : done) lats.push_back(r.fin_us - r.arrive_us);
        std::sort(lats.begin(), lats.end());
        auto pct = [&](double p) {
            const std::size_t i = static_cast<std::size_t>(
                p * static_cast<double>(lats.size() - 1));
            return lats[i];
        };
        std::printf("[3] continuous batching 模拟（并发上限=%zu, %zu 请求）:\n",
                    max_conc, completed);
        std::printf("    吞吐 %8.0f req/s，完成窗口 %.0f µs；P50 %.0f µs | P95 %.0f µs | "
                    "P99 %.0f µs\n", qps, total_win, pct(0.50), pct(0.95), pct(0.99));
        std::printf("    峰值并发批大小 %zu（KV 占用峰值即此 × 单请求 KV）——见 [1][2] 公式\n",
                    static_cast<std::size_t>(peak_tokens));
        std::printf("    说明: step 标定值仅用于演示「内存账本 + 批调度」的形态，非 GPU 实测；\n"
                    "    真实 serving 的吞吐/延迟需在 NVIDIA 环境按 ex08 文件头说明实测。\n");
        if (completed < 2000) throw std::runtime_error("sim completed too few requests");
    }
    std::printf("ph23-ex08 OK\n");
    return 0;
}
