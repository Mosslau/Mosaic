# ph17 阶段项目：流式日志处理器（streamlog）

> 对应 roadmap 第 17 节「推荐项目」第一个「流式日志处理器」——把本阶段四层协议（迭代/生成、装饰器、上下文管理器、dataclass）合流成一个真实可用的命令行工具；第二个推荐项目「可复用装饰器库」由 [`../exercises/`](../exercises/) 的练习 1/2 与 [`../examples/ex02-decorators-advanced.py`](../examples/ex02-decorators-advanced.py) 覆盖。

## 需求

日志文件动辄几百 MB、上百万行，`readlines()` 整读会直接吃光内存。**流式日志处理器**把「读 → 解析 → 过滤 → 输出/统计」建成一条**逐行流动的生成器管线**：任何时刻内存里只有一行——四个阶段模块各司其职，且每个都是主文档某个协议的教学落点：

- **生成器流式处理**（主文档 3.1/3.2）：`reader.read_lines` 逐行产出（只迭代文件对象、从不整读）；`parser.parse_lines` 惰性解析为结构化记录——内存与文件大小无关；
- **装饰器横切**（主文档 3.3）：`filters.Counted` 装饰器把「条数 + 耗时」统计从管线业务里切出去，业务函数保持纯净，`--stats` 时按阶段汇总；
- **上下文管理器资源管理**（主文档 3.4）：`sinks.FileSink` 用 `with` 管理输出句柄（异常也必关、不吞异常）；cli 用 `ExitStack` 动态组合输出资源；
- **dataclass 结构化记录**（主文档 3.8）：`parser.LogRecord` 一行一对象，`slots=True` 省内存。

```text
管线（惰性，逐行流动）：
  read_lines ──▶ parse_lines ──▶ [by_level] ──▶ [by_pattern] ──▶ 写 sink / 计数
      │               │
  （生成器）      （dataclass 记录）      （生成器过滤链）     （上下文管理器 + 装饰器统计）
```

## 功能清单

- [x] `streamlog/reader.py`：`read_lines(source)` 生成器——文件或 stdin（`-`）逐行产出，无整读
- [x] `streamlog/parser.py`：`parse_line`/`parse_lines`——默认语法 `LEVEL message`（LEVEL ∈ DEBUG/INFO/WARN/ERROR/CRITICAL），脏行跳过（cli 汇总为 skipped）；`LogRecord` dataclass（frozen + slots）
- [x] `streamlog/filters.py`：`Counted` 装饰器（条数/耗时横切统计，`update_wrapper` 保身份）；`by_level`/`by_pattern` 惰性过滤生成器
- [x] `streamlog/sinks.py`：`FileSink` 上下文管理器——文件/stdout 双形态、异常路径必关、`written` 报告
- [x] `streamlog/cli.py`：`argparse` 入口——`--file`（默认 stdin）/`--level`（可多次）/`--pattern`/`--stats`/`--out`/`--quiet`；错误路径退出码：文件打不开 1、正则错误 2
- [x] `pyproject.toml`：ruff（E/F/I/UP/B、line-length 100）+ pytest 配置（`pythonpath=["."]`）；`[project.scripts] streamlog`
- [x] `tests/test_streamlog.py`：13 个 pytest 用例（parser/reader/过滤器/装饰器/sink/5 万行流式集成/CLI 各路径）

## 验收标准

- 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12；纯标准库、无第三方运行依赖（dev 依赖仅 pytest/ruff）
- `python3 -m pytest` → **全部通过**（project 目录内；`tests/` 13 个用例）
- `ruff check .` → `All checks passed!`；`ruff format --check .` → 全绿
- 流式性：`test_pipeline_counts_on_big_file` 用 5 万行样本断言计数正确且 dirty 行被跳过；`reader.py` 源码不出现 `readlines()`/`.read(`（静态证据，同 exercises 练习 4 的手法）
- CLI 冒烟（示例命令，stdout 为纯数据便于管道）：
  ```bash
  # 1. 造个样例日志再跑（样例工具在 tests/test_streamlog.py 的 build_sample，或自造若干
  #    "ERROR xxx" 行）
  # 2. 只留 ERROR 并打印统计（统计在 stderr，数据在 stdout）
  python3 -m streamlog.cli --file app.log --level ERROR --stats
  # 3. 按正则过滤命中行写入文件
  python3 -m streamlog.cli --file app.log --pattern "timeout" --out hits.log
  # 4. 管道形态：tail 实时喂 stdin 也能流式跑
  tail -f app.log | python3 -m streamlog.cli --level WARN --pattern "disk"
  ```
- **验证状态：已验证**（Python 3.13.9 + pytest 8.4.2 + ruff 0.12.0 本机实测：`python3 -m pytest` 13 用例全绿、`ruff check .` 与 `ruff format --check .` 全绿）

## 运行手册

```bash
# 1.（可选）装 dev 依赖（仅本地校验用；运行本身零依赖）
python3 -m pip install "pytest>=8" "ruff>=0.4"

# 2. 测试
cd project
python3 -m pytest          # 等价：python3 -m pytest -q

# 3. lint 与格式
ruff check .
ruff format --check .

# 4. 试用（任选）
printf 'INFO boot ok\nERROR disk full\nWARN retry\nERROR oom\n' | \
    python3 -m streamlog.cli --level ERROR --stats
# 预期 stdout：两行 ERROR 原文；stderr：level 分布与各段条数/耗时
```

## 扩展方向

- **接 examples/ex05 的机制认知**：把 CLI 升级为「跟随模式」（`tail -f` 语义：文件增长时继续读新行）需要保留文件偏移——生成器的暂停帧正是实现它的自然载体（读一行、`yield`、外部记录偏移）
- **加 `async for` 版本**：接 ph14/主文档 3.9——数据源换成异步流（如 MQTT/WebSocket 日志推送）时，把管线各环改造成异步生成器（`async def` + `yield`），骨架不变（衔接 roadmap 第 18 节数据平台分析方向：MQTT 数据采集服务即此形态）
- **Cython 加速解析热环**：主文档 3.10 的四代形态——`parse_line` 的正则解析是热环，量级不够时先测 profile，真到瓶颈再用 Cython 加类型（`project/` 的 parser 是理想的渐进改造对象）
- **加 `--json` 输出 / 结构化 sink**：LogRecord 已有 dataclass 形态，序列化到 JSON/按级别分文件（旋转）作为新 sink 接入 `ExitStack`
- **复用进 ph18 场景**：BUS 日志按 ID 流式统计（roadmap 第 18 节）——把 `by_level` 换成 `by_bus_id`、`LogRecord` 换成 BUS 帧记录，管线骨架原样复用
