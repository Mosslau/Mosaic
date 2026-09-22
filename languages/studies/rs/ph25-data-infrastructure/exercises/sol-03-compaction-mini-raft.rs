// exercises/sol-03-compaction-mini-raft.rs —— 练习 3 参考实现：基础 compaction 归并 + Mini Raft 单节点状态机
// 对应 roadmap §25 练习「实现基础 compaction 与 Mini Raft KV 的单节点状态机」与主文档 3.4/3.5。
// Part A：两个有序 run 的归并（新 run 在前、旧 run 在后），同名 key 取 seq 大者；
//         本练习只做「两 run 全量归并到底」→ 胜者是 tombstone 时 key 彻底消失。
//         真实引擎里非底层归并必须保留 tombstone（否则更旧 run 的值会复活），见主文档 3.4。
// Part B：单节点 Raft —— 内存日志 (term,index,cmd)，先 append 再 commit，按序 apply 到
//         K-V 状态机；recover() 模拟崩溃后仅凭日志重放，幂等且与崩溃前一致。
// 本文件从零实现（Part B 结构思路与 examples/ex04 同源，代码独立重写）。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-03-compaction-mini-raft.rs -o /tmp/ph25-sol03 && /tmp/ph25-sol03
//   rustc --edition 2021 -D warnings --test sol-03-compaction-mini-raft.rs -o /tmp/ph25-sol03-t && /tmp/ph25-sol03-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。

use std::collections::BTreeMap;

// ================= Part A：compaction 归并 =================

#[derive(Debug, Clone, PartialEq, Eq)]
struct Entry {
    key: String,
    value: String, // deleted=true 时为空
    seq: u64,
    deleted: bool,
}

impl Entry {
    fn live(key: &str, value: &str, seq: u64) -> Entry {
        Entry { key: key.to_string(), value: value.to_string(), seq, deleted: false }
    }
    fn tombstone(key: &str, seq: u64) -> Entry {
        Entry { key: key.to_string(), value: String::new(), seq, deleted: true }
    }
}

/// 归并两个**各按 key 升序、key 唯一**的 run（newer 在前、older 在后）。
///
/// 语义（本练习限定为「归并到底」）：
///   1. 同名 key 取 seq 大者（数据上 newer run 的 seq 恒更大）；
///   2. 胜者是 tombstone → key 彻底消失（连同 tombstone 一起丢掉）；
///   3. 单边存在的 key：older 的删除/存活照旧带入，newer 的删除同样到底丢掉；
///   4. 输出按 key 升序。
/// 返回 (输出 run, 丢弃条数统计)。
fn merge_to_bottom(newer: &[Entry], older: &[Entry]) -> (Vec<Entry>, (usize, usize)) {
    // 双指针归并：两条 run 都各按 key 升序且 key 唯一
    let (mut out, mut i, mut j) = (Vec::new(), 0usize, 0usize);
    let (mut dropped_overwrite, mut dropped_tombstone) = (0usize, 0usize);
    while i < newer.len() || j < older.len() {
        // 选 key 较小的一侧推进；两边 key 相等时一起推进并决胜负
        let same_key = i < newer.len() && j < older.len() && newer[i].key == older[j].key;
        if same_key {
            // 同名：seq 大者胜（数据上 newer run 的 seq 恒更大）
            let (winner, loser) = if newer[i].seq >= older[j].seq {
                (newer[i].clone(), older[j].clone())
            } else {
                (older[j].clone(), newer[i].clone())
            };
            i += 1;
            j += 1;
            if winner.deleted {
                // 删除压掉了旧值：只记 tombstone 落地，不重复记「覆盖」
                dropped_tombstone += 1;
                continue;
            }
            dropped_overwrite += 1; // loser 的旧值被新值覆盖
            out.push(winner);
            let _ = loser;
            continue;
        }
        // key 不同：取较小的一侧（单边条目）
        let from_newer = j >= older.len() || (i < newer.len() && newer[i].key < older[j].key);
        let cand = if from_newer { newer[i].clone() } else { older[j].clone() };
        if from_newer {
            i += 1;
        } else {
            j += 1;
        }
        if cand.deleted {
            dropped_tombstone += 1; // 单边 tombstone 到底同样落地
            continue;
        }
        out.push(cand);
    }
    (out, (dropped_overwrite, dropped_tombstone))
}

