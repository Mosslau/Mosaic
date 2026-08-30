# 外部规范 Skill 来源追踪

本目录（`.workbuddy/skills/`）下除 `tenetlang-notes`（自建）外的 6 个 skill 均为外部引入，此处记录上游来源以便更新追踪。

| Skill | 上游仓库 | 上游路径 | 引入时 commit | 引入日期 |
|-------|---------|---------|--------------|---------|
| cpp-coding-standards | [affaan-m/ecc](https://github.com/affaan-m/ecc) | `skills/cpp-coding-standards/` | `d8e6a51` (2026-08-29) | 2026-08-30 |
| rust-patterns | [affaan-m/ecc](https://github.com/affaan-m/ecc) | `skills/rust-patterns/` | `d8e6a51` (2026-08-29) | 2026-08-30 |
| golang-patterns | [affaan-m/ecc](https://github.com/affaan-m/ecc) | `skills/golang-patterns/` | `d8e6a51` (2026-08-29) | 2026-08-30 |
| python-patterns | [affaan-m/ecc](https://github.com/affaan-m/ecc) | `skills/python-patterns/` | `d8e6a51` (2026-08-29) | 2026-08-30 |
| java-coding-standards | [affaan-m/ecc](https://github.com/affaan-m/ecc) | `skills/java-coding-standards/` | `d8e6a51` (2026-08-29) | 2026-08-30 |
| markdown-style | [josiahsiegel/claude-plugin-marketplace](https://github.com/josiahsiegel/claude-plugin-marketplace) | `plugins/doc-master/skills/markdown-style/` | `5a1b112` (2026-06-18) | 2026-08-30 |

## 更新方式

引入方式为手动复制（非 `npx skills add`），因此**无自动更新机制**。需要更新时：

```bash
# 以 ecc 系列为例
TMP=$(mktemp -d) && git clone --depth 1 https://github.com/affaan-m/ecc "$TMP/ecc"
diff -r "$TMP/ecc/skills/golang-patterns" .workbuddy/skills/golang-patterns
# 确认变更后覆盖
cp -r "$TMP/ecc/skills/golang-patterns" .workbuddy/skills/
# 更新本表的 commit 与日期
```

## 本地修改原则

- **不改外部 skill 原文**：需要项目级覆盖时，改 `tenetlang-notes`（L1）而非外部 skill（L2/L3）——外部 skill 保持与上游可 diff，本地补丁会让更新时无法干净合并
- 选型与审查结论见 `books/agent-skills-comparison.md`
