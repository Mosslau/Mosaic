//! ex04：缓存局部性实测 —— 「访问模式」与「数据布局」两个维度。
//!
//! 为什么缓存局部性决定性能：CPU 以缓存行（cache line）为单位搬运内存，
//! 本机 Apple Silicon 实测缓存行 128B（`sysctl hw.cachelinesize`）。一个 u64
//! 只占 8B，顺序遍历时一次取进缓存行的 128B 能服务 16 个元素；随机 gather 时
//! 每次触碰一个新行、前 120B 都被浪费。AoS（Array of Struct）把不同字段放同一
//! 行，遍历只用其中一个字段时其余字段白白占行；SoA（Struct of Array）让同一
//! 字段连续排布，一次取行服务 16 个所需元素。
//!
//! 测量：每组 `best-of-7`（丢弃首轮预热）取中位数，输出毫秒。
//! 数据全部预生成在测量窗口之外，测的只是「读 + 求和」本身。

use std::hint::black_box;
use std::time::Instant;

/// 数据规模：顺序遍历数组元素数。
const N: usize = 1 << 23; // 8_388_608 个 u64 = 64 MiB，远超 L2/L3，保证访存主导
/// 随机 walk 的步数（gather 次数）。
const WALK: usize = 1 << 21; // 2_097_152 次 gather
/// 布局对比的结构体数量。
const M: usize = 1 << 22; // AoS/SoA 各 4M 元素：AoS≈96MB / SoA 每列 32MB

/// LCG 快速填充，保证数据不可被编译器折叠成常量。
fn fill_lcg(buf: &mut [u64], seed: u64) {
    let mut x = seed;
    for slot in buf.iter_mut() {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        *slot = x;
    }
}

/// 对连续 u64 切片分块求和；每 256 元素做一次 black_box（chunk 内让编译器
/// 自由向量化，黑盒只拦 chunk 边界）。测的是「真实读流量」，不是逐元素 barrier。
#[inline(always)]
fn sum_chunks(v: &[u64]) -> u64 {
    v.chunks(256)
        .map(|c| c.iter().fold(0u64, |a, &x| a.wrapping_add(x)))
        .fold(0u64, |a, s| a.wrapping_add(black_box(s)))
}

/// 顺序遍历。
#[inline(always)]
fn sum_seq(data: &[u64]) -> u64 {
    sum_chunks(data)
}

/// 随机 gather：索引随机无法向量化，逐元素读已是下限；结果用 black_box 消费。
#[inline(always)]
fn sum_gather(data: &[u64], idx: &[u32]) -> u64 {
    idx.iter().fold(0u64, |acc, &i| {
        acc.wrapping_add(black_box(data[i as usize]))
    })
}

/// AoS：三个字段挨在一起的结构体数组。
struct AoSPoint {
    x: u64,
    y: u64,
    z: u64,
}

/// SoA：三个字段各自成列。
struct SoAPoints {
    xs: Vec<u64>,
    ys: Vec<u64>,
    zs: Vec<u64>,
}

fn best_of_n(mut f: impl FnMut() -> u64) -> std::time::Duration {
    // 首轮丢弃（预热），随后 11 轮取**最小**——负载噪声只会把测量拖慢，
    // 最小值最接近该场景的真实最优；这是微基准对抗环境噪声的常用口径
    let mut best = std::time::Duration::MAX;
    f();
    for _ in 0..11 {
        let t = Instant::now();
        let out = f();
        black_box(out);
        best = best.min(t.elapsed());
    }
    best
}

