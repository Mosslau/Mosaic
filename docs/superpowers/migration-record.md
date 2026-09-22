# Mosaic 迁移记录

> 2026-09-22 三仓合并（TenetLang + MindSpring + OceanVerse → Mosaic）的**可跟踪**收尾记录，
> 取代不随仓库发布的进程账本 `.superpowers/sdd/2026-09-22-mosaic-merge/progress.md`。
> 设计依据：[`specs/2026-09-22-mosaic-merge-design.md`](specs/2026-09-22-mosaic-merge-design.md)；
> 实施依据：[`plans/2026-09-22-mosaic-merge.md`](plans/2026-09-22-mosaic-merge.md)。

## 1. 成果

- **仓库**：`https://github.com/Mosslau/Mosaic`（private，默认分支 `main`，本地与 `origin/main` 同步）
- **三部分结构**：`languages/`（① 开发语言）/ `algorithms/`（② 算法）/ `engineering/`（③ 工程系统，含 `ai-platform/` + `data-platform/`）
- **规模（发布提交时的快照：已跟踪文件 4702）**：`languages` 3907 / `engineering` 637 / `algorithms` 93 / `roadmap` 4 / `books` 1
  - `languages` 内部：studies 3789 / analysis 47 / tenet 42 / website 27
  - `engineering` 内部：ai-platform 529 / data-platform 107 / 域总览 `README.md` 1

## 2. 合并机制

```bash
git subtree add --prefix=_import/TenetLang  tl/main   # 同理 ms / ov；保留完整提交历史
git mv _import/<repo>/… <目标路径>                     # 逐域整体重排，重命名记为 R100
git rm -r _import && rm -rf _import                    # 最后清空暂存区
```

- **提交账目**（发布提交时的快照）：`HEAD 352 = 三仓历史 318（154 + 41 + 123）+ 本次 34`
- **本次 34** = 3 引导文档 + 3 个 `git subtree add` + 1 里程碑空提交 + 6 任务实施 + 5 修复 + 16 计划修正
- 三个源仓 tip：TenetLang `37b494a`（154）/ MindSpring `a0d1d7d`（41）/ OceanVerse `2ef5087`（123）

## 3. 验收门禁与实测值

spec §9 的 7 项门禁在发布提交上的实测结果：

| # | 门禁 | 实测 |
|---|---|---|
| ① | `tenetlang-notes/scripts/validate.py --links` | `0 个问题，0 条需人工核对`，exit 0 |
| ② | `mindspring-lab/scripts/validate.py` | `0 个硬伤，0 个警告`，exit 0 |
| ② | `python -m pytest -q` | `48 passed` |
| ② | `ruff`（差分记录，**非门禁**） | `522` 处，与迁移前持平（源仓 MindSpring 冻结点即 `420` + 45 文件需重排） |
| ③ | `check-docs.sh` / `check-compose-budget.sh` / `test-compose-budget.sh` | `文档校验: 全部通过` / `通过 5 项` / `8 项符合预期`，均 exit 0 |
| ③ | `docker compose config -q`（`deploy/docker-compose.yaml`） | exit 0（纯客户端解析，不需 daemon） |
| ③ | `check-mermaid.sh` | ⚠ **未验证**：需 Docker daemon + `minlag/mermaid-cli` 镜像 |
| ④ | `languages/website` 的 `npm run build` | `build complete`，0 条失效链接 |
| ⑤ | 历史连通（subtree 感知，**不是** `--follow`） | 3 个源 tip 均为 HEAD 祖先；`rev-list --count` = `154 41 123`；3 个内容比对一致 |
| ⑥ | 全仓残留路径扫描 | 已跟踪内容 0 命中 |
| ⑦ | 工作树干净 | `git status --porcelain` 空 |

## 4. 如何追溯历史（重要）

`git log --follow` **不能**穿过 `git subtree` 合并提交——历史挂在 merge 的**第二父**上，而 `--follow` 不跟 merge。
这是 git 的限制，不是搬迁缺陷。正确姿势是**按源 tip + 原路径**查：

