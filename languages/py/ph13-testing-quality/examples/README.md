# examples —— 测试与工程质量阶段完整示例

> 每个示例对应主文档 `13-testing-quality.md` 相关小节（3.x / 4.x / 6 章）的完整可运行版。验证环境：Python 3.13.9（macOS）；工具链：pytest 8.4.2、ruff 0.12.0、mypy 1.17.1、black 25.9.0（本机已装并实测）；pytest-cov 未安装 → 覆盖率用标准库 `trace` 模块实测；pre-commit 未安装（配置示例见主文档 3.7 与 project 扩展方向）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-pytest-basics.py` | pytest 基础：断言、`pytest.raises` 异常测试、`tmp_path` 临时文件、参数化初体验（主文档 3.1/3.2/3.4） | `python3 -m pytest ex01-pytest-basics.py -q`（离线） |
| `ex02-fixture-scope.py` | fixture 进阶：`scope="session"` 共享、`autouse` 自动生效、工厂模式、fixture 依赖注入（主文档 3.2/4.2） | `python3 -m pytest ex02-fixture-scope.py -q`（离线） |
| `ex03-mock.py` | mock 外部依赖：`unittest.mock` 的 `patch`/`MagicMock`/`side_effect` 隔离网络请求（主文档 3.3/4.3） | `python3 -m pytest ex03-mock.py -q`（离线，不会真的发请求） |
| `ex04-parametrize.py` | 参数化测试 + 覆盖率：边界值参数化 + 标准库 `trace` 测覆盖率（主文档 3.4/4.4） | `python3 -m pytest ex04-parametrize.py -q`；覆盖率命令见下 |
| `ex05-mypy.py` | 类型注解 + mypy：dataclass、联合类型、Protocol 的干净版（主文档 3.5） | `mypy ex05-mypy.py`；`python3 ex05-mypy.py` |
| `ex05b-mypy-bugs.py` | 故意出错示例：4 处类型错误供 mypy 演示（主文档 3.5/4.5），**勿直接运行** | `mypy ex05b-mypy-bugs.py` |
| `ex06-ruff.py` | ruff 配置 + 干净代码：lint 与格式双通过（主文档 3.6，配置见 `pyproject.toml`） | `ruff check ex06-ruff.py`；`python3 ex06-ruff.py` |
| `ex06b-ruff-bad.py` | 故意出错示例：6 处 lint 违规供 ruff 演示（主文档 3.6），**勿直接运行** | `ruff check ex06b-ruff-bad.py` |
| `pyproject.toml` | 本目录 ruff 校验基准（line-length 100、select E/F/I/UP/B） | 被上方 ruff 命令自动读取 |

说明：

- **产物纪律**：ex05/ex06 的运行产物一律写到系统临时目录（`tempfile.mkdtemp`）；ex01~ex04 的临时文件由 pytest 的 `tmp_path` fixture 自动创建并清理——运行后用 `git status` 可确认工作区干净。
- **依赖状态**：pytest 8.4.2、ruff 0.12.0、mypy 1.17.1、black 25.9.0 在本环境已安装并实测；**pytest-cov 未安装**，覆盖率改用标准库 `trace` 模块实测（`python3 -m trace --count --summary --coverdir /tmp/ph13-cover --ignore-dir <你的 site-packages 路径> --module pytest ex04-parametrize.py -q`）；**pre-commit 未安装**，其配置只以示例形式出现在主文档 3.7。
- 全部示例离线可跑：ex03 用 mock 替换 `requests.get`，从不真正联网；ex05b/ex06b 是「故意出错」示例，文件首行注释已写明运行前提，仅用于演示工具报错。

验证状态（全部在本环境实际运行，已验证）：

- `ex01`：`10 passed`（3 基础断言 + 1 tmp_path + 参数化 3+3 组）
- `ex02`：`7 passed`（session 共享 2 + autouse 1 + 工厂 2 + 依赖注入 2）
- `ex03`：`6 passed`（成功 2 + HTTPError 1 + 超时 1 + side_effect 序列 1 + 自动 mock 陷阱 1）
- `ex04`：`14 passed`；本模块覆盖率 **100%**（trace 实测：25 个可执行行全命中）
- `ex05`：`mypy ex05-mypy.py` → `Success: no issues found in 1 source file`；运行输出 3 行（`EV-001,42.0,88.0` / `{'EV-001': 48.5, 'EV-002': 30.0}` / `['EV-001: 42.0 km/h']`）
- `ex05b`：`mypy ex05b-mypy-bugs.py` → **Found 4 errors**（assignment / incompatible types / attr-defined / arg-type 各 1，故意出错）
- `ex06`：`ruff check ex06-ruff.py` → `All checks passed!`；`ruff format --check ex06-ruff.py` → `1 file already formatted`；运行输出合并后行数 2、报表 3 行
- `ex06b`：`ruff check ex06b-ruff-bad.py` → **Found 6 errors**（I001 导入顺序 / F401 未使用导入 / F821 未定义名称 / F841 未使用变量 / E722 裸 except / E501 行超长，故意出错）
