#!/usr/bin/env bash
# examples/ex05-cargo-tree-features.sh —— cargo tree 四用法 + feature 并集对照实验（主文档 3.9/3.10 / 示例 5）
# 验证环境：bash 3.2+；cargo 1.92.0。需联网拉取演示依赖（serde / serde_json，国内配 rsproxy）。
# 运行：bash examples/ex05-cargo-tree-features.sh（产物全落 /tmp/ph17-ex05-features，可重复运行）
# 未在本环境验证 —— 输出措辞随 cargo 版本微调，观察点以脚本注释为准。
set -euo pipefail

DEMO=/tmp/ph17-ex05-features
rm -rf "$DEMO"
mkdir -p "$DEMO/src"
cd "$DEMO"

# 起点依赖：serde 开 derive，serde_json 不加任何 feature（它内部依赖 serde 的 std）
cat > Cargo.toml <<'EOF'
[package]
name = "ph17-feature-demo"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
EOF

printf 'fn main() { println!("feature demo"); }\n' > src/main.rs

echo "================ 1. cargo tree：全量依赖树（缩进 = 层级） ================"
cargo tree

echo ""
echo "================ 2. cargo tree -e features：每个 crate 实际开了哪些 feature ================"
cargo tree -e features

echo ""
echo "================ 3. cargo tree -d：重复版本体检（无输出 = 版本对齐良好） ================"
cargo tree -d

echo ""
echo "================ 4. cargo tree -i serde_json：反向影响面（谁依赖它） ================"
cargo tree -i serde_json

echo ""
echo "================ 5. 对照实验：自己把 serde 默认特性关掉，看并集结果 ================"
# 把 serde 依赖改成 default-features = false（模拟 3.9 的「关默认 + 精开」习惯）
python3 - <<'PY'
import pathlib
p = pathlib.Path("Cargo.toml")
t = p.read_text()
t = t.replace(
    'serde = { version = "1", features = ["derive"] }',
    'serde = { version = "1", default-features = false, features = ["derive"] }',
)
p.write_text(t)
PY
echo "--- 改后 Cargo.toml 的 [dependencies] ---"
sed -n '/\[dependencies\]/,$p' Cargo.toml
echo "--- 再看 -e features：serde 的 std 还在吗？ ---"
cargo tree -e features | grep -E "serde v|feature \"(std|derive)\"" || true

echo ""
echo "================ 观察结论 ================"
echo "derive feature 依赖 std（见 serde 自己的 Cargo.toml），而 serde_json 无条件需要 serde/std ——"
echo "所以即使你 default-features = false，feature 统一（并集）后 std 依然在："
echo "『你的 feature 开关不是依赖树里该 crate 特性的唯一决定者』（主文档 3.9 语义点 2 / 4.2）。"
