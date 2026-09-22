//! ph25 ex04：Mini Raft 单节点日志复制状态机 + 选举概念（纯 std，零第三方依赖）
//!
//! 边界声明（对应主文档 3.5）：本示例**不实现真实网络共识**——没有节点间
//! RPC、没有多数派投票、没有 leader 切换。它把 Raft 里「与单节点也成立」
//! 的两块核心抽象落地：① 日志条目带 (term, index)，客户端指令先 append
//! 进日志、再按 commit_index 顺序应用到状态机（K-V 表）；② 「选举」在
//! 单节点簇里的退化形态——term 单调递增、节点给自己投票、立即当选 leader。
//! 多节点选举/日志复制的完整语义（PreVote、quorum、matchIndex/nextIndex、
//! 心跳、超时随机化）是**概念**而非本示例实现，正文用流程文字与注释讲清。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）
//! - 运行：`cargo run --release`（选举 → 追加 → 提交 → 应用 → 恢复五幕）
//! - 测试：`cargo test --release`
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测，输出见 examples/README）

use std::collections::BTreeMap;

/// 客户端指令：写入状态机的操作（Raft 论文里的 `command`）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    Put(String, String),
    Delete(String),
}

/// 一条日志条目：`(term, index)` 是它在 Raft 日志里的坐标。
/// `command=None` 表示「空日志」（no-op，当选后立刻 append 一条用来提交前任任期）。
#[derive(Debug, Clone)]
struct LogEntry {
    term: u64,
    index: u64,
    command: Option<Command>,
}

/// Raft 日志的不变量：index 连续从 1 起、term 只随任期单调、同 index 只出现一次。
#[derive(Debug, Default)]
struct RaftLog {
    entries: Vec<LogEntry>,
}

impl RaftLog {
    fn last_index(&self) -> u64 {
        self.entries.last().map_or(0, |e| e.index)
    }

    fn last_term(&self) -> u64 {
        self.entries.last().map_or(0, |e| e.term)
    }

    /// append（leader 收到客户端指令后调用）：index 由日志长度决定。
    fn append(&mut self, term: u64, command: Command) -> u64 {
        let index = self.last_index() + 1;
        self.entries.push(LogEntry {
            term,
            index,
            command: Some(command),
        });
        index
    }

    /// 选举后追加 no-op 条目（提交前任任期的遗留状态）。
    fn append_noop(&mut self, term: u64) -> u64 {
        let index = self.last_index() + 1;
        self.entries.push(LogEntry {
            term,
            index,
            command: None,
        });
        index
    }

    fn entry(&self, index: u64) -> Option<&LogEntry> {
        // index 从 1 起，数组下标 = index - 1
        self.entries.get(index as usize - 1)
    }
}

/// 单节点 Raft 节点：日志 + 选举元数据 + 状态机。
///
/// 状态机与日志分离，正是 Raft 的核心：**先让指令进日志（复制），再按顺序
/// apply 到状态机**；崩溃后从日志重新 apply 就能把状态机恢复回来（demo 第 5 幕）。
struct SingleNodeRaft {
    id: String,
    term: u64,
    voted_for: Option<String>,
    /// 已确认安全提交的日志前缀长度（单节点：append 即提交）。
    commit_index: u64,
    /// 已经应用到状态机的日志前缀长度（幂等推进，绝不回退）。
    last_applied: u64,
    log: RaftLog,
    state_machine: BTreeMap<String, String>,
    leader: bool,
}

impl SingleNodeRaft {
    fn new(id: &str) -> SingleNodeRaft {
        SingleNodeRaft {
            id: id.to_string(),
            term: 0,
            voted_for: None,
            commit_index: 0,
            last_applied: 0,
            log: RaftLog::default(),
            state_machine: BTreeMap::new(),
            leader: false,
        }
    }