```bash
# 例：某个文件在 TenetLang 里的完整历史（路径用源仓里的原路径）
git log 37b494a -- languages/go/go.md

# 配合 _import/ 暂存区的 R100 重命名记录，可定位搬迁那一步
git log --oneline -- _import/TenetLang/languages/go/go.md

# 连通性断言
git merge-base --is-ancestor 37b494a HEAD && echo OK
git rev-list --count 37b494a        # 154
```

三个源 tip：`37b494a`（TenetLang）/ `a0d1d7d`（MindSpring）/ `2ef5087`（OceanVerse）。

## 5. 已知限制与未验证项

1. **`check-mermaid.sh` 未验证**（唯一未闭合的门禁）：需 Docker daemon + `minlag/mermaid-cli` 镜像。Task 6 已用「无污染探针」在源仓内容副本上复现同样的失败，证明**非迁移回归**，但仍需在有 Docker 的机器上补跑。
2. **ruff 是既存红**（`522`）：三个源仓从未让 ruff 绿过，`mindspring-lab/validate.py` 也不运行 ruff。本次只保证**差分 0**（不新增）。
3. **Go module 路径仍为 `github.com/Mosslau/OceanVerse/...`**：实测 **63 个匹配**，其中 **58 个在 28 个 `.go` / `.mod` 文件**（模块声明与 import），另 4 个在 `engineering/data-platform/ingest/device-contracts/README.md`、1 个在本记录。它是**模块标识**而非路径，四个 Go 模块 `go build ./...` 均通过、编译不受影响；改名等于一次模块重构（`go.mod` + 全部 import + 文档）。
4. **内容域里的仓名自称（残留）88 行**：`docs/superpowers/` 之外共 **150 行**匹配仓名，其中 **62 行**是 Go module 路径（计入第 3 项，不是文案残留）；扣除后的**纯自称残留为 88 行** = `.md` **56 行**（engineering 35 / `.dsh` 14 / languages 6 / 顶层 `README.md` 1）+ 其他文件类型 **32 行**（`.sh` 5 / `.conf` 4 / `.py` 3 / `.c` 3 / `.yml` 2 / `.go` 2 / `.sql` 2 / `.css` 2 / `.svg` 2 / `.json` / `.gitignore` / `.example` / `.xml` / `.yaml` / `.mts` / `Dockerfile` 各 1）。按决策 D10 **刻意保留**，留待后续「文案统一」轮。
   > ⚠ 全部 `.md` 实测 **232 行**，其中 `docs/superpowers/` 内 **172 行**是**迁移自身的元文本**（本记录 / spec / plan 在讨论迁移本身），**不属残留**；后续「文案统一」时不要把它们当作自称清理掉。
5. **`languages/` 内约 169 个 L3 车辆教学示例刻意保留**（spec §2：py 87 / go 57 / java 23 / rs 2）：它们是语言路线的教学素材，与工程域的去车联网是两件事。

## 6. 后续项

1. **去车联网**（OceanVerse 域）：`GB/T 32960` 协议层、`VIN` 语义、相关 CI 断言保持原样，单独一轮处理。
2. **文案统一**：内容域仓名自称（**88 行**，排除 Go module 路径行；含则是 150）+ Go module 路径（63 个匹配，28 个 `.go` / `.mod` 文件）+ 站点标签（`languages/website` 的站点标题/描述仍是 `TenetLang`）。
3. **`check-mermaid` 补跑**：在装有 Docker daemon + `minlag/mermaid-cli` 的机器上闭合该门禁。
4. **三个源仓的归档状态**：截至本记录，`Mosslau/TenetLang` / `Mosslau/MindSpring` / `Mosslau/OceanVerse` **均未归档**（`isArchived=false`，Task 8 待执行）；发布仓 `Mosslau/Mosaic` 为 private、活跃。
