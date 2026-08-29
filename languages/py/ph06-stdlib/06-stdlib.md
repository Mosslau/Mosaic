# Python 标准库阶段

> 面向自动化、数据分析、Web 服务方向，本阶段系统性熟悉 Python 自带工具库（batteries included），让脚本拥有路径处理、数据序列化、正则提取、日志、命令行与子进程调用的完整工程能力。

## 1. 概述

Python 标准库阶段的目标是：**能用 `pathlib` 熟练处理路径与文件，用 `re` 提取文本信息，用 `logging` 取代 `print` 调试，用 `argparse` 把脚本变成可配置的工具，用 `subprocess` 安全调用外部命令**。这一阶段把前五个阶段的基础语法、函数、OOP、文件操作组装成"能上生产"的脚本工程能力——**标准库本身就能解决大量基础问题**，动手前先查标准库是本阶段最重要的习惯。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 路径与文件 | `pathlib`、`os`、`sys`、`shutil` |
| 数据序列化 | `json`、`csv` |
| 时间与文本 | `datetime`、`re` |
| 工程化三件套 | `logging`、`argparse`、`subprocess` |
| 函数式工具 | `collections`、`itertools`、`functools` |
| 并发与测试概览 | `threading`、`multiprocessing`、`asyncio`、`unittest` |

**范围边界**：本阶段承接 ph05 文件操作与异常处理阶段，聚焦标准库本身。不涉及第三方库（ph08）、数据分析（ph09）、Web 框架（ph10）、测试主力 pytest（ph13）；`threading`/`multiprocessing`/`asyncio` 本节只做概览与选型，深入在 ph14 并发阶段。

## 2. 来源与演变

Python 标准库的核心哲学是 **"batteries included"（自带电池）**：解释器发行时捆绑大量实用模块，让开发者"开箱即用"。这一口号由 Guido van Rossum 在 1999 年提出——`http.server`、`sqlite3`、`email` 等模块让很多小需求零依赖解决。

标准库持续把社区实践收编进来：早期 `os`/`sys` 承袭 Unix 接口；2.3 加入 `logging`；2.6/3.0 加入 `json`（源自 simplejson）；3.4 年 `pathlib` 实验性进入（PEP 428），3.6 转正并引入 f-string（PEP 498）；3.9 的 `zoneinfo` 带来 IANA 时区；3.11 的 `tomllib` 原生解析 TOML。

| 版本 | 标准库里程碑 |
|------|-------------|
| Python 2.3 | `logging` 加入——日志有了"正规军" |
| Python 2.6 / 3.0 | `json` 加入（源自 simplejson） |
| Python 3.4 | `pathlib` 实验性加入（PEP 428） |
| Python 3.6 | `pathlib` 转正；f-string 引入 |
| Python 3.9 | `zoneinfo` IANA 时区数据库 |
| Python 3.11 | `tomllib` 只读 TOML 解析 |

## 3. 语法与参数

### 3.1 pathlib 路径处理

`pathlib` 用 **`Path` 对象**替代手写路径字符串：`/` 运算符拼接路径，跨平台自动处理分隔符（Windows 反斜杠 / POSIX 正斜杠）。

```python
from pathlib import Path

p = Path("data") / "2024" / "06"        # 用 / 拼接，等价于 os.path.join
print(p.name, p.parent)                 # 06 data/2024

f = Path("can_2024-06-01.log")
print(f.name, f.stem, f.suffix)         # can_2024-06-01.log can_2024-06-01 .log
f.write_text("hello", encoding="utf-8") # 写文件（自动 open/close）
print(f.read_text(encoding="utf-8"))    # 读文件
```

要点：

- **`pathlib` 优先于手写路径字符串**（roadmap 必会概念）：`"data/" + name` 跨平台会出分隔符 bug；**坑**是 `str(Path)` 与字符串混拼——要么 `Path` 到底，要么 `str` 到底。
- `Path` 实现了 `__fspath__` 协议，可直接传给 `open()`/`shutil`/`subprocess` 等 API；遍历用 `glob("*.log")`（单层）/ `rglob("*.log")`（递归）。

