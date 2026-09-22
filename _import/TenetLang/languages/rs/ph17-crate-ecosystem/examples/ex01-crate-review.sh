#!/usr/bin/env bash
# examples/ex01-crate-review.sh —— 六维评审命令流水线骨架（主文档 3.2 / 示例 1）
# 把「评估一个 crate 能不能引进来」的六维清单翻译成可执行命令序列。
# 验证环境：bash 3.2+、python3；rustc/cargo 1.92.0。需联网：crates.io API 查询、
# cargo 拉取 crate（国内可配 rsproxy 镜像）、cargo audit 首次运行拉 RustSec 公告库。
# 运行：bash examples/ex01-crate-review.sh <crate 名>（建议先在临时目录 cargo init 一个空 crate）
# 未在本环境验证 —— 命令语义以 cargo / crates.io API / 各工具官方文档为准；cargo-deny/cargo-audit
# 未安装时对应步骤自动跳过（cargo install cargo-audit / cargo install cargo-deny --locked）。
set -u

CRATE="${1:?用法: bash ex01-crate-review.sh <crate 名>}"
echo "==================== 评审: ${CRATE} ===================="

echo ""
echo "== [1/6] 维护活跃度：最近版本 / 更新时间 / 下载量（crates.io API） =="
curl -s "https://crates.io/api/v1/crates/${CRATE}" -H "User-Agent: ph17-crate-review/0.1" \
  | python3 -c '
import json, sys
try:
    c = json.load(sys.stdin)["crate"]
except Exception:
    print("查询失败：crate 不存在或网络不可达"); raise SystemExit(0)
print("name          :", c["name"])
print("latest version:", c["max_version"])
print("updated_at    :", c["updated_at"])          # 最近一次 publish
print("recent_downloads:", c.get("recent_downloads"))
print("total_downloads :", c.get("downloads"))
'
echo "提示：updated_at 距今 > 1 年 → 活跃度红灯；近 90 天下载量是比总下载量更敏感的采用信号。"

echo ""
echo "== [2/6] API 稳定性：主版本与 0.x 状态（cargo search 或 crates.io 版本列表） =="
cargo search "${CRATE}" --limit 1 || echo "（cargo search 失败可忽略：直接看 [1/6] 的 max_version 判断）"
echo "提示：主版本 >= 1 才有 semver 硬承诺；0.x 的 minor 可破坏；再翻 docs.rs 的 CHANGELOG 确认节奏。"

echo ""
echo "== [3/6] 依赖树膨胀：引入并看两层内依赖（不满意可回退） =="
cargo add "${CRATE}" || echo "（cargo add 需要网络；失败则手工在 Cargo.toml 写依赖再 cargo build）"
cargo tree --depth 2 || true
echo "提示：干小事的 crate 若在 depth 2 内拖进大量重型传递依赖 → 膨胀信号。"

echo ""
echo "== [4/6] 重复版本体检：同一 crate 多版本并存 =="
cargo tree -d || true
echo "提示：-d 无输出 = 版本对齐良好；有输出则查是谁锁了老主版本（见主文档 4.2）。"

echo ""
echo "== [5/6] 已知漏洞扫描：cargo audit（RustSec 公告库） =="
if command -v cargo-audit >/dev/null 2>&1 || cargo audit --help >/dev/null 2>&1; then
    cargo audit
else
    echo "cargo-audit 未安装，跳过（安装：cargo install cargo-audit --locked，再跑 cargo audit）。"
fi

echo ""
echo "== [6/6] 许可证门禁（可选）：cargo deny =="
if command -v cargo-deny >/dev/null 2>&1; then
    # 首次运行生成 deny.toml 默认配置；licenses 子命令对照 SPDX 表达式做兼容检查
    cargo deny init 2>/dev/null || true
    cargo deny check licenses || echo "（license 冲突需人工核对：本脚本只报警不裁决）"
else
    echo "cargo-deny 未安装，跳过（安装：cargo install cargo-deny --locked）。"
fi

echo ""
echo "== 收尾：把结果填进六维清单（主文档 3.2 表格） =="
echo "① 维护活跃度 [1/6]  ② API 稳定性 [2/6]  ③ 依赖树膨胀 [3/6]+[4/6]"
echo "④ 许可证兼容 [6/6]  ⑤ unsafe 面（docs.rs 读源码 / cargo geiger 统计）"
echo "⑥ MSRV（cargo metadata 提取 rust-version，见 ph16 sol-02-check-msrv.sh）"
echo "结论一句话模板：这个 crate <能/不能> 引入，因为 <六维里最强/最弱的一项>；"
echo "替代方案：<列 1~2 个>；若引入，风险登记：<维护/漏洞/膨胀/许可/unsafe/MSRV>。"