    /// 选举概念演示：单节点簇里没有竞争者，term+1、投自己、当选。
    /// 多节点时这一步要经历「随机超时 → 请求投票 → 多数派同意 → 当选」，
    /// 且收到更高 term 的 RPC 要先让位——这些属于主文档 3.5 的概念部分。
    fn begin_election(&mut self) {
        self.term += 1;
        self.voted_for = Some(self.id.clone());
        self.leader = true;
        println!(
            "[选举] 节点 {} 选举计时器超时：term {} → {}，投自己一票",
            self.id,
            self.term - 1,
            self.term
        );
        println!(
            "[选举] 单节点簇 majority=1/1，立即当选 leader（voted_for = {:?}）",
            self.voted_for
        );
        // 当选惯例：append 一条 no-op 并提交，让上一任期遗留的未提交条目被覆盖掉
        let idx = self.log.append_noop(self.term);
        self.commit_index = idx;
        println!(
            "[选举] 新 leader append no-op（index {idx}, term {}）并提交到 commit_index={}",
            self.term, self.commit_index
        );
    }

    /// 客户端写路径：append 到本地日志 → 提交（单节点即 majority）→ 应用到状态机。
    fn client_write(&mut self, cmd: Command) -> u64 {
        assert!(self.leader, "只有 leader 能接受客户端写入");
        let idx = self.log.append(self.term, cmd.clone());
        println!(
            "[写路径] append 指令 index={idx} term={}：{:?}",
            self.term,
            describe(&cmd)
        );
        self.commit_index = idx; // 单节点：日志落本地即 majority，安全提交
        println!("[写路径] commit_index → {idx}（单节点 majority=1）");
        self.apply_committed();
        idx
    }

    /// 把 commit_index 之前尚未 apply 的日志顺序应用到状态机（幂等推进）。
    fn apply_committed(&mut self) {
        while self.last_applied < self.commit_index {
            let next = self.last_applied + 1;
            let entry = self.log.entry(next).expect("commit 前的日志必在").clone();
            if let Some(cmd) = entry.command {
                println!(
                    "[apply] index {next} term {} 应用到状态机：{}",
                    entry.term,
                    describe(&cmd)
                );
                apply_command(&mut self.state_machine, &cmd);
            } else {
                println!(
                    "[apply] index {next} term {} 是 no-op，状态机无变化",
                    entry.term
                );
            }
            self.last_applied = next;
        }
        // 不变量：应用进度恒等于提交进度（只前进、不回退）
        debug_assert_eq!(self.last_applied, self.commit_index);
    }

    /// 崩溃恢复演示：用「日志 + commit_index」重建状态机（幂等：重放应用）。
    /// 真实引擎里日志已持久化（ex01 的 WAL 形态），这里用内存日志模拟。
    fn recover_state_machine(&mut self) {
        println!("\n[恢复] 模拟崩溃后重启：丢弃内存状态机，仅凭日志重放…");
        self.state_machine.clear();
        self.last_applied = 0;
        self.apply_committed();
        println!(
            "[恢复] 重放完成：重放 {} 条已提交指令（last_applied={}），状态机与崩溃前一致",
            self.commit_index, self.last_applied
        );
    }

    fn state(&self) -> &BTreeMap<String, String> {
        &self.state_machine
    }
}

fn describe(cmd: &Command) -> String {
    match cmd {
        Command::Put(k, v) => format!("put {k} = {v}"),
        Command::Delete(k) => format!("del {k}"),
    }
}

fn apply_command(sm: &mut BTreeMap<String, String>, cmd: &Command) {
    match cmd {
        Command::Put(k, v) => {
            sm.insert(k.clone(), v.clone());
        }
        Command::Delete(k) => {
            sm.remove(k);
        }
    }
}