### 3.2 os·sys·shutil 系统交互

`os` 管"操作系统级"接口（环境变量、目录），`sys` 管"解释器级"接口（参数、版本、退出码），`shutil` 管"人类语义"的文件操作（复制、移动、归档）。

```python
import os, sys, shutil
from pathlib import Path

print(os.environ.get("HOME"))      # 读取环境变量
print(sys.version.split()[0])      # Python 版本

src = Path("a.txt")
src.write_text("data", encoding="utf-8")
shutil.copy2(src, "b.txt")                     # 复制（保留元数据）
Path("sub").mkdir(exist_ok=True)
shutil.move("b.txt", Path("sub") / "b.txt")    # 移动
shutil.rmtree("sub")                           # 删除目录树
```

要点：**不要用 `os.system()` 拼字符串执行外部命令**（那是 `subprocess` 的职责，3.8 节）；`sys.argv[0]` 是脚本名，`sys.exit(code)` 设置退出码，`shutil.rmtree` 递归删目录。

### 3.3 json·csv 数据序列化

承接 ph05 的完整读写用法，本阶段强调两条工程习惯：**`utf-8-sig` 写 CSV 让 Excel 打开中文不乱码**；**`default=str` 兜底序列化 `datetime` 等非 JSON 原生类型**。

```python
import json, csv
from datetime import datetime

print(json.dumps({"vin": "LSVAU2A28N2100001"}, ensure_ascii=False, indent=2))
print(json.dumps({"ts": datetime(2024, 6, 1)}, default=str))  # 兜底 datetime
with open("out.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["ts", "id"])
    w.writeheader()
    w.writerow({"ts": "2024-06-01 08:00:01", "id": "0x123"})
```

要点：**坑**：普通 UTF-8 写的 CSV 用 Excel 打开中文乱码——用 `utf-8-sig` 解决；`sort_keys=True` 让 JSON 键序稳定，人读记得 `ensure_ascii=False`。

### 3.4 datetime 时间处理

```python
from datetime import datetime, timedelta, timezone

now = datetime.now()
print(now.strftime("%Y-%m-%d %H:%M:%S"))                    # 格式化输出
dt = datetime.strptime("2024-06-01 08:00:01", "%Y-%m-%d %H:%M:%S")  # 解析
print(dt + timedelta(hours=2))                              # 时间运算
utc_now = datetime.now(timezone.utc)                        # aware：带时区
print(utc_now.isoformat())                                  # 2024-06-01T00:00:01+00:00
```

要点：**坑（时区）**：naive 与 aware `datetime` 直接比较会抛 `TypeError`；日志与数据库统一存 **UTC 或 ISO 字符串**，展示再转本地（3.9+ 用 `zoneinfo.ZoneInfo("Asia/Shanghai")`）。

### 3.5 re 正则表达式

```python
import re

pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")   # 编译一次，重复使用
print(pattern.findall("2024-06-01, 2024-06-15"))   # 有分组返回元组列表
print(re.search(r"\d+", "id=42").group())          # search：任意位置查找
print(re.sub(r"\s+", "_", "a b  c"))               # 替换
m = re.search(r"(?P<ip>\d+\.\d+\.\d+\.\d+)\s+E(?P<code>\d+)",
              "192.168.1.10 E1001")
print(m.group("ip"), m.group("code"))              # 192.168.1.10 1001
```

要点：

- **必须用原始字符串 `r"..."`**；**`re.findall` 有分组时返回分组值的元组列表**，提取字段用 `()`，别用 `.*` 吞整行。
- **坑（贪婪匹配）**：`.*` 默认贪婪会吞到最后一个可能位置，想最小匹配用 `.*?`（详见 4.2）。

