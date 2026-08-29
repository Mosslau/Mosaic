# Python 文件操作与异常处理阶段

> 在 OOP 基础上，掌握 Python 文件 I/O 的完整能力：用 `with` 安全管理资源、按编码读写常见格式（txt/csv/json/yaml/xml/log/excel）、用 `try/except/else/finally` 构建健壮的错误处理、写出能面对真实数据的车联网工具脚本。

## 1. 概述

Python 文件操作与异常处理阶段的目标是：**能以 `with` 安全打开文件并明确指定编码，能读写 txt/csv/json 三大格式，能用 `try/except/else/finally` 四段式健壮处理错误，能定义带错误码的自定义异常并通过 `raise from` 保留异常链**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件打开与模式 | `open()` 读写模式（`r`/`w`/`a`/`x`/`b`/`t`/`+`）、文本 vs 二进制 |
| 上下文管理器 | `with` 语句、`__enter__`/`__exit__` 协议、自动资源释放 |
| 编码 | `encoding` 参数、UTF-8 优先、Windows GBK 兼容陷阱 |
| CSV | `csv.reader`/`DictReader`/`writer`/`DictWriter`、`delimiter`/`quotechar` |
| JSON | `json.load`/`loads`/`dump`/`dumps`、`indent`/`ensure_ascii`、`JSONEncoder` |
| 其他格式 | yaml（PyYAML）、xml（`xml.etree.ElementTree`）、log（正则逐行解析）、excel（openpyxl） |
| 异常处理 | `try`/`except`/`else`/`finally` 四段式、捕获具体异常、`raise from` 保留链 |
| 自定义异常 | 继承 `Exception`、定义错误码和消息 |

**范围边界**：本阶段聚焦文件读写与异常处理核心机制，不涉及 `asyncio` 异步文件 I/O、`mmap` 内存映射、二进制序列化（`pickle`/`struct`）、`pathlib` 路径操作（归入 ph06 标准库阶段）。下一阶段为 **Python 标准库阶段**（ph06-stdlib，文档规划中）。

## 2. 来源与演变

Python 文件 I/O 继承 C 标准库 `fopen`/`fclose` 模型，Python 2.5（PEP 343）引入 `with` 语句和上下文管理器协议。异常方面：3.0 将 `except Exception, e:` 改为 `except Exception as e:`，并引入 `raise X from Y`（PEP 3134）异常链。

## 3. 语法与参数

### 3.1 `open()` 基础与文件模式

文件模式速查：`r` 只读（默认，文件须存在）；`w` 只写（创建或清空）；`a` 追加写；`x` 排他创建（已存在则 `FileExistsError`）；`b` 二进制模式（`rb`/`wb`/`ab`）；`t` 文本模式（默认）；`+` 读写模式（`r+`/`w+`/`a+`）。

```python
# 读取整个文件
with open("example.txt", "r", encoding="utf-8") as f:
    content = f.read()

# 逐行读取（大文件推荐 —— 迭代器惰性读取，不占内存）
with open("example.txt", "r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip("\n"))
```
文本模式（`t`，默认）自动处理平台换行符，返回 `str`；二进制（`b`）返回 `bytes`——图片、音频等非文本数据必须用 `b`。

### 3.2 `with` 上下文管理器

`with` 基于 **上下文管理器协议**：进入块时调用 `__enter__()`，离开时（即使抛异常）必定调用 `__exit__()` 执行 `close()`。

```python
# with 等价于以下手动写法
f = open("data.txt", "r", encoding="utf-8")
try:
    content = f.read()
finally:
    f.close()          # 即使 read() 抛异常也会执行
```

自定义上下文管理器演示协议本质：

```python
class FileLogger:
    def __init__(self, path):
        self.path = path; self.file = None
    def __enter__(self):
        self.file = open(self.path, "a", encoding="utf-8")
        self.file.write("--- START ---\n")
        return self.file
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.write("--- END ---\n")
        self.file.close()
        return False                # False = 不抑制异常；True = 吞掉

with FileLogger("session.log") as f:
    f.write("操作记录\n")
```

`__exit__` 三参数接收异常信息（无异常时全为 `None`）；返回 `True` 抑制异常。

### 3.3 `encoding` 指定 —— 不写就是埋坑

