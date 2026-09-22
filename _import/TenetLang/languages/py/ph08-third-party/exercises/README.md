# exercises —— 第三方库阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节一一对应：请求 API、抓取网页、分析 CSV、画图、写 FastAPI 接口。

完成顺序建议：按 1~5 顺序完成。依赖安装：`pip install requests beautifulsoup4 pandas matplotlib "fastapi[standard]"`（承接 ph07 的 venv 做法，先在虚拟环境里装）。

## 练习 1：请求 API（★）

- **目标**：用 requests 请求一个公开 API（如 httpbin.org 或 GitHub API），把请求封装成可复用的函数
- **要求**：
  - 必须显式传 `timeout`，禁止裸 `requests.get(url)`
  - 先 `resp.raise_for_status()` 再 `.json()`；超时、HTTP 错误、网络错误三类异常分开捕获，错误信息里带上 URL
  - 封装成函数 `fetch_json(url, timeout=10) -> dict`，`__main__` 中演示一次真实调用
- **验收**：对 `https://httpbin.org/json` 调用能打印出 JSON 里的字段；对一个会返回 404 的 URL 调用时，抛出带 URL 信息的错误而非静默失败

## 练习 2：抓取网页（★★）

- **目标**：requests + BeautifulSoup 抓一个页面，提取标题与全部链接，存成 CSV
- **要求**：
  - 先看页面 HTML 结构再定 CSS 选择器（`soup.select(...)`）
  - 链接去重、排序；中文页面注意 `resp.encoding = resp.apparent_encoding`
  - 用标准库 `csv` 写出 `links.csv`（两列：link_text, href）——小任务不引 pandas，体会"依赖成本"
  - 页面若是 JS 动态渲染，说明为什么 requests 拿不到、应换什么方案（写在注释里即可，不要求实现）
- **验收**：对 `https://example.com` 运行后生成 `links.csv`，至少含 1 行数据；`file` 命令确认是合法 CSV

## 练习 3：分析 CSV（★★）

- **目标**：pandas 读 CSV → `info()` 看类型 → 筛选 → `groupby` 统计 → `to_csv(index=False)` 输出
- **要求**：
  - 输入数据可自己造（参考 `examples/ex03-csv-analysis.py` 的生成方式）或用任意公开 CSV
  - 至少一次布尔筛选、一次 `groupby` 聚合（mean/sum/count 均可）
  - 筛选后若要继续使用结果，注意索引：`reset_index()` 恢复 0..n-1
  - 输出文件必须 `index=False`，不带行号列
- **验收**：脚本运行后打印分组统计表，并生成 `result.csv`；用 `head result.csv` 确认首行是表头而非索引

## 练习 4：画图（★★）

- **目标**：matplotlib 画一张折线图 + 一张柱状图（同图双子图或两张图均可），`savefig` 存 PNG
- **要求**：
  - 脚本开头 `matplotlib.use("Agg")`，保证无显示环境（服务器/CI）也能跑
  - 图必须有标题、x/y 轴标签；多序列要有图例
  - 数据可复用练习 3 的统计结果（推荐：把 3、4 连成"分析 → 出图"小链路）
- **验收**：运行后生成 PNG 文件且非空（`ls -l` 大小 > 0）；在无显示环境（`ssh` 或 `env -i`）下运行不报错

## 练习 5：写 FastAPI 接口（★★★）

- **目标**：FastAPI + Pydantic 实现一个资源的最小 CRUD（至少 GET 列表 + POST 新增），并用 TestClient 或浏览器 `/docs` 验证
- **要求**：
  - 用 Pydantic `BaseModel` 声明请求体模型，字段至少一个 str、一个数值
  - POST 成功返回 201；请求体类型不符应自动返回 422（不准手工 if 检查类型）
  - `__main__` 里用 `fastapi.testclient.TestClient` 自测合法与非法两种请求
  - 选做：`uvicorn main:app --reload` 启动，浏览器打开 `/docs` 截图对比自动文档
- **验收**：TestClient 自测输出 POST 合法 201、POST 非法 422、GET 返回刚新增的资源

> **提示**：练习 1~5 与主文档第 6 章示例 1/2/3/4 主题一一对应——先独立完成，再对照 `examples/` 检查思路。`sol-*` 为参考实现，做完再看。
