# ex06-secret-handling —— secret 注入的最小形态

对应主文档 3.7。一个零依赖 bin crate 演示 secret 管理的三条纪律的最小落地：**不入库、不硬编码、最小权限注入**。代码从环境变量读 secret，读不到就显式失败；「用到但不泄露」的最小示范（输出长度而非内容）。

## 验证状态

- **已验证**（本机 macOS arm64 / rustc/cargo 1.92.0，2026-09-04；两条运行路径均实测）

## 目录结构

```text
ex06-secret-handling/
├── Cargo.toml        # 零依赖 bin
├── README.md         # 本文件
└── src/main.rs       # load_secret + main（读环境变量、失败显式报错、不回显）
```

## 运行命令与实测输出

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph24-ex06-target
cd ex06-secret-handling

# 路径 ①：没有注入 secret —— 显式失败（不拿空值继续跑）
cargo run
# 实测输出：
#   Error: "缺少环境变量 CRATES_IO_TOKEN：请注入，不要写进代码"

# 路径 ②：注入 dummy token —— 输出长度、不回显内容
CRATES_IO_TOKEN=dummy cargo run
# 实测输出：
#   token 已就绪（长度 5，内容不回显）
```

## 纪律清单（为什么这么写）

| 纪律 | 落地姿势 | 违反的后果 |
|------|---------|-----------|
| 不入库 | `.env`/`*.pem`/`*.key` 进 `.gitignore`；确认从未 commit | token 进 git 历史 = 已泄露（`git rm` 删不掉历史） |
| 不硬编码 | 代码只读环境变量，字符串字面量里零 secret | 代码仓库 = secret 分发渠道 |
| 最小权限注入 | CI 平台 secret 只给需要的 job；crates.io token 带作用域 + 过期（3.7） | 一次配置泄露 = 账号级泄露 |
| 失败显式化 | `env::var` 读不到返回 Err，进程终止 | 空值/占位符继续跑 = 下游拿假凭据或误发 |
| 不回显 | 只用长度/哈希做校验，不 `println!` 内容 | 日志即泄露面 |

## cargo 侧的 secret 形态

```bash
cargo login                        # 存 API token 到 ~/.cargo/credentials.toml（权限 600）
cargo logout                       # 删除本地凭证
# CI 发布场景（project/.github/workflows/release.yml 的最小权限形态）：
#   env: { CARGO_REGISTRY_TOKEN: ${{ secrets.CRATES_IO_TOKEN }} }  # 平台 secret，永不进日志
```

> ⚠️ 这是「最小形态」教学示例，不含真实密钥。团队级 secret（SOPS 加密入库 / Vault 动态取用）是同一原理的工程化放大：**加密与保管分离，使用侧永远只有最小权限**（主文档 3.7 概念层，不在本仓库实操密钥）。