`open()` 默认编码取决于 `locale.getpreferredencoding()`：macOS/Linux 返回 `UTF-8`，**Windows 中文版返回 `cp936`（GBK）**。同一代码跨平台会乱码甚至 `UnicodeDecodeError`，**永远显式写 `encoding="utf-8"`**。

```python
# 错误：依赖系统默认编码 —— Windows 上用 GBK 读 UTF-8 文件 → 乱码
with open("data.txt", "r") as f: text = f.read()

# 正确：显式指定编码
with open("data.txt", "r", encoding="utf-8") as f: text = f.read()

# 处理未知编码：errors 参数控制错误策略
with open("legacy.csv", "r", encoding="utf-8", errors="replace") as f:
    text = f.read()        # 无法解码的字节替换为 �（U+FFFD）
# errors: 'strict'（抛异常，默认）| 'ignore'（跳过）| 'replace'（替换为 �）
```

### 3.4 `csv` 模块

核心类：`reader` 读→`list[str]`、`DictReader` 读→`dict`、`writer` 写→list、`DictWriter` 写→dict。

```python
import csv

# DictReader：按列名访问，推荐用于有表头的数据
with open("can_log.csv", "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)                       # 第一行自动作为列名
    for row in reader:
        print(f"{row['timestamp']} {row['can_id']}: {row['data']}")

# DictWriter：用 dict 写入，结构清晰
with open("output.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["ts", "id", "data"])
    writer.writeheader()                             # 写入表头
    writer.writerow({"ts": "08:00:01", "id": "0x123", "data": "A1B2"})
```

`delimiter` 处理 TSV（`delimiter="\t"`）等分隔符变体；`quotechar` 处理字段内含分隔符的引用。**车联网场景**：CAN 日志常以 CSV 导出，`DictReader` 按列名访问比 `reader` 按索引 `row[0]` 更可靠。

### 3.5 `json` 模块

核心函数：`load(f)` 文件→对象、`loads(s)` 字符串→对象、`dump(obj, f)` 对象→文件、`dumps(obj)` 对象→字符串。

```python
import json

with open("vehicle_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
print(config["vehicle"]["vin"])

# indent + ensure_ascii=False 写入可读 JSON
data = {"vehicle": {"vin": "LSVAU2A28N2100001", "品牌": "特斯拉"}}
json_str = json.dumps(data, indent=2, ensure_ascii=False)
print(json_str)
```

`ensure_ascii=False` 关键——默认 `True` 将非 ASCII 转义为 `\uXXXX`。非 JSON 原生类型（如 `datetime`）需自定义 `JSONEncoder` 子类重写 `default()`。

```python
import json
from datetime import datetime

class VehicleEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

log = {"event": "charge_start", "ts": datetime(2024, 6, 1, 8, 0, 0)}
print(json.dumps(log, cls=VehicleEncoder, ensure_ascii=False))
```

### 3.6 其他常见格式

| 格式 | 库 | 适用场景 | 核心用法 |
|------|----|---------|---------|
| **yaml** | PyYAML（pip 安装） | 人工编写配置 | `yaml.safe_load(f)` |
| **xml** | `xml.etree.ElementTree`（标准库） | 企业遗留接口 | `ET.parse(path)` → `.findall()` |
| **log** | 纯文本 + 正则 | 诊断日志分析 | `re.match(pattern, line)` 逐行 |
| **excel** | openpyxl（pip 安装） | 报表输出 | `load_workbook(path)` |

### 3.7 `try`/`except`/`else`/`finally` 四段式

核心规则：**`except` 按书写顺序匹配**（子类须在父类前）；**不裸写 `except:`**；**`else` 只在无异常时执行**；**`finally` 必定执行**（即使 `return` 也先执行）。

```python
def read_vehicle_config(path):
    """标准四段式：try → except → else → finally"""
    f = None
    try:
        f = open(path, "r", encoding="utf-8")
        data = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {path}"); return None
    except PermissionError:
        print(f"错误: 无权限读取 - {path}"); return None
    except UnicodeDecodeError as e:
        print(f"错误: 编码问题 - {e}"); return None
    else:
        # 仅在 try 无异常时执行 —— 适合放"依赖 try 成功"的逻辑
        print(f"读取成功: {len(data)} 字节"); return data
    finally:
        if f is not None: f.close()
        print("资源清理完成")
```