fn main() {
    println!("== ex04 缓存局部性 ==");
    println!("本机缓存行: 由 `sysctl hw.cachelinesize` 实测 (Apple Silicon 通常 128)\n");

    // ---- 维度 1：访问模式（顺序 vs 随机 gather）----
    let data: Vec<u64> = {
        let mut v = vec![0u64; N];
        fill_lcg(&mut v, 42);
        v
    };
    let mut rng = 0x1234_5678_9abc_def0u64;
    let idx: Vec<u32> = (0..WALK)
        .map(|_| {
            rng = rng
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (rng >> 32) as u32 % N as u32 // 限定在数组范围内
        })
        .collect();

    let ms = |d: std::time::Duration| d.as_secs_f64() * 1e3;
    let d_seq = best_of_n(|| sum_seq(black_box(&data)));
    let d_rand = best_of_n(|| sum_gather(black_box(&data), black_box(&idx)));
    // 顺序 8M 读 vs 随机 2M 读工作量不同：按「单次读取成本」算比值才公平
    let seq_ns = d_seq.as_secs_f64() * 1e9 / N as f64;
    let rand_ns = d_rand.as_secs_f64() * 1e9 / WALK as f64;
    println!(
        "[访问模式] 顺序遍历 {N} 元素: {:>8.2} ms  ({seq_ns:.2} ns/元素)",
        ms(d_seq)
    );
    println!(
        "[访问模式] 随机 gather {WALK} 步: {:>8.2} ms  ({rand_ns:.2} ns/步, 单次读 ≈ {:.0}x 贵)",
        ms(d_rand),
        rand_ns / seq_ns
    );

    // ---- 维度 2：数据布局（AoS vs SoA）----
    // 只求和 x 字段——AoS 一次取行却只用一个字段，SoA 则整行都是要用的 x
    let aos: Vec<AoSPoint> = {
        let mut v = Vec::with_capacity(M);
        let mut rng = 7u64;
        for _ in 0..M {
            rng = rng
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            v.push(AoSPoint {
                x: rng,
                y: rng >> 1,
                z: rng >> 2,
            });
        }
        v
    };
    let soa = {
        let (mut xs, mut ys, mut zs) = (vec![0u64; M], vec![0u64; M], vec![0u64; M]);
        let mut rng = 7u64;
        for i in 0..M {
            rng = rng
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            xs[i] = rng;
            ys[i] = rng >> 1;
            zs[i] = rng >> 2;
        }
        SoAPoints { xs, ys, zs }
    };

    // 逐列读取时用分块求和（内部可向量化）；AoS 用同样分块、chunk 内 fold 三个字段
    let sum_xyz_aos = |a: &[AoSPoint]| {
        a.chunks(256)
            .map(|c| {
                c.iter().fold(0u64, |acc, p| {
                    acc.wrapping_add(p.x).wrapping_add(p.y).wrapping_add(p.z)
                })
            })
            .fold(0u64, |acc, s| acc.wrapping_add(black_box(s)))
    };
    let sum_x_aos = |a: &[AoSPoint]| {
        a.chunks(256)
            .map(|c| c.iter().fold(0u64, |acc, p| acc.wrapping_add(p.x)))
            .fold(0u64, |acc, s| acc.wrapping_add(black_box(s)))
    };

    let t_aos = best_of_n(|| sum_xyz_aos(black_box(&aos)));
    let t_soa = best_of_n(|| {
        // SoA xyz：三条 u64 列按 256 元素同长分块，各自求和后合并
        soa.xs
            .chunks(256)
            .zip(soa.ys.chunks(256))
            .zip(soa.zs.chunks(256))
            .map(|((cx, cy), cz)| {
                let (mut sx, mut sy, mut sz) = (0u64, 0u64, 0u64);
                for k in 0..cx.len() {
                    sx = sx.wrapping_add(cx[k]);
                    sy = sy.wrapping_add(cy[k]);
                    sz = sz.wrapping_add(cz[k]);
                }
                sx.wrapping_add(sy).wrapping_add(sz)
            })
            .fold(0u64, |acc, s| acc.wrapping_add(black_box(s)))
    });
    // 只求 x：AoS 仍要跳过 y/z 占用的行空间，SoA 只读 xs 一列
    let t_aos_x = best_of_n(|| sum_x_aos(black_box(&aos)));
    let t_soa_x = best_of_n(|| sum_chunks(black_box(&soa.xs)));
    println!(
        "\n[布局] AoS 求 x+y+z: {:>9.2} ms   SoA 求 x+y+z: {:>9.2} ms",
        ms(t_aos),
        ms(t_soa)
    );
    println!(
        "[布局] AoS 只求 x  : {:>9.2} ms   SoA 只求 x  : {:>9.2} ms   (SoA/AoS ≈ {:.2}x)",
        ms(t_aos_x),
        ms(t_soa_x),
        t_soa_x.as_secs_f64() / t_aos_x.as_secs_f64()
    );
    println!(
        "\n要点: 数据规模超过缓存后, 顺序访问 ≈ 随机访问速度的差就是缓存行的代价; \n      SoA 比 AoS 快在『同一列元素连续』——只读 x 时整条缓存行都是有效载荷。"
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lcg_fills_distinct_values() {
        let mut v = vec![0u64; 16];
        fill_lcg(&mut v, 99);
        assert_ne!(v[0], v[1]);
    }

    #[test]
    fn sum_seq_matches_manual() {
        let v = vec![1u64, 2, 3, 4, 5];
        assert_eq!(sum_seq(&v), 15);
    }
}