### 3.6 logging 日志

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.debug("调试细节")      # 不输出（级别低于 INFO）
logging.info("任务开始")
logging.warning("磁盘剩余空间不足")
```

要点：

- **`logging` 优先于 `print` 调试**（roadmap 必会概念）：分级（DEBUG < INFO < WARNING < ERROR < CRITICAL）、带时间戳、可输出到文件、可统一关闭。
- **模块内用 `logger = logging.getLogger(__name__)`**（机制见 4.3）；**坑（配置陷阱）**：`basicConfig` 只在 root 未配置时生效，子模块日志默认向 root 冒泡，容易"打两遍"。

### 3.7 argparse 命令行

```python
import argparse

parser = argparse.ArgumentParser(description="车辆日志处理工具")
parser.add_argument("dir", nargs="?", default=".", help="目标目录（默认当前目录）")
parser.add_argument("--ext", default=".log", help="扩展名过滤")
parser.add_argument("--level", choices=["INFO", "WARN", "ERROR"],
                    default="ERROR", help="级别过滤")
parser.add_argument("--limit", type=int, default=100, help="条数上限")

args = parser.parse_args(["--ext", ".csv", "--limit", "50"])
print(args.dir, args.ext, args.level, args.limit)
print(parser.format_help())    # 自动生成 --help
```

要点：**`argparse` 让脚本变成工具**（roadmap 必会概念）：自动生成 `--help`、类型校验（`type=int` 非法值自动报错）、`choices` 枚举、`action="store_true"` 开关；常用参数给默认值，必需参数用 `required=True`。

### 3.8 subprocess 子进程

```python
import subprocess, sys

result = subprocess.run(
    [sys.executable, "-c", "print('hi from child')"],
    capture_output=True, text=True, timeout=10,   # 捕获输出 + 文本 + 超时
)
print(result.returncode, result.stdout.strip())

try:
    subprocess.run([sys.executable, "-c", "import sys; sys.exit(3)"], check=True)
except subprocess.CalledProcessError as e:
    print(f"非零退出码: {e.returncode}")

try:
    subprocess.run(["sleep", "5"], timeout=1)
except subprocess.TimeoutExpired:
    print("命令超时, 已被终止")
```

要点：**永远传参数列表而非拼接字符串**：`["ls", "-l"]` 安全，`shell=True` 有注入风险；`capture_output=True` + `text=True` 是捕获输出的标准组合，持续交互用 `Popen`。

### 3.9 collections·itertools·functools 函数式工具

```python
from collections import Counter, defaultdict
from functools import lru_cache, partial

words = ["error", "warn", "error", "error"]
print(Counter(words).most_common(2))      # [('error', 3), ('warn', 1)]
counts = defaultdict(int)
counts["error"] += 1                      # 缺失键自动初始化为 0

@lru_cache(maxsize=128)                   # 记忆化缓存
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)
print(fib(30))                            # 832040 —— 缓存让递归不再指数爆炸
double = partial(int, base=2)             # 预填参数
print(double("1010"))                     # 10
```

要点：**标准库能解决大量基础问题**（roadmap 必会概念）：`Counter` 统计、`defaultdict` 归组、`lru_cache` 缓存、`groupby` 分组；`itertools` 返回惰性迭代器，可流式处理大日志。

### 3.10 threading·multiprocessing·asyncio·unittest 概览

本阶段只要求**认识三种并发模型并会选型**（细节在 ph14）；`unittest` 能跑通最小用例即可。

```python
import asyncio, unittest
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def fetch(url):          # IO 密集任务：下载、读文件、网络请求
    return f"GET {url} ok"

def heavy(n):            # CPU 密集任务：大文件解析、数值计算
    return sum(range(n))

class TestMath(unittest.TestCase):
    def test_add(self):
        self.assertEqual(1 + 1, 2)

async def work(i):               # 协程：海量并发网络 IO
    await asyncio.sleep(0.1)
    return i * 2