常见反模式：`except: pass` 吞掉所有异常；`except Exception: data = {}` 静默回退掩盖问题。正确做法：捕获具体异常并记录日志。

### 3.8 `raise from` 保留异常链

`raise X from Y` 将 `Y` 设为 `X` 的 `__cause__`；`raise X from None` 断开链。

```python
def load_config(path):
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ValueError(f"配置文件不存在: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {path}") from e

try:
    load_config("nonexistent.json")
except ValueError as e:
    print(f"业务错误: {e}")      # ValueError: 配置文件不存在: nonexistent.json
    print(f"根因: {e.__cause__}") # FileNotFoundError: [Errno 2] No such file ...
```

### 3.9 自定义异常

```python
class ConfigError(Exception):
    """配置文件异常 —— 携带错误码和字段信息"""
    def __init__(self, code, field, message):
        self.code = code; self.field = field
        super().__init__(f"[{code}] {field}: {message}")

def validate_sensor_config(cfg):
    required = ["sensor_id", "type", "unit", "range_min", "range_max"]
    for f in required:
        if f not in cfg:
            raise ConfigError("E001", f, "缺少必填字段")
    if cfg["range_min"] >= cfg["range_max"]:
        raise ConfigError("E002", "range", "range_min 必须小于 range_max")

try:
    validate_sensor_config({"sensor_id": "T-001", "type": "温度"})
except ConfigError as e:
    print(f"校验失败: {e} (code={e.code}, field={e.field})")
```

错误码让调用方程序化判断；始终调用 `super().__init__()` 确保 `str(e)` 正确。

## 4. 底层原理

### 4.1 文件对象与缓冲

`open()` 返回 `TextIOWrapper`（文本模式）或 `BufferedReader`/`BufferedWriter`（二进制），默认缓冲区 `io.DEFAULT_BUFFER_SIZE`（8192 字节）。`write()` 写入缓冲区，`flush()`/`close()` 时才落盘——不关文件丢数据的根因。

```python
f = open("data.txt", "w", encoding="utf-8")
f.write("important data")  # 在缓冲区
f.flush()                  # 强制刷盘
f.close()                  # 自动 flush 后关闭
```

### 4.2 上下文管理器协议栈

`with` 编译为 `SETUP_WITH` + `WITH_CLEANUP` 字节码，`__exit__` 是 C 级保证——`SystemExit`/`KeyboardInterrupt` 也会执行清理，仅 `SIGKILL` 无法拦截。

### 4.3 异常匹配机制

`except SomeException` 使用 `isinstance(exc_value, SomeException)` 匹配——捕获父类也捕获其所有子类，如 `except OSError` 覆盖 `FileNotFoundError`/`PermissionError`/`TimeoutError`。多个 `except` 按书写顺序匹配，子类必须写在父类前面。

## 5. 使用场景

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 读取文本配置文件 | `with open(... encoding="utf-8")` + 手动解析 | 最可控，适合 `.cfg`/`.ini` 等自定格式 |
| 解析 CAN 日志 CSV | `csv.DictReader` + 列名访问 | 表头自解释，不受列顺序变化影响 |
| 读写 JSON 配置/API 数据 | `json.load`/`json.dump` + `indent`/`ensure_ascii` | 结构化、人类可读、跨语言 |
| 解析诊断日志 | `re` 逐行匹配 + `try/except` 容错 | 非结构化文本，逐行处理避免大内存 |
| 异常转换 | `raise BusinessError(...) from e` | 保留根因同时转成上层可理解的异常 |
| 资源必须释放 | `with` 语句 / `try-finally` | 文件句柄、网络连接、锁等资源 |

## 6. 代码示例

### 示例 1：读取车辆配置文件

```python
import os, tempfile

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "app.cfg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 车辆平台配置\n[server]\nhost = 0.0.0.0\nport = 8080\n")
        f.write("[battery]\nchemistry = LFP\ncapacity_kwh = 70.0\n")

    config, section = {}, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1]; config[section] = {}
                elif "=" in line and section is not None:
                    k, v = line.split("=", 1)
                    config[section][k.strip()] = v.strip()
    except FileNotFoundError:
        print("错误: 文件不存在")
    except PermissionError:
        print("错误: 无权限读取")
    else:
        print(f"配置解析成功: {config}")
```

