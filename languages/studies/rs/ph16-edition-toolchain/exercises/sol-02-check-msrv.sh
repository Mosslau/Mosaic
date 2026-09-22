#!/usr/bin/env bash
# 来源：languages/rs/ph16-edition-toolchain/exercises/README.md 练习 2
# 说明：检查依赖的 MSRV —— 用 cargo metadata 提取依赖树中每个包的 rust-version，
#       汇总出「依赖要求的最高 MSRV」，并与本 crate 声明的 rust-version 对照。
# 验证环境：cargo 1.92.0（macOS arm64）+ python3；依赖经 rsproxy 镜像拉取
# 用法：bash sol-02-check-msrv.sh [cargo 工程目录]（默认当前目录）
# 验证状态：已验证——对 examples/ex04 的 /tmp/ph16-ex04-msrv/msrv-aware 工程实测输出（2026-09-02 复测确认）：
#   home 0.5.11: rust-version = 1.81
#   windows-sys 0.59.0: rust-version = 1.60
#   windows-targets 0.52.6: rust-version = 1.56（及其 windows_* 目标包）
#   本 crate msrv-aware 声明 rust-version = 1.85
#   依赖最高 MSRV = 1.81（home）
# 注：windows-* 等传递依赖版本随 crates.io 索引日期漂移，验收以输出结构为准
#   （home 0.5.11 由 MSRV 感知解析保证：只要 0.5.12 仍要求更高 rustc 就会持续选中）
# 加分项对照（cargo-msrv 0.19.3，已装）：cargo msrv show → MSRV is Rust 1.85.0
set -eu

DIR="${1:-.}"
cd "$DIR"

# cargo metadata 需要解析依赖；无网/未配镜像环境下对零依赖工程也能跑
META=$(cargo metadata --format-version 1 2>/dev/null)

echo "== 依赖树各包的 rust-version（MSRV 声明）=="
echo "$META" | python3 -c '
import json, sys
d = json.load(sys.stdin)
pkgs = d["packages"]
root_names = {p["name"] for p in pkgs if p["id"] in {m for m in d.get("workspace_members", [])}}

def rv_key(v):
    return tuple(int(x) for x in v.split(".")) if v else ()

rows = []
for p in pkgs:
    rv = p.get("rust_version")
    rows.append((p["name"], p["version"], rv or "（未声明）", p["name"] in root_names, rv_key(rv)))

for name, ver, rv, is_root, _ in sorted(rows, key=lambda r: (r[4], r[0])):
    tag = "（本 crate）" if is_root else ""
    print(f"  {name} {ver}: rust-version = {rv} {tag}")

dep_rvs = [r[4] for r in rows if not r[3] and r[4]]
if dep_rvs:
    top = max(dep_rvs)
    print(f"== 依赖最高 MSRV = {top[0]}.{top[1]} ==")
else:
    print("== 依赖均未声明 rust-version ==")
'