async def main():
    return await asyncio.gather(*(work(i) for i in range(3)))

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:    # 线程池：IO 密集
        print(list(ex.map(fetch, ["a", "b", "c"])))
    print(asyncio.run(main()))                       # asyncio.run 只接受协程
    with ProcessPoolExecutor(max_workers=2) as ex:   # 进程池：CPU 密集
        print(list(ex.map(heavy, [10**6, 10**6])))
    unittest.main(exit=False)                        # 跑最小测试用例
```

| 场景 | 推荐 | 原因 |
|------|------|------|
| IO 密集（文件、网络、等待） | `threading` / `ThreadPoolExecutor` | 等待时释放 GIL，可重叠等待 |
| CPU 密集（计算、解析） | `multiprocessing` / `ProcessPoolExecutor` | 多进程绕过 GIL，真并行 |
| 海量并发网络 IO | `asyncio` | 单线程事件循环，开销最小 |

要点：**选型口诀：IO 用线程、CPU 用进程、海量网络 IO 用 asyncio**（原因见 4.4）；`ProcessPoolExecutor` 记得加 `if __name__ == "__main__":` 保护。

## 4. 底层原理

### 4.1 pathlib 与 os.path 的关系

`pathlib.Path` 本质是 **`os.path` 字符串函数的面向对象封装**：`/` 运算符内部调用 `os.path.join`，`rename()`/`mkdir()` 内部调用 `os.rename`/`os.makedirs`。`PurePath` 只做纯字符串运算、不触碰文件系统，`Path` 继承它并追加 `exists()`、`glob()` 等 IO 方法；`Path` 实现了 `__fspath__` 协议，可传给任何接受路径的 API。

| 字符串风格（os.path） | 面向对象（pathlib） |
|----------------------|--------------------|
| `os.path.join(a, b)` | `Path(a) / b` |
| `os.path.basename(p)` | `Path(p).name` |
| `os.path.splitext(p)` | `Path(p).stem` + `.suffix` |
| `os.path.exists(p)` | `Path(p).exists()` |

### 4.2 正则引擎基础（回溯、贪婪 vs 非贪婪）

Python `re` 是**回溯型（backtracking）NFA 引擎**：按顺序穷举所有可能路径，失败就回退重试。绝大多数模式没问题，但**嵌套量词**（如 `(a+)+b`）遇到不匹配文本可能触发**灾难性回溯（catastrophic backtracking）**，指数级膨胀拖垮进程——这是"正则把服务拖死"的经典事故。

| 写法 | 语义 | 对 `"<a>1</a>"` 匹配 `r"<.*>"` |
|------|------|--------------------------------|
| `.*` 贪婪 | 先吞到结尾，再逐字符回退找 `>` | 匹配整个 `<a>1</a>` |
| `.*?` 非贪婪 | 先只吞一个字符，再逐字符扩张 | 匹配 `<a>` |

实践建议：能用字符类就不用点号（`[^>]*` 比 `.*` 快且不越界）；复杂模式用 `re.VERBOSE` 写注释。

### 4.3 logging 的 Logger/Handler/Formatter 层级机制

logging 由三个角色协作：**Logger**（记录器）是代码调用入口，按包名构成**树状层级**（`getLogger("app.http")` 的父级是 `getLogger("app")`，根是 root）；**Handler**（处理器）决定日志去向（`StreamHandler` 控制台、`FileHandler` 文件、`RotatingFileHandler` 按大小回滚）；**Formatter**（格式化器）决定一行日志的样子。

关键机制是 **传播（propagation）**：子 logger 处理完记录后默认继续向祖先冒泡，直到 root。因此 `basicConfig` 只配置了 root 的 handler 时，子 logger 的日志会"自身输出一次，冒泡到 root 又输出一次"——**这就是"日志打两遍"的根因**；不想向上传播就设 `logger.propagate = False`。

```text
root                    ← 接收所有冒泡上来的记录
└─ app
   └─ app.http          ← 自身 handler 输出一次，再冒泡给 app、root → 重复