fn main() {
    println!("== Mini Raft：单节点日志复制状态机 ==");
    let mut raft = SingleNodeRaft::new("n1");

    // —— 第 1 幕：选举（单节点退化形态） ——
    raft.begin_election();

    // —— 第 2 幕：客户端写路径（先日志后状态机） ——
    raft.client_write(Command::Put("alpha".into(), "1".into()));
    raft.client_write(Command::Put("beta".into(), "2".into()));
    raft.client_write(Command::Put("alpha".into(), "10".into())); // 覆盖
    raft.client_write(Command::Delete("beta".into())); // tombstone 语义同 ex01/ex02

    println!("\n[状态] 状态机快照：{:?}", raft.state());
    println!(
        "[状态] log 总长 {}，term {}，commit_index {}，last_applied {}",
        raft.log.last_index(),
        raft.term,
        raft.commit_index,
        raft.last_applied
    );

    // —— 第 3 幕：幂等（重复 apply 不重复生效——用已跟踪的 last_applied 保证） ——
    let before = raft.state().clone();
    raft.apply_committed(); // last_applied == commit_index，什么都不做
    assert_eq!(*raft.state(), before, "重复 apply 不应改变状态机");
    println!("[幂等] 再次 apply_committed：last_applied 已追平 commit_index，状态机无变化 ✓");

    // —— 第 4 幕：崩溃恢复（日志重放重建状态机） ——
    raft.recover_state_machine();
    assert_eq!(
        *raft.state(),
        BTreeMap::from([("alpha".to_string(), "10".to_string())]),
        "恢复后状态机应与崩溃前一致（alpha=10，beta 已被删除）"
    );
    println!(
        "[状态] 恢复后的状态机：{:?}（alpha=10，beta 不存在）",
        raft.state()
    );

    // —— 第 5 幕：选任期单调性的不变量说明（多节点时的 term 纪律在此可见雏形） ——
    println!("\n[不变量] term 单调递增、vote 只投一次、日志 index 连续——单节点也保持这些纪律；");
    println!(
        "       多节点 Raft 在此之上叠加：请求投票/AppendEntries RPC、多数派、心跳超时与随机化。"
    );

    // 用日志坐标展示「为什么 commit 顺序 = apply 顺序」
    println!("\n[日志] 逐条坐标（term, index, 内容）：");
    for e in &raft.log.entries {
        let content = match &e.command {
            Some(c) => describe(c),
            None => "no-op".to_string(),
        };
        println!("       (term={}, index={}) {content}", e.term, e.index);
    }
    println!("\n== ex04 完成：单节点日志复制 → 状态机 → 恢复全链路符合预期 ==");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_leader(id: &str) -> SingleNodeRaft {
        let mut r = SingleNodeRaft::new(id);
        r.begin_election();
        r
    }

    #[test]
    fn election_increments_term_and_self_votes() {
        let mut r = SingleNodeRaft::new("solo");
        assert_eq!(r.term, 0);
        r.begin_election();
        assert_eq!(r.term, 1);
        assert_eq!(r.voted_for.as_deref(), Some("solo"));
        assert!(r.leader);
        assert_eq!(r.commit_index, 1, "当选后 no-op 应被提交");
    }

    #[test]
    fn log_index_contiguous_and_terms_consistent() {
        let mut r = make_leader("solo");
        r.client_write(Command::Put("a".into(), "1".into()));
        r.client_write(Command::Delete("b".into()));
        let last = r.log.last_index();
        assert_eq!(last, 3, "no-op + 2 条指令");
        for (i, e) in r.log.entries.iter().enumerate() {
            assert_eq!(e.index, i as u64 + 1, "index 必须从 1 连续");
            assert!(e.term >= 1 && e.term == r.log.entry(e.index).unwrap().term);
        }
    }

    #[test]
    fn write_applies_to_state_machine_in_order() {
        let mut r = make_leader("solo");
        r.client_write(Command::Put("x".into(), "1".into()));
        r.client_write(Command::Put("x".into(), "2".into()));
        r.client_write(Command::Delete("x".into()));
        assert!(r.state().is_empty(), "x 最终被删除");
        assert_eq!(r.last_applied, r.commit_index);
    }

    #[test]
    fn double_apply_is_idempotent() {
        let mut r = make_leader("solo");
        r.client_write(Command::Put("k".into(), "v".into()));
        let snap = r.state().clone();
        r.apply_committed();
        assert_eq!(*r.state(), snap);
    }

    #[test]
    fn recovery_rebuilds_state_from_log() {
        let mut r = make_leader("solo");
        r.client_write(Command::Put("a".into(), "1".into()));
        r.client_write(Command::Put("b".into(), "2".into()));
        r.client_write(Command::Delete("a".into()));
        r.recover_state_machine();
        assert!(r.state().get("a").is_none());
        assert_eq!(r.state().get("b").map(String::as_str), Some("2"));
    }
}