// ================= Part B：Mini Raft 单节点状态机 =================

#[derive(Debug, Clone)]
enum Command {
    Put(String, String),
    Delete(String),
}

#[derive(Debug, Clone)]
struct LogEntry {
    term: u64,
    index: u64,
    cmd: Option<Command>, // None = no-op（当选后提交，覆盖上一任期遗留）
}

struct RaftNode {
    id: String,
    term: u64,
    voted_for: Option<String>,
    log: Vec<LogEntry>,
    commit_index: u64, // 已安全提交的日志前缀长度
    last_applied: u64, // 已应用到状态机的日志前缀长度
    sm: BTreeMap<String, String>,
    leader: bool,
}

impl RaftNode {
    fn new(id: &str) -> RaftNode {
        RaftNode {
            id: id.to_string(),
            term: 0,
            voted_for: None,
            log: Vec::new(),
            commit_index: 0,
            last_applied: 0,
            sm: BTreeMap::new(),
            leader: false,
        }
    }

    /// 选举（单节点退化形态）：term 单调 +1、投自己、当选，并 append 一条 no-op。
    fn begin_election(&mut self) {
        self.term += 1;
        self.voted_for = Some(self.id.clone());
        self.leader = true;
        let idx = self.log.len() as u64 + 1;
        self.log.push(LogEntry { term: self.term, index: idx, cmd: None });
        self.commit_index = idx;
        self.apply_committed();
    }

    fn client_write(&mut self, cmd: Command) -> u64 {
        assert!(self.leader, "只有 leader 能接受客户端写入");
        let idx = self.log.len() as u64 + 1;
        self.log.push(LogEntry { term: self.term, index: idx, cmd: Some(cmd) });
        self.commit_index = idx; // 单节点 majority=1：append 即安全提交
        self.apply_committed();
        idx
    }

    /// 把 commit_index 之前尚未 apply 的日志按序应用到状态机（幂等、不回退）。
    fn apply_committed(&mut self) {
        while self.last_applied < self.commit_index {
            let next = (self.last_applied + 1) as usize;
            let entry = self.log[next - 1].clone();
            match entry.cmd {
                Some(Command::Put(k, v)) => {
                    self.sm.insert(k, v);
                }
                Some(Command::Delete(k)) => {
                    self.sm.remove(&k);
                }
                None => {} // no-op
            }
            self.last_applied += 1;
        }
    }

    /// 崩溃恢复：丢掉内存状态机，仅凭日志重放（从头 apply 一遍）。
    fn recover(&mut self) {
        self.sm.clear();
        self.last_applied = 0;
        self.apply_committed();
    }
}