```

### 4.4 GIL 对多线程的影响（为 ph14 铺垫）

CPython 有一个 **GIL（Global Interpreter Lock，全局解释器锁）**：同一时刻只允许一个线程执行 Python 字节码。

- **IO 密集任务**（等待文件、网络、`sleep`）：等待期间线程**释放 GIL**，可重叠等待 → 线程池有效。
- **CPU 密集任务**（纯计算）：线程轮流抢 GIL，**无法并行**，甚至更慢 → 必须用 `multiprocessing`。

GIL 的完整影响（线程安全、锁、事件循环）留给 ph14，本阶段只需建立"**多线程不等于多核并行**"的认知。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 批量整理/重命名文件 | `pathlib.glob` + `Path.rename` + `shutil.move` |
| 解析日志提取时间/IP/错误码、统计分布 | `re.findall` + 命名分组 + `datetime.strptime` + `Counter` |
| 脚本输出分级日志 | `logging` + `RotatingFileHandler` |
| 把脚本变成可配置工具 | `argparse`（默认值、`--help`、类型校验） |
| 调用外部命令/其他语言工具 | `subprocess.run`（捕获输出、超时、`check=True`） |
| 缓存重复计算结果 | `functools.lru_cache` |
| 交换配置/数据 | `json`（`ensure_ascii=False`）、`csv`（`utf-8-sig`） |

**不适合此阶段的事项**：

- 高性能数值计算：用 NumPy（ph09 数据分析阶段）
- Web 服务框架：用 FastAPI（ph10 Web 后端阶段）
- 大规模并发与异步深入（线程安全、锁、事件循环）：ph14 并发阶段

## 6. 代码示例

### 示例 1：pathlib 批量整理文件（glob + 重命名）

呼应"批量移动文件 / 批量重命名工具"练习：把散落的日志文件按文件名中的日期归档到 `archive/YYYY-MM-DD/` 子目录，并统一加 `backup_` 前缀。

```python
import re, tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    for name in ["can_2024-06-01.log", "can_2024-06-02.log",
                 "diag_2024-06-01.log", "bms_2024-06-03.log", "readme.txt"]:
        (root / name).write_text("", encoding="utf-8")

    for f in root.glob("*.log"):            # glob 遍历 *.log
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if not m:
            continue
        target_dir = root / "archive" / m.group(1)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"backup_{f.name}"
        f.rename(target)                    # 移动 + 重命名一步完成
        print(f"{f.name} -> {target.relative_to(root)}")
```

### 示例 2：正则提取日志中的关键字段（re.findall，时间/IP/错误码）

呼应"正则提取日志 / 日志提取工具"练习：用 `re.findall` 提取时间、级别、IP、错误码，并统计错误码分布。

```python
import re, tempfile
from pathlib import Path
from collections import Counter

with tempfile.TemporaryDirectory() as d:
    log_path = Path(d) / "vehicle.log"
    log_path.write_text(
        "2024-06-01 08:00:01 ERROR 192.168.1.10 E1001 电芯压差异常\n"
        "2024-06-01 08:00:05 WARN  10.0.0.5   E2003 电机温度偏高\n"
        "2024-06-01 08:00:10 ERROR 192.168.1.11 E1002 BMS 通讯超时\n"
        "2024-06-01 08:00:15 WARN  192.168.1.10 E2003 电机温度偏高\n"
        "2024-06-01 08:00:20 ERROR 10.0.0.5   E1001 电芯压差异常\n",
        encoding="utf-8",
    )
    pattern = re.compile(
        r"(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"   # 时间
        r"\s+(?P<level>\w+)"                                # 级别
        r"\s+(?P<ip>\d+\.\d+\.\d+\.\d+)"                    # IP
        r"\s+(?P<code>E\d+)"                                # 错误码
    )
    rows = pattern.findall(log_path.read_text(encoding="utf-8"))
    code_count = Counter(row[3] for row in rows)
    print("错误码分布:", dict(code_count))
    for t, level, ip, code in rows:
        print(f"{t} [{level}] {ip} {code}")