### 示例 2：CAN 日志 CSV 解析

```python
import csv, os, tempfile

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "can_log.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "can_id", "dlc", "data"])
        w.writerow(["2024-06-01 08:00:01", "0x123", "8", "A1B2C3D4E5F6A7B8"])
        w.writerow(["2024-06-01 08:00:02", "0x18F", "4", "11223344"])
        w.writerow(["2024-06-01 08:00:03", "0x123", "8", "FFEEDDCCBBAA9988"])

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            msgs = [{"ts": r["timestamp"], "id": r["can_id"],
                      "data": r["data"]} for r in reader]
        matches = [m for m in msgs if m["id"] == "0x123"]
        print(f"共 {len(msgs)} 条 CAN 消息, 0x123 出现 {len(matches)} 次")
        for m in matches:
            print(f"  {m['ts']} -> data={m['data']}")
    except FileNotFoundError:
        print("CSV 文件不存在")
    except csv.Error as e:
        print(f"CSV 解析错误: {e}")
```

### 示例 3：车辆配置 JSON 读写

```python
import json, os, tempfile

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "vehicle.json")
    vehicle = {
        "vin": "LSVAU2A28N2100001", "model": "Model-Y",
        "battery": {"capacity_kwh": 70.0, "nominal_voltage_v": 400}
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vehicle, f, indent=2, ensure_ascii=False)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"VIN={data['vin']} 容量={data['battery']['capacity_kwh']}kWh")
        data["battery"]["soc_pct"] = 85.0
        out_path = os.path.join(d, "vehicle_updated.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        with open(out_path, "r", encoding="utf-8") as f:
            reloaded = json.load(f)
        print(f"round-trip 成功: soc={reloaded['battery']['soc_pct']}%")
    except FileNotFoundError:
        print("JSON 文件不存在")
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
    except KeyError as e:
        print(f"缺少字段: {e}")
```

### 示例 4：诊断日志分析

```python
import os, tempfile, re
from collections import Counter

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "diag.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write("2024-06-01 08:00:01 INFO  BMS-001 电池温度正常 32C\n")
        f.write("2024-06-01 08:00:05 WARN  MCU-003 电机温度偏高 85C\n")
        f.write("2024-06-01 08:00:10 ERROR BMS-001 电芯压差异常 0.15V\n")
        f.write("2024-06-01 08:00:15 INFO  VCU-002 车速 60km/h\n")
        f.write("2024-06-01 08:00:20 ERROR MCU-003 过流保护触发 320A\n")

    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
        r"\s+(INFO|WARN|ERROR)"
        r"\s+([A-Z]+-\d+)"
        r"\s+(.+)"
    )
    level_count = Counter()
    comp_errors = Counter()

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    level = m.group(2); comp = m.group(3)
                    level_count[level] += 1
                    if level in ("ERROR", "WARN"):
                        comp_errors[comp] += 1
    except FileNotFoundError:
        print("日志文件不存在")

    print(f"日志级别统计: {dict(level_count)}")
    print(f"部件告警/错误次数: {dict(comp_errors)}")
    if comp_errors:
        worst = comp_errors.most_common(1)[0]
        print(f"最需关注部件: {worst[0]} (共 {worst[1]} 次)")
```

### 示例 5：批量重命名 + 自定义异常 + `raise from`

