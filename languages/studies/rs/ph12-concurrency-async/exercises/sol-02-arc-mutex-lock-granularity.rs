// 来源：languages/rs/ph12-concurrency-async/exercises/README.md 练习 2
// 说明：为共享状态加锁并评估锁粒度——两个场景实测对比：
//   场景 A（纯 CPU 小临界区）：细粒度每轮抢锁 vs 粗粒度一次持锁——
//       本机实测粗粒度更快（锁获取本身有开销，临界区工作微不足道时细粒度不划算）；
//   场景 B（锁外有真实等待）：锁外 sleep 模拟 I/O 等待——
//       细粒度让锁外等待全部并行，粗粒度把等待串行化，细粒度明显更快。
//   结论：锁粒度不是越小越好，取舍看「临界区的工作量 + 锁外的并行机会」。
//   对应 roadmap 练习「为共享状态增加锁并评估粒度」。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-02-arc-mutex-lock-granularity.rs -o /tmp/sol02
// 运行：/tmp/sol02
// 验证状态：已验证（编译零警告；计数全部精确为实测确定值；耗时为本机实测，
//           数值因机器/负载而异，但量级结论稳定：A 粗快、B 细快）

use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const THREADS: u32 = 4;
const ITERS: u32 = 200_000;

fn main() {
    // ===== 场景 A：纯 CPU 小临界区 =====
    // 细粒度：每轮循环都抢锁（临界区 = 一次自增）
    let fine = Arc::new(Mutex::new(0u32));
    let t0 = Instant::now();
    let mut hs = Vec::new();
    for _ in 0..THREADS {
        let c = Arc::clone(&fine);
        hs.push(thread::spawn(move || {
            for _ in 0..ITERS {
                let mut g = c.lock().unwrap();
                *g += 1;
                // g 在此 drop：立刻解锁
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let fine_a = *fine.lock().unwrap();
    let fine_a_ms = t0.elapsed().as_millis();

    // 粗粒度：整个循环只抢一次锁
    let coarse = Arc::new(Mutex::new(0u32));
    let t1 = Instant::now();
    let mut hs = Vec::new();
    for _ in 0..THREADS {
        let c = Arc::clone(&coarse);
        hs.push(thread::spawn(move || {
            let mut g = c.lock().unwrap();
            for _ in 0..ITERS {
                *g += 1;
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let coarse_a = *coarse.lock().unwrap();
    let coarse_a_ms = t1.elapsed().as_millis();

    let expected = THREADS * ITERS;
    assert_eq!(fine_a, expected);
    assert_eq!(coarse_a, expected);
    println!("场景 A（纯 CPU 小临界区）：细粒度计数={fine_a} 耗时 {fine_a_ms}ms；粗粒度计数={coarse_a} 耗时 {coarse_a_ms}ms");
    println!("  → 粗粒度更快：临界区工作微不足道时，锁获取开销占主导，细粒度白白多抢了 80 万次锁");

    // ===== 场景 B：锁外有真实等待（模拟 I/O 取数） =====
    const ROUNDS: u32 = 40;
    const WAIT_MS: u64 = 2;

    // 细粒度：sleep 在锁外，锁只包自增 → 4 个线程的等待并行
    let fine = Arc::new(Mutex::new(0u32));
    let t2 = Instant::now();
    let mut hs = Vec::new();
    for _ in 0..THREADS {
        let c = Arc::clone(&fine);
        hs.push(thread::spawn(move || {
            for _ in 0..ROUNDS {
                thread::sleep(Duration::from_millis(WAIT_MS)); // 锁外等待（真实场景是 I/O）
                let mut g = c.lock().unwrap();
                *g += 1;
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let fine_b = *fine.lock().unwrap();
    let fine_b_ms = t2.elapsed().as_millis();

    // 粗粒度：整个循环持锁 → 4 个线程的等待被锁串行化
    let coarse = Arc::new(Mutex::new(0u32));
    let t3 = Instant::now();
    let mut hs = Vec::new();
    for _ in 0..THREADS {
        let c = Arc::clone(&coarse);
        hs.push(thread::spawn(move || {
            let mut g = c.lock().unwrap();
            for _ in 0..ROUNDS {
                thread::sleep(Duration::from_millis(WAIT_MS)); // 持锁等待：别人进不来
                *g += 1;
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let coarse_b = *coarse.lock().unwrap();
    let coarse_b_ms = t3.elapsed().as_millis();

    let expected_b = THREADS * ROUNDS;
    assert_eq!(fine_b, expected_b);
    assert_eq!(coarse_b, expected_b);
    println!("场景 B（锁外有等待）：细粒度计数={fine_b} 耗时 {fine_b_ms}ms；粗粒度计数={coarse_b} 耗时 {coarse_b_ms}ms");
    println!("  → 细粒度更快：锁外等待全部并行（约 {ROUNDS}×{WAIT_MS}ms），粗粒度把等待串行化（约 ×{THREADS}）");
    println!("结论：锁粒度取舍 = 临界区工作量 vs 锁外并行机会；统一原则是临界区只放必要的共享变更");
}