```

### 示例 3：logging 配置与模块化日志（按级别输出、文件回滚）

呼应"能使用 logging"验收：控制台输出全部分级，文件按大小回滚（`RotatingFileHandler`）只留 INFO 以上。

```python
import logging, tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    log_file = Path(d) / "tool.log"
    logger = logging.getLogger("batch_tool")     # 模块化 logger，而非 root
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()            # 控制台：全部级别
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    rotate = RotatingFileHandler(                # 文件：INFO 以上，超 1KB 回滚
        log_file, maxBytes=1024, backupCount=2, encoding="utf-8",
    )
    rotate.setLevel(logging.INFO)
    rotate.setFormatter(fmt)
    logger.addHandler(console)
    logger.addHandler(rotate)
    logger.debug("调试细节（仅控制台可见）")
    logger.info("任务开始")
    for i in range(50):
        logger.warning(f"第 {i} 条告警")
    logger.error("处理失败")
    print("回滚文件数:", len(list(Path(d).glob("tool.log*"))))
```

### 示例 4：argparse 命令行工具（参数、默认值、--help）

呼应"命令行参数工具 / 批量重命名工具"练习：可配置的批量重命名工具，支持 `--dry-run` 预览。保存为 `rename_tool.py`，运行 `python3 rename_tool.py --help` 查看自动生成的帮助。

```python
import argparse
from pathlib import Path

def build_parser():
    parser = argparse.ArgumentParser(description="批量重命名工具（统一加前缀）")
    parser.add_argument("--dir", default=".", help="目标目录（默认当前目录）")
    parser.add_argument("--ext", default=".log", help="要处理的扩展名（默认 .log）")
    parser.add_argument("--prefix", default="backup_", help="新文件名前缀")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际改名")
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    root = Path(args.dir)
    if not args.ext.startswith("."):
        args.ext = "." + args.ext
    for f in sorted(root.glob(f"*{args.ext}")):
        new_name = args.prefix + f.name
        print(f"{'[DRY-RUN] ' if args.dry_run else ''}{f.name} -> {new_name}")
        if not args.dry_run:
            f.rename(f.with_name(new_name))

if __name__ == "__main__":
    main()
```

```python
# 演示两种模式（真实使用时从命令行传参）
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    for name in ["a.log", "b.log", "c.txt"]:
        (root / name).write_text("", encoding="utf-8")
    main(["--dir", d, "--ext", ".log"])                       # 实际改名
    print("改名后:", sorted(p.name for p in root.iterdir()))
    main(["--dir", d, "--ext", ".log", "--prefix", "again_", "--dry-run"])
    print("dry-run 后不变:", sorted(p.name for p in root.iterdir()))
```

### 示例 5：subprocess 调用外部命令并捕获输出（含超时）

呼应"subprocess 调命令"练习：调用系统命令统计行数、处理非零返回码、用超时保护防止外部命令卡死脚本。

```python
import subprocess, sys, tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as d:
    data = Path(d) / "data.txt"
    data.write_text("1\n2\n3\n", encoding="utf-8")

    result = subprocess.run(                 # 调用系统命令统计行数
        ["wc", "-l", str(data)],
        capture_output=True, text=True, timeout=10,
    )
    print("返回码:", result.returncode)
    print("输出:", result.stdout.strip())

    try:                                     # check=True：非零返回码抛异常
        subprocess.run([sys.executable, "-c", "import sys; sys.exit(2)"],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"命令返回非零退出码: {e.returncode}")

    try:                                     # 超时保护：防止外部命令卡死脚本
        subprocess.run(["sleep", "30"], timeout=2)
    except subprocess.TimeoutExpired:
        print("命令超过 2 秒未完成，已终止")
