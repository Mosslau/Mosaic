// 来源：languages/rs/ph10-smart-pointers/project/ —— roadmap 推荐项目「规则树执行器」
// 说明：用 Box 表达递归规则（And/Or/Leaf 无限嵌套），用 Rc 共享规则元数据；
//       eval 在给定事实集下求值（And 全真、Or 任一真、Leaf 查表），node_count/weight
//       递归统计。零第三方依赖，单文件，含单元测试（11 个用例）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 src/main.rs -o /tmp/proj
// 运行：/tmp/proj
// 测试：rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告，11 个单元测试全部通过）

use std::collections::HashMap;
use std::rc::Rc;

/// 规则元数据：Rc 共享——多个规则节点可指向同一份元数据（一处修改、处处生效）
#[derive(Debug)]
struct RuleMeta {
    name: &'static str,
    weight: u32,
}

/// 递归规则树：Box 让 enum 无限嵌套合法；Leaf 持有共享元数据
#[derive(Debug)]
enum RuleNode {
    Leaf(Rc<RuleMeta>),
    And(Vec<Box<RuleNode>>),
    Or(Vec<Box<RuleNode>>),
}

type RuleCtx = HashMap<&'static str, bool>;

impl RuleNode {
    /// 规则求值：Leaf 查事实表（缺省 false），And 全真、Or 任一真
    fn eval(&self, ctx: &RuleCtx) -> bool {
        match self {
            RuleNode::Leaf(meta) => *ctx.get(meta.name).unwrap_or(&false),
            RuleNode::And(children) => children.iter().all(|c| c.eval(ctx)),
            RuleNode::Or(children) => children.iter().any(|c| c.eval(ctx)),
        }
    }

    /// 节点总数（递归遍历）
    fn node_count(&self) -> usize {
        match self {
            RuleNode::Leaf(_) => 1,
            RuleNode::And(children) | RuleNode::Or(children) => {
                1 + children.iter().map(|c| c.node_count()).sum::<usize>()
            }
        }
    }

    /// 权重总和（递归求和；同一份共享元数据被多处引用时重复计入）
    fn weight(&self) -> u32 {
        match self {
            RuleNode::Leaf(meta) => meta.weight,
            RuleNode::And(children) | RuleNode::Or(children) => {
                children.iter().map(|c| c.weight()).sum()
            }
        }
    }

    /// 带缩进的树打印（递归渲染）
    fn render(&self, indent: usize) -> String {
        let pad = "  ".repeat(indent);
        match self {
            RuleNode::Leaf(meta) => format!("{pad}Leaf({}) w={}", meta.name, meta.weight),
            RuleNode::And(children) => {
                let mut s = format!("{pad}And");
                for c in children {
                    s.push('\n');
                    s.push_str(&c.render(indent + 1));
                }
                s
            }
            RuleNode::Or(children) => {
                let mut s = format!("{pad}Or");
                for c in children {
                    s.push('\n');
                    s.push_str(&c.render(indent + 1));
                }
                s
            }
        }
    }
}

fn main() {
    // 共享元数据：同一份规则说明在树中复用（Rc 共享）
    let auth_meta = Rc::new(RuleMeta { name: "auth_check", weight: 10 });
    let rate_meta = Rc::new(RuleMeta { name: "rate_limit", weight: 5 });

    // 规则树：auth_check 且 (rate_limit 或 auth_check 兜底)——auth_meta 被两处引用
    let tree = RuleNode::And(vec![
        Box::new(RuleNode::Leaf(Rc::clone(&auth_meta))),
        Box::new(RuleNode::Or(vec![
            Box::new(RuleNode::Leaf(Rc::clone(&rate_meta))),
            Box::new(RuleNode::Leaf(Rc::clone(&auth_meta))),
        ])),
    ]);

    println!("=== 规则树 ===");
    println!("{}", tree.render(0));

    // 求值：事实集决定结果
    let ctx_ok = HashMap::from([("auth_check", true), ("rate_limit", true)]);
    let ctx_partial = HashMap::from([("auth_check", true), ("rate_limit", false)]);
    let ctx_deny = HashMap::from([("auth_check", false), ("rate_limit", false)]);

    println!("\n=== 求值 ===");
    println!("全真        -> {}", tree.eval(&ctx_ok));      // true
    println!("仅 auth 真  -> {}", tree.eval(&ctx_partial)); // true（Or 分支 rate_limit 为假，兜底 auth 为真）
    println!("全部为假    -> {}", tree.eval(&ctx_deny));    // false

    println!("\n=== 统计 ===");
    println!("节点数 = {}", tree.node_count()); // 1 And + 2（Or + 兜底 Leaf）+ 2 Leaf = 5
    println!("总权重 = {}", tree.weight());     // auth(10) + rate(5) + auth(10) = 25
    println!("auth_meta strong = {}", Rc::strong_count(&auth_meta)); // 3（局部 + 两处 Leaf 引用）
}

#[cfg(test)]
mod tests {
    use super::*;

    fn meta(name: &'static str, weight: u32) -> Rc<RuleMeta> {
        Rc::new(RuleMeta { name, weight })
    }

