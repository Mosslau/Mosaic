#!/usr/bin/env bash
# exercises/sol-02-cargo-tree.sh —— 练习 2 参考实现：cargo tree 观察依赖树
# 验证环境：bash 3.2+；cargo 1.92.0。需联网拉取演示依赖（serde / serde_json，国内配 rsproxy）。
# 运行：bash sol-02-cargo-tree.sh（产物全落 /tmp/ph17-ex02-sol，可重复运行）
# 未在本环境验证 —— 输出措辞随 cargo 版本微调；命令语义以 cargo 官方文档为准。
set -euo pipefail

DEMO=/tmp/ph17-ex02-sol
rm -rf "$DEMO"
mkdir -p "$DEMO/src"
cd "$DEMO"

cat > Cargo.toml <<'EOF'
[package]
name = "ph17-tree-demo"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
EOF

printf 'fn main() { println!("tree demo"); }\n' > src/main.rs

echo "########## 命令 1：cargo tree（全量依赖树） ##########"
cargo tree
echo "观察：serde_json 在 depth 1，它自己的依赖（itoa/ryu/serde 等）在 depth 2+。"

echo ""
echo "########## 命令 2：cargo tree --depth 2（只看两层） ##########"
cargo tree --depth 2
echo "观察：直接依赖的传递依赖在不在 depth 2 内——干小事的 crate 若拖到很深的层才合理出现要警惕。"

echo ""
echo "########## 命令 3：cargo tree -e features（实际开的 feature） ##########"
cargo tree -e features
echo "观察点 ①：serde 实际 features 含 std + derive（derive 依赖 std，见其 Cargo.toml）。"
echo "观察点 ②：serde_json 也依赖 serde/std —— 见主文档 3.9 语义点 2（feature 并集由全图决定）。"

echo ""
echo "########## 命令 4：cargo tree -d（重复版本） ##########"
cargo tree -d
echo "答案：本演示工程无输出 = 每个 crate 只有一个版本，版本对齐良好。"
echo "若出现重复（如 serde 0.8 与 1.0 并存）→ 某依赖锁了老主版本，见主文档 4.2。"

echo ""
echo "########## 命令 5：cargo tree -i serde_json（反向影响面） ##########"
cargo tree -i serde_json
echo "答案：只有 ph17-tree-demo 直接依赖 serde_json —— 影响面小；若 -i 列出多个 crate，"
echo "升级 serde_json 前要先确认所有依赖方兼容（对应 3.2 维度② 的升级前评审）。"
