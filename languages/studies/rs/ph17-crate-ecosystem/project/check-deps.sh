#!/usr/bin/env bash
# project/check-deps.sh —— fetch-cli 依赖体检脚本（配套 REPORT.md 第 3 节取证）
# 验证环境：bash 3.2+；cargo 1.92.0。需联网拉取依赖（国内配 rsproxy）；cargo-audit / cargo-deny 为可选子命令。
# 运行：bash check-deps.sh（应在含 fetch-cli 依赖清单的 crate 目录执行；无则先建空 crate 并抄 REPORT.md 第 2 节依赖）
# 未在本环境验证 —— 命令语义以 cargo 官方文档为准；工具缺失时优雅跳过。
set -u

echo "================ [③依赖树膨胀] cargo tree --depth 2 ================"
cargo tree --depth 2 || echo "（cargo tree 失败：确认当前目录是 cargo 工程且依赖已解析，可能需要先 cargo fetch）"

echo ""
echo "================ [③ 重复版本] cargo tree -d ================"
cargo tree -d || true
echo "无输出 = 版本对齐良好；有输出 = 见 REPORT.md 第 3 节维度③与主文档 4.2。"

echo ""
echo "================ [③ 反向影响面] cargo tree -i reqwest ================"
cargo tree -i reqwest || true

echo ""
echo "================ [① 已知漏洞] cargo audit ================"
if command -v cargo-audit >/dev/null 2>&1 || cargo audit --help >/dev/null 2>&1; then
    cargo audit || echo "⚠️ audit 发现漏洞：先看公告影响版本是否命中锁定版本；命中则升级或换替代方案（REPORT.md 第 4 节）"
else
    echo "cargo-audit 未安装，跳过（安装：cargo install cargo-audit --locked）"
fi

echo ""
echo "================ [④ 许可证] cargo deny check licenses ================"
if command -v cargo-deny >/dev/null 2>&1; then
    cargo deny check licenses || echo "⚠️ license 冲突：对照 REPORT.md 维度④（本项目预期全 MIT OR Apache-2.0，冲突即需人工裁决）"
else
    echo "cargo-deny 未安装，跳过（安装：cargo install cargo-deny --locked）"
fi

echo ""
echo "================ 收尾提示 ================"
echo "把上面输出归档进 REPORT.md：维度③ 附 cargo tree 输出、维度① 附 audit 结果、"
echo "维度④ 附 deny 结果；openssl-sys 若出现在 tree 里 → rustls 路线被破坏，回查 Cargo.toml 的 reqwest feature。"