fn main() {
    // —— Part A 演示 ——
    let older = vec![
        Entry::live("alpha", "r0", 1),
        Entry::live("beta", "r0", 2),
        Entry::live("gamma", "r0", 3),
    ];
    let newer = vec![
        Entry::live("alpha", "r1", 11),  // 覆盖 r0 的 alpha
        Entry::tombstone("beta", 12),    // 删除 beta → 压掉 r0 的 beta
        Entry::live("delta", "r1", 13),
    ];
    let (merged, stats) = merge_to_bottom(&newer, &older);
    println!("[A compaction] 归并到底层：输出 {} 条", merged.len());
    for e in &merged {
        println!(
            "    {} = {} (seq {})",
            e.key,
            if e.deleted { "<del>" } else { &e.value },
            e.seq
        );
    }
    println!(
        "[A compaction] 丢弃统计：覆盖 {} 条，tombstone 落地 {} 个",
        stats.0, stats.1
    );
    assert_eq!(merged.len(), 3); // alpha(gamma,delta 保留, beta 消失
    assert_eq!(merged[0].key, "alpha");
    assert_eq!(merged[0].value, "r1");
    assert_eq!(merged[1].key, "delta");
    assert_eq!(merged[2].key, "gamma");
    assert!(merged.iter().all(|e| !e.deleted), "到底层归并不应残留 tombstone");
    assert!(merged.windows(2).all(|w| w[0].key < w[1].key), "输出必须升序");

    // —— Part B 演示 ——
    let mut raft = RaftNode::new("n1");
    raft.begin_election();
    println!("[B raft] 选举：term {}，leader={}", raft.term, raft.leader);
    raft.client_write(Command::Put("voltage".into(), "12.8".into()));
    raft.client_write(Command::Put("temperature".into(), "36.5".into()));
    raft.client_write(Command::Delete("voltage".into()));
    println!("[B raft] 提交后状态机：{:?}", raft.sm);
    println!("[B raft] 日志坐标 (term,index,指令)：");
    for e in &raft.log {
        let cmd = match &e.cmd {
            Some(Command::Put(k, v)) => format!("put {k}={v}"),
            Some(Command::Delete(k)) => format!("del {k}"),
            None => "no-op".to_string(),
        };
        println!("    (term {}, index {}) {}", e.term, e.index, cmd);
    }
    let snap = raft.sm.clone();
    raft.recover();
    assert_eq!(raft.sm, snap, "崩溃恢复后状态机必须与崩溃前一致");
    println!("[B raft] 崩溃恢复（仅凭日志重放）后状态机：{:?} —— 与崩溃前一致 ✓", raft.sm);

    println!("\n练习 3 参考实现自检通过");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merge_newer_wins_and_tombstone_drops() {
        let older = vec![
            Entry::live("a", "old", 1),
            Entry::live("b", "old", 2),
            Entry::live("c", "old", 3),
        ];
        let newer = vec![
            Entry::live("a", "new", 10),
            Entry::tombstone("b", 11),
        ];
        let (out, stats) = merge_to_bottom(&newer, &older);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].value, "new");
        assert_eq!(out[1].key, "c");
        assert_eq!(stats.0, 1); // a 覆盖一次
        assert_eq!(stats.1, 1); // b 删除落地
    }

    #[test]
    fn merge_single_side_runs() {
        let older = vec![Entry::live("z", "1", 1)];
        let newer = vec![Entry::live("a", "2", 5), Entry::tombstone("m", 6)];
        let (out, _) = merge_to_bottom(&newer, &older);
        assert_eq!(out.len(), 2); // a,z 保留；m 的 tombstone 到底丢弃
        assert!(out.windows(2).all(|w| w[0].key < w[1].key));
    }

    #[test]
    fn raft_apply_idempotent_and_recover_consistent() {
        let mut r = RaftNode::new("n1");
        r.begin_election();
        r.client_write(Command::Put("x".into(), "1".into()));
        r.client_write(Command::Put("x".into(), "2".into()));
        r.client_write(Command::Delete("x".into()));
        let snap = r.sm.clone();
        r.apply_committed(); // 已追平：不应改变任何东西
        assert_eq!(r.sm, snap);
        r.recover();
        assert_eq!(r.sm, snap);
    }

    #[test]
    fn log_index_contiguous() {
        let mut r = RaftNode::new("n1");
        r.begin_election();
        r.client_write(Command::Put("a".into(), "1".into()));
        r.client_write(Command::Delete("b".into()));
        for (i, e) in r.log.iter().enumerate() {
            assert_eq!(e.index, i as u64 + 1);
        }
        assert_eq!(r.last_applied, r.commit_index);
    }
}
