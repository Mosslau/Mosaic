# exercises —— 测试与工程质量阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节对应：工具函数测试、数据处理测试、mock 外部接口；练习 5（类型注解/mypy）对应「学习内容」中的类型注解与 mypy，是工程质量的另一半。

完成顺序建议：按 1~5 顺序完成（逐步叠加：pytest 基础 → fixture 组织 → mock 隔离 → 参数化 + 覆盖率 → 类型注解 + lint）。

## 依赖与验证方式

- 依赖：练习 1/2/4 只用**标准库**（零安装）；练习 3 需要 `pip install requests`（本环境 2.32.5 已装）；练习 5 需要 `pip install mypy ruff`（本环境 mypy 1.17.1、ruff 0.12.0 已装）；pytest 8.4.2 已装
- 运行：`python3 -m pytest sol-XX-*.py -q`（sol 文件内同时含被测代码与测试，pytest 直接收集）
- 覆盖率：pytest-cov 本环境未安装，用标准库实测：`python3 -m trace --count --summary --coverdir /tmp/ph13-sol-cover --ignore-dir <你的 site-packages 路径> --module pytest sol-XX-*.py -q`（summary 末尾给出每个模块的 lines/cov%）
- 产物纪律：临时文件一律走 pytest 的 `tmp_path` fixture（系统临时目录，自动清理）——运行后 `git status` 工作区干净
- 参考实现文件头带**验证块**：环境、运行命令、实测输出（测试数、覆盖率为本机实际运行结果）

## 练习 1：工具函数测试（★）

- **目标**：给一组字符串/文本工具函数写 pytest 测试，掌握断言与异常测试的基本姿势
- **要求**：
  - 实现 `reverse(s)`、`is_palindrome(s)`、`count_words(text)`、`word_freq(text)` 四个函数（自己写一份实现）
  - 用 `assert` 覆盖正常输入与空输入；`is_palindrome` 用参数化覆盖 3 组（真/假/空串）
  - 加一个 `tmp_path` 用例：把词表存成 JSON 再读回（`json.dumps/loads`），验证往返一致
- **验收**：`python3 -m pytest sol-01-string-utils.py -q` 全过（参考实现 9 个用例）；每个函数至少被一个用例调用

## 练习 2：fixture 组织测试数据（★★）

- **目标**：用 fixture 管理测试前置与共享状态（对应「数据处理测试」的工程化组织）
- **要求**：
  - 实现 `TaskStore` 任务存储类：`add(title)` 返回自增 id、`list()` 按 id 排序、`mark_done(id)` 翻转状态（不存在返回 False）
  - 设计 fixture：`empty_store`（空库）、`prefilled_store`（预置 3 条任务，依赖一个先建目录的 fixture）、`scope="session"` 的启动计数 fixture、一个 `autouse` fixture（每个用例自动建目录）
  - 至少 8 个用例覆盖：自增 id、排序、标记完成、不存在 id、session 共享（两个用例都断言计数为 1）、autouse 生效、双 fixture 隔离
- **验收**：全部用例通过；能说清每个 fixture 的 scope 与依赖关系（参考实现 8 个用例）

## 练习 3：mock 外部接口（★★）

- **目标**：用 `unittest.mock` 隔离网络依赖，让测试离线、快、可复现（对应 roadmap「mock 外部接口」）
- **要求**：
  - 实现 `TelemetryFetcher`：`fetch_speed(vehicle_id)` 调 `requests.get(..., timeout=2)` 并 `raise_for_status()`；`fetch_batch(ids)` 逐条调用 `fetch_speed`
  - 测试：成功路径断言返回值与**调用参数**（`assert_called_once_with` 含 timeout）；HTTPError 与 ConnectTimeout 路径；`patch.object` 替换实例方法验证 `fetch_batch` 复用了单条逻辑；响应缺 `speed` 字段应抛 KeyError
  - 全程不许真的发网络请求（mock 后测试进程内完成）
- **验收**：`python3 -m pytest sol-03-telemetry-fetcher.py -q` 全过（参考实现 7 个用例）；能说清 `patch` 上下文管理器与装饰器两种写法等价

## 练习 4：参数化 + 覆盖率（★★★）

- **目标**：用参数化覆盖边界值，用标准库 `trace` 实测覆盖率（对应「数据处理测试」+「覆盖率」）
- **要求**：
  - 实现三个车辆遥测处理函数：`categorize_speed`（invalid/low/normal/high 四档边界）、`parse_reading`（"42.5 km/h" → 42.5，非法输入抛 ValueError）、`estimate_range(battery, consumption)`（能耗 ≤ 0 抛 ValueError）
  - 参数化覆盖全部边界：速度的 0/30/120 三个分界点两侧、非法读数的 4 组、续航计算的 3 组 + 1 组异常
  - 用上面的 trace 命令测覆盖率，**把实测行数与百分比写进 sol 文件头验证块**
- **验收**：参考实现 18 个用例全过、覆盖率 100%（36 行全命中）；能说清「覆盖率 100% 不等于没有 bug」（只证明测过的行都跑过）

## 练习 5：类型注解 + mypy + ruff（★★★）

- **目标**：给数据处理模块补全类型注解，通过 mypy 与 ruff 双门禁（对应「学习内容」类型注解/mypy）
- **要求**：
  - 实现 `InventoryItem`（`@dataclass`：sku/name/price/qty）与四个函数：`total_value`（货值求和）、`find_by_sku`（返回 `InventoryItem | None`）、`low_stock(items, threshold=5)`、`stock_report`（SKU → 数量）
  - 全部签名带完整类型注解（含容器泛型 `list[InventoryItem]` 与联合类型）；至少 8 个测试用例
  - 门禁：`mypy sol-XX-*.py` 0 错误、`ruff check sol-XX-*.py` 0 错误、pytest 全过、trace 覆盖率数字写入验证块
- **验收**：三项门禁全绿（参考实现 8 个用例、覆盖率 100%、mypy Success、ruff All checks passed）；能说清「注解让调用方与工具链都能发现类型错误」

> **提示**：练习 1~5 与主文档 3.x 小节一一对应（3.1 pytest 基础、3.2 fixture、3.3 mock、3.4 参数化与覆盖率、3.5 类型注解与 mypy、3.6 ruff）；做完后对照 `sol-*` 参考实现复盘——先独立完成，再看答案。
