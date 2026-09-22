# ex05-sbom-generate —— SBOM 生成实测（SPDX-2.3 / CycloneDX-1.6）

对应主文档 3.9。用 cargo-sbom 对「含真实三方依赖」的工程生成 SBOM 并保存样例。核心认识：**SBOM 的价值在生成之后的程序化消费**——依赖一变（哪怕 patch 升级），SBOM 里的成分与漏洞可查性就变，所以发布物附 SBOM 要与发布同源同版（project 的 release-check.sh 把这一步编进了流水线）。

## 验证状态

- **已验证**（本机 macOS arm64 / cargo 1.92.0 / cargo-sbom **0.10.0**，2026-09-04）：对实验工程（依赖 time 0.1.35 / libc / winapi）实测生成，样例见本目录两个 JSON
- **工具事实**：cargo-deny **0.20.2 已移除 `sbom` 子命令**（可用命令只剩 check/fetch/init/list）——SBOM 生成走独立工具 cargo-sbom（本项目实测）或 cargo-spdx（另一社区工具）；主文档 3.9 以本文实测为准
- 生成命令需在含 Cargo.lock 的工程内运行；首次运行 cargo metadata 需联网解析 registry

## 目录结构

```text
ex05-sbom-generate/
├── sample-spdx-2.3.json        # 真实输出：SPDX-2.3（cargo sbom --output-format spdx_json_2_3）
├── sample-cyclonedx-1.6.json   # 真实输出：CycloneDX 1.6（--output-format cyclone_dx_json_1_6）
└── README.md                   # 本文件
```

## 安装与运行

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cargo install cargo-sbom --locked        # 本机 0.10.0，已验证
cd <含 Cargo.lock 的 cargo 工程>

cargo sbom --output-format spdx_json_2_3 > sbom.spdx.json          # SPDX-2.3（默认）
cargo sbom --output-format cyclone_dx_json_1_6 > sbom.cdx.json     # CycloneDX 1.6
# 支持的格式：spdx_json_2_3 / cyclone_dx_json_1_4 / _1_5 / _1_6
```

## 实测输出的结构（对照样例文件）

**SPDX-2.3（`sample-spdx-2.3.json`）**：

```text
spdxVersion: SPDX-2.3
packages: 5 个 —— ph24-vulndemo(license=NOASSERTION，根包自身)
                 time 0.1.35(MIT OR Apache-2.0) / libc 0.2.189(MIT OR Apache-2.0)
                 kernel32-sys 0.2.2(MIT) / winapi 0.2.8(MIT)
relationships: 7 条依赖关系边（DEPENDS_ON）
```

**CycloneDX 1.6（`sample-cyclonedx-1.6.json`）**：

```text
bomFormat: CycloneDX / specVersion: 1.6 / version: 1
components: 4 个 —— 不含根包自身（libc / kernel32-sys / time / winapi）
每个 component 带 license.expression（如 "MIT OR Apache-2.0"）
```

**两格式的差异是可读出的**：SPDX 把根包与依赖都列成 packages 并保留 NOASSERTION（未声明许可）；CycloneDX 只列第三方 components、根包语义在 metadata——**选哪种格式取决于你的下游工具链**（SPDX 偏许可证合规、CycloneDX 偏漏洞/依赖图），不必二选一，发布时附其一即可（主文档 3.9 对比表）。

## 样例文件怎么来的

```bash
mkdir -p /tmp/ph24-exp/vulndemo/src
# …（构造依赖 time = "=0.1.35" 的工程，cargo generate-lockfile，见 ex01）
cd /tmp/ph24-exp/vulndemo
cargo sbom --output-format spdx_json_2_3 > sbom.spdx.json
cargo sbom --output-format cyclone_dx_json_1_6 > sbom.cdx.json
```

> ⚠️ 零依赖工程也能生成 SBOM，但成分列表只有根包自己（如 ex07 pkgdemo）——教学上保留一次「空转」体验可以，工程上要验证「SBOM 有内容」需真实依赖树。本示例特意用含三方依赖的实验工程生成，样例文件即是「有内容的 SBOM」的参照。

## 发布物附 SBOM 的最小姿势（project 落地）

```bash
# 与 cargo package 同源同版生成并归档（示意，完整见 project/release-check.sh）
cargo sbom --output-format spdx_json_2_3 > target/release/sbom.spdx.json
# 发布时把 sbom.spdx.json 作为 release asset 与 .crate 一同归档
```
