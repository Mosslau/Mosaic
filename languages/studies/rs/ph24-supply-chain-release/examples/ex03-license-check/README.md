# ex03-license-check —— 许可证清单自动核对

对应主文档 3.6。一个零依赖脚本（bash + python3 + `cargo metadata`）把工程的依赖树 license 字段拉出来，与 allow 清单核对，输出「哪几个包 OK / 哪几个需人工确认」。它是 cargo deny 的 `licenses` 段的轻量替代与补充——deny 需要装 cargo-deny（本机未装），而本脚本在**任何有 cargo + python3 的机器**都能跑，适合先自查再上正式门禁。

## 验证状态

- **已验证**（本机 macOS arm64 / cargo 1.92.0 / python3 3.13.12，2026-09-04）：在零依赖工程（ex07 pkgdemo）与含三方依赖工程（vulndemo：time/libc/winapi 等）上均实测通过，见下方真实输出
- 它只核对 `license` **元数据**——license-file 型声明与缺失字段需要人工，脚本如实标 MANUAL

## 目录结构

```text
ex03-license-check/
├── check-licenses.sh   # 用法：./check-licenses.sh [cargo 工程目录]（缺省当前目录）
└── README.md           # 本文件
```

## 运行命令与实测输出

```bash
export PATH="$HOME/.cargo/bin:$PATH"   # 确保 cargo 在 PATH
cd ex03-license-check
./check-licenses.sh ../ex07-publish-preview    # 零依赖工程
./check-licenses.sh <任一含三方依赖的工程目录>  # 真实依赖树工程
```

**实测输出 ①（零依赖工程 ex07 pkgdemo）：**

```text
== 工程：ph24-pkgdemo ==
== allow 清单：MIT /Apache-2.0 /BSD-3-Clause /ISC /MPL-2.0 /0BSD /Unicode-3.0 /Zlib（含 OR 组合）==

状态      crate                          version      license
------------------------------------------------------------------------
OK      ph24-pkgdemo                   0.1.0        MIT OR Apache-2.0

汇总：依赖核对 1 个 / allow 命中 1 / 需人工确认 0
结论：全部命中 allow 清单
```

**实测输出 ②（含三方依赖工程 vulndemo：time 0.1.35 链）：**

```text
状态      crate                          version      license
------------------------------------------------------------------------
OK      kernel32-sys                   0.2.2        MIT
OK      libc                           0.2.189      MIT OR Apache-2.0
MANUAL  ph24-vulndemo                  0.1.0        <未声明>      ← 根包没写 license！
OK      time                           0.1.35       MIT/Apache-2.0  ← 老式斜杠写法，OR 拆解后命中 MIT
OK      winapi                         0.2.8        MIT
OK      winapi-build                   0.1.1        MIT

汇总：依赖核对 6 个 / allow 命中 5 / 需人工确认 1
结论：存在需人工确认项 → 排查 license 缺失或 allow 清单外的许可（主文档 3.6）
```

**输出的两个教学点**：① 根包（发布物自身）license 缺失同样会被标 MANUAL——发布前记得给 `Cargo.toml` 写 `license`（主文档 3.6/3.10）；② `time 0.1.35` 的老式 `MIT/Apache-2.0`（斜杠）是历史遗留写法，脚本按 `OR` 拆开后命中 MIT——真实世界数据比文档脏，核对脚本的容错是必要的。

## 与 cargo deny licenses 的关系

| 维度 | 本脚本 | `cargo deny check licenses` |
|------|--------|---------------------------|
| 安装成本 | 无（cargo + python3） | 需 `cargo install cargo-deny` |
| 输出形态 | 文本清单 + 退出码 | 结构化报告 + 退出码 |
| 策略文件 | allow 清单在脚本内 | deny.toml 的 `[licenses]` 段（含 confidence/exceptions） |
| 建议用法 | 自查/教学/无 deny 环境 | CI 正式门禁（同源 allow 清单，见 ex02 deny.toml） |

## 裁剪 allow 清单

脚本顶部的 `ALLOW_LICENSES` 变量按你的分发模式改：内部应用可放宽（加 GPL/LGPL 类评估项），闭源商业分发收紧。三档建议见主文档 3.4 表格。