```

## 7. 总结

### 关键要点

1. **`pathlib` 优先于手写路径字符串**：`Path` 对象用 `/` 拼接，跨平台安全（roadmap 必会概念）
2. **`logging` 优先于 `print` 调试**：分级、带时间戳、可输出到文件、可审计（roadmap 必会概念）
3. **`argparse` 让脚本变成工具**：自动 `--help`、类型校验、默认值（roadmap 必会概念）
4. **标准库能解决大量基础问题**：动手前先查标准库文档，再考虑第三方（roadmap 必会概念）
5. **正则用原始字符串并优先 `re.compile`**：提取字段用分组 `()`；**贪婪默认吞到底，非贪婪用 `.*?`**
6. **`subprocess.run` 传参数列表**：`capture_output=True` + `text=True` 捕获输出，别用字符串拼接 + `shell=True`
7. **`datetime` 区分 naive 与 aware**：时区不统一是时间类 bug 的头号来源，存 UTC/ISO 展示再转本地
8. **`collections`/`itertools`/`functools` 减少手写循环**：`Counter`、`defaultdict`、`lru_cache`、`groupby` 即拿即用
9. **并发选型口诀：IO 用线程、CPU 用进程、海量网络 IO 用 asyncio**（GIL 与深入细节在 ph14）

### 跨语言对比：标准库与工程习惯

| 维度 | Python | Go | Java | C++ | Rust |
|------|--------|----|------|-----|------|
| 路径处理 | `pathlib.Path` | `path/filepath` | `java.nio.file.Path` | `std::filesystem::path` | `std::path::PathBuf` |
| 正则 | `re` | `regexp` | `java.util.regex` | `std::regex` | `regex` crate |
| 日志 | `logging` | `log`/`slog` | SLF4J/log4j | `spdlog` | `log`/`tracing` |
| 命令行解析 | `argparse` | `flag`/`cobra` | `picocli` | `CLI11` | `clap` |
| 子进程 | `subprocess` | `os/exec` | `ProcessBuilder` | `fork`+`exec` | `std::process::Command` |

### 阶段验收标准

- 能用 `pathlib` 熟练处理路径和文件：拼接、遍历、glob、重命名、移动（对应 roadmap"能熟练处理路径和文件"）
- 能用 `argparse` 写出带默认值、类型校验、`--help` 的 CLI 参数（对应 roadmap"能写 CLI 参数"）
- 能用 `logging` 输出分级日志，控制台与文件双通道（对应 roadmap"能使用 logging"）
- 能用 `re` 提取字段并统计；能用 `subprocess` 调用外部命令并处理失败与超时

### 进入下一阶段前

确保能完成以下练习：

- 批量移动文件：用 `pathlib` 遍历目录，按扩展名或文件名中的日期归类到子目录（提示：先 `--dry-run` 预览）
- 正则提取日志：用 `re.findall` + 命名分组提取时间/IP/错误码，用 `Counter` 统计分布（提示：先拿 5 行样本验证正则）
- 命令行参数工具：用 `argparse` 给批量重命名工具加 `--dir`/`--ext`/`--prefix`/`--dry-run`（提示：`--help` 免费送）
- subprocess 调命令：调用外部命令并捕获输出，加 `timeout` 与 `check=True` 的错误处理（提示：传参数列表，别拼 shell）
- 把 ph05 的批量重命名示例升级为 logging + argparse 版本（提示：把 `print` 换成 `logger`）

### 推荐项目

- **批量重命名工具**：pathlib + argparse + logging，支持扩展名过滤、前缀/后缀、`--dry-run`、递归目录，输出统计报告
- **日志提取工具**：re + datetime + collections.Counter，按时间/IP/错误码过滤，输出统计 CSV（把 json/csv 序列化一起收尾）

### 下一阶段

[虚拟环境与包管理阶段](../ph07-venv-packaging/07-venv-packaging.md) —— pip/venv、requirements.txt、pyproject.toml、poetry/uv。