    fn ctx(pairs: &[(&'static str, bool)]) -> RuleCtx {
        pairs.iter().copied().collect()
    }

    #[test]
    fn leaf_true_when_fact_present() {
        let tree = RuleNode::Leaf(meta("a", 1));
        assert!(tree.eval(&ctx(&[("a", true)])));
    }

    #[test]
    fn leaf_false_when_fact_absent_or_false() {
        let tree = RuleNode::Leaf(meta("a", 1));
        assert!(!tree.eval(&ctx(&[]))); // 缺省 false
        assert!(!tree.eval(&ctx(&[("a", false)])));
    }

    #[test]
    fn and_requires_all_true() {
        let tree = RuleNode::And(vec![
            Box::new(RuleNode::Leaf(meta("a", 1))),
            Box::new(RuleNode::Leaf(meta("b", 1))),
        ]);
        assert!(tree.eval(&ctx(&[("a", true), ("b", true)])));
        assert!(!tree.eval(&ctx(&[("a", true), ("b", false)])));
    }

    #[test]
    fn or_true_when_any_true() {
        let tree = RuleNode::Or(vec![
            Box::new(RuleNode::Leaf(meta("a", 1))),
            Box::new(RuleNode::Leaf(meta("b", 1))),
        ]);
        assert!(tree.eval(&ctx(&[("a", true), ("b", false)])));
        assert!(!tree.eval(&ctx(&[("a", false), ("b", false)])));
    }

    #[test]
    fn nested_and_or() {
        // (a 且 b) 或 c
        let tree = RuleNode::Or(vec![
            Box::new(RuleNode::And(vec![
                Box::new(RuleNode::Leaf(meta("a", 1))),
                Box::new(RuleNode::Leaf(meta("b", 1))),
            ])),
            Box::new(RuleNode::Leaf(meta("c", 1))),
        ]);
        assert!(tree.eval(&ctx(&[("a", true), ("b", true), ("c", false)])));
        assert!(tree.eval(&ctx(&[("a", false), ("b", true), ("c", true)])));
        assert!(!tree.eval(&ctx(&[("a", false), ("b", true), ("c", false)])));
    }

    #[test]
    fn empty_context_all_false() {
        let tree = RuleNode::And(vec![
            Box::new(RuleNode::Leaf(meta("a", 1))),
            Box::new(RuleNode::Or(vec![
                Box::new(RuleNode::Leaf(meta("b", 1))),
                Box::new(RuleNode::Leaf(meta("c", 1))),
            ])),
        ]);
        assert!(!tree.eval(&ctx(&[])));
    }

    #[test]
    fn node_count_counts_every_node() {
        // 1 And + (1 Or + 2 Leaf) + 1 Leaf = 5
        let tree = RuleNode::And(vec![
            Box::new(RuleNode::Leaf(meta("a", 1))),
            Box::new(RuleNode::Or(vec![
                Box::new(RuleNode::Leaf(meta("b", 1))),
                Box::new(RuleNode::Leaf(meta("c", 1))),
            ])),
        ]);
        assert_eq!(tree.node_count(), 5);
    }

    #[test]
    fn weight_sums_shared_meta_per_reference() {
        // 同一份元数据被两处引用，weight 重复计入：10 + (5 + 10) = 25
        let auth = meta("auth_check", 10);
        let rate = meta("rate_limit", 5);
        let tree = RuleNode::And(vec![
            Box::new(RuleNode::Leaf(Rc::clone(&auth))),
            Box::new(RuleNode::Or(vec![
                Box::new(RuleNode::Leaf(Rc::clone(&rate))),
                Box::new(RuleNode::Leaf(Rc::clone(&auth))),
            ])),
        ]);
        assert_eq!(tree.weight(), 25);
    }

    #[test]
    fn rc_sharing_is_by_count_not_copy() {
        let auth = meta("auth_check", 10);
        let tree = RuleNode::And(vec![
            Box::new(RuleNode::Leaf(Rc::clone(&auth))),
            Box::new(RuleNode::Leaf(Rc::clone(&auth))),
        ]);
        // 局部变量 + 两个叶子 = 3 个强引用，数据只有一份
        assert_eq!(Rc::strong_count(&auth), 3);
        assert_eq!(tree.weight(), 20);
    }

    #[test]
    fn render_shows_nesting() {
        let tree = RuleNode::Or(vec![
            Box::new(RuleNode::Leaf(meta("a", 2))),
            Box::new(RuleNode::And(vec![Box::new(RuleNode::Leaf(meta("b", 3)))])),
        ]);
        let s = tree.render(0);
        assert!(s.starts_with("Or"));
        assert!(s.contains("  Leaf(a) w=2"));
        assert!(s.contains("    Leaf(b) w=3")); // And 在缩进 1，其下 Leaf 在缩进 2
    }

    #[test]
    fn single_leaf_edge_case() {
        let tree = RuleNode::Leaf(meta("only", 7));
        assert_eq!(tree.node_count(), 1);
        assert_eq!(tree.weight(), 7);
        assert!(tree.eval(&ctx(&[("only", true)])));
    }
}