```python
import os, tempfile

class BatchRenameError(Exception):
    """批量重命名异常，携带失败文件路径和原因"""
    def __init__(self, path, reason):
        self.path = path; self.reason = reason
        super().__init__(f"重命名失败: {os.path.basename(path)} - {reason}")

def batch_rename_ext(dir_path, old_ext, new_ext, dry_run=True):
    """批量修改文件扩展名。dry_run=True 时只预览不实际操作。"""
    if not old_ext.startswith("."): old_ext = "." + old_ext
    if not new_ext.startswith("."): new_ext = "." + new_ext
    renamed = 0
    for fname in os.listdir(dir_path):
        if not fname.endswith(old_ext): continue
        old_path = os.path.join(dir_path, fname)
        new_path = os.path.join(dir_path, fname[:-len(old_ext)] + new_ext)
        if os.path.exists(new_path):
            raise BatchRenameError(fname, f"目标文件已存在: {new_path}")
        try:
            if not dry_run: os.rename(old_path, new_path)
            renamed += 1
            print(f"{'[DRY RUN] ' if dry_run else ''}{fname} -> {os.path.basename(new_path)}")
        except OSError as e:
            raise BatchRenameError(fname, str(e)) from e
    return renamed

with tempfile.TemporaryDirectory() as d:
    for name in ["can_001.log", "can_002.log", "can_003.log", "diag.txt"]:
        open(os.path.join(d, name), "w").close()
    count = batch_rename_ext(d, ".log", ".csv", dry_run=True)
    print(f"预览完成: {count} 个文件将被重命名")
    remaining_logs = [n for n in os.listdir(d) if n.endswith(".log")]
    print(f"dry_run 后仍有 {len(remaining_logs)} 个 .log 文件（未实际修改）")
```

## 7. 总结

### 关键要点

1. **`with` 是文件 I/O 的唯一正确打开方式**：离开作用域自动关闭，绝不泄漏句柄
2. **永远显式指定 `encoding="utf-8"`**：不写依赖系统默认，Windows 上是 GBK 会导致乱码
3. **文本 vs 二进制**：文本用 `r`/`w`（返回 `str`），图片/二进制协议用 `rb`/`wb`（返回 `bytes`）
4. **`csv.DictReader` 优先于 `csv.reader`**：按列名访问不受列顺序影响
5. **`json.dump` 记得 `ensure_ascii=False`**：否则中文变成 `\uXXXX` 不可读
6. **`except` 捕获具体异常类型**：不裸写 `except:` 或 `except Exception:` 吞掉所有错误
7. **`else` 放依赖 try 成功的逻辑**：不让 `except` 意外捕获 `else` 中的异常
8. **`finally` 必定执行**：即使有 `return`/`break`/`continue` 也先执行
9. **`raise NewError(...) from original`**：保留异常链，根因不丢失
10. **自定义异常继承 `Exception`**：携带错误码和业务字段，调用方可程序化处理

### 跨语言对比：文件操作与异常处理

| 维度 | Python | Go | Java | C++ |
|------|--------|----|------|-----|
| 资源自动释放 | `with` 上下文管理器 | `defer f.Close()` | try-with-resources | RAII（析构函数） |
| 错误传递 | `try`/`except` 异常 | `if err != nil` 返回值 | `try`/`catch`/`throw` | 异常 + `noexcept` |
| 异常链保留 | `raise X from Y`（`__cause__`） | `fmt.Errorf("...: %w", err)` | `initCause()` 构造器链 | `throw_with_nested` |
| 编码默认 | 系统 locale 依赖（坑） | 显式 UTF-8（安全） | 平台默认 | `std::locale` 全局影响 |
| 文件关闭保底 | `with` 保证 `__exit__` 必调 | `defer` 保证 | `finally` / try-with-resources | 析构函数保证 |

### 阶段验收标准

- 能用 `with open()` 安全读写文件并显式指定编码，区分文本与二进制模式
- 能读写 txt/csv/json 三种核心格式，了解 yaml/xml/log/excel 的入口方法
- 能写 `try`/`except`/`else`/`finally` 四段式；捕获具体异常不裸写 `except`
- 能用 `raise from` 保留异常链；能定义带错误码的自定义异常

### 进入下一阶段前

确保能完成以下练习：
- 读配置文件（ini 格式手动解析）
- 解析 CSV（CAN 日志统计 CAN ID 出现次数）
- 读取 JSON（车辆配置 round-trip）
- 日志分析（正则提取错误行统计故障频率）
- 批量重命名（扩展名批量修改 + dry-run）

### 推荐项目

- **日志分析工具**（按部件 + 级别统计输出 CSV）
- **文件批处理工具**（按扩展名分类移动/重命名，dry-run 预览）

### 下一阶段

**Python 标准库阶段**（ph06-stdlib，文档规划中）—— `os`/`sys`/`pathlib`/`shutil`、`datetime`/`re`/`logging`/`argparse`/`subprocess`、`collections`/`itertools`/`functools`。
