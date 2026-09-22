# languages —— 开发语言部分

Mosaic 的第 ① 部分。三条**并列**主线，对应「学 → 析 → 合」：

| 目录 | 主线 | 内容 |
|---|---|---|
| `studies/` | 学 | 6 门主流语言 × 126 个阶段的系统化学习路线 |
| `analysis/` | 析 | 语言设计解剖：C++ / Java / Python / Rust 的机制对比 |
| `tenet/` | 合 | Tenet 语言设计与 3 个编译器实现（cpp / rs / arm64） |

## studies —— 六门语言的学习路线

| 语言 | 路线文档 | 阶段数 |
|---|---|---|
| C | [`studies/c/c.md`](studies/c/c.md) | 16 |
| C++ | [`studies/cpp/cpp.md`](studies/cpp/cpp.md) | 23 |
| Go | [`studies/go/go.md`](studies/go/go.md) | 21 |
| Java | [`studies/java/java.md`](studies/java/java.md) | 23 |
| Python | [`studies/py/python.md`](studies/py/python.md) | 18 |
| Rust | [`studies/rs/rust.md`](studies/rs/rust.md) | 25 |
| **合计** | | **126** |

每个阶段目录（`studies/<语言>/ph<NN>-<slug>/`）固定四层交付物：

```
ph<NN>-<slug>/
├── <NN>-<slug>.md    知识文档
├── examples/         示例代码
├── exercises/        代码练习
└── project/          综合项目
```

## 文档站

本域的 VitePress 站点在 [`website/`](website/)，内容真源就是 `studies/`、`analysis/`、`tenet/` 三个目录。

```bash
cd languages/website && npm run build
```

## 校验

```bash
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links
```

## 写作规范

`languages/studies/` 下所有文档受 `.dsh/skills/tenetlang-notes/` 管辖；`analysis/` 与 `tenet/` 不在其列。
