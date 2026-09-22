# ph03 阶段项目：CLI 工具（txtool 文本文件工具箱）

## 需求

对应 Roadmap「ph03 函数与模块化阶段」推荐项目第一个「CLI 工具」：用 `sys.argv` 解析命令，用模块组织命令处理函数，支持 `--help` 和子命令。

实现一个文本文件工具箱 `txtool`，提供 `wc` / `grep` / `head` / `tail` 四个子命令。核心教学点是**多模块组织**：

- `ops.py`：文本处理纯函数（输入行列表、输出结果，不做 IO）
- `files.py`：文件读写封装
- `cli.py`：`sys.argv` 解析 + 子命令分发
- `__main__.py`：包入口，支持 `python3 -m txtool`

## 功能清单

- [ ] `wc <文件>`：统计行数、词数、字符数
- [ ] `grep <关键词> <文件>`：显示包含关键词的行（带行号）
- [ ] `head <n> <文件>`：显示前 n 行
- [ ] `tail <n> <文件>`：显示后 n 行
- [ ] `-h` / `--help` 显示用法说明
- [ ] 未知命令给出提示并列出可用命令
- [ ] 命令处理函数按模块组织（`ops.py` 纯函数 + `files.py` 文件读写 + `cli.py` 分发）

## 验收标准

- `python3 -m txtool wc sample.txt` 输出 `行数: 5`、`词数: 26`、`字符数: 157`
- `python3 -m txtool grep "reusable" sample.txt` 输出 `3: Modules organize reusable code.`
- `python3 -m txtool head 3 sample.txt` 输出前 3 行；`python3 -m txtool tail 2 sample.txt` 输出后 2 行
- `python3 -m txtool` 或 `python3 -m txtool --help` 显示用法说明
- 命令处理逻辑分布在独立模块，`cli.py` 只负责解析和分发
- 全程不引入第三方库，仅用标准库 `sys`

## 扩展方向（可选）

- 用 `argparse` 替换手写 `sys.argv` 解析，获得自动生成的帮助信息 —— 属于 ph06 标准库阶段
- 为 `ops.py` 写 `pytest` 单元测试 —— 属于 ph13 测试与工程质量阶段
- 文件不存在时友好报错（`FileNotFoundError` 处理）—— 属于 ph05 文件操作与异常处理阶段

## 验证环境

Python 3.13.12。运行（在 `project/` 目录下）：

```bash
python3 -m txtool --help
python3 -m txtool wc sample.txt
python3 -m txtool grep "reusable" sample.txt
python3 -m txtool head 3 sample.txt
python3 -m txtool tail 2 sample.txt
```

已在本环境验证。
