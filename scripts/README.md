# scripts —— 仓库工具脚本

## check-mermaid.sh — 文档 Mermaid 图渲染校验

文档里的流程图现在是**图即代码**：语法错了整张图不显示，且只在渲染端才暴露。改动任何 `.md` 里的 `mermaid` 块后跑一遍：

```bash
scripts/check-mermaid.sh                      # 全仓校验（跳过 .dsh/ 第三方技能文件）
scripts/check-mermaid.sh ingest/README.md     # 只校验指定文件
```

依赖 Docker（用 `minlag/mermaid-cli` 镜像渲染），临时产物在 `.tmp-mmdc/`（已 gitignore）。
**注意**：挂载目录必须在 `$HOME` 下——Rancher Desktop 只共享 `$HOME` 给 VM，`/tmp` 挂不进（与 `deploy/README` Q9 同源限制）。

## 文档图表约定

| 用 Mermaid | 保留代码块（不转） |
|---|---|
| 流程图 / 拓扑图 / 分层架构 / 泳道 / 状态机 / 时序 / 依赖树 | **目录树**（无 tree 语法，代码块对齐更好读）<br/>**字节布局与字段偏移**（`[类型 1B][版本 1B][长度 2B]` 这类精确表达）<br/>**公式**（对账等式）<br/>**配置对齐线**（`emqx.conf ═══ GATEWAY_WEBHOOK_TOKEN` 靠 `═══` 视觉表达对齐）<br/>**命令 / JSON 示例**（本就不是图） |

其它要求：

- **单一真相**：一处图只保留一种形式（转 Mermaid 即删 ASCII），避免两处漂移
- **大图拆分**：一张图超过 ~40 行就拆（例：架构总览 §1.1 的 154 行 ASCII 拆成"分层总览 / 接入层细节 / 湖仓与计算细节"三张）
- **渲染前提**：Mermaid 需要渲染器（GitHub / VS Code / GitLab / 多数 Markdown 预览）；纯终端 `cat` 不可读——因此**面向排障的速查内容仍用文字/表格**
