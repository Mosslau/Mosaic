# Python 数据分析阶段

> 面向自动化、数据分析、车联网数据平台方向，本阶段用 NumPy 与 Pandas 完成数据读取、清洗、统计，并用 Matplotlib/Plotly 可视化，让"拿到 CSV 就能出结论、出图表"成为基本功。

## 1. 概述

Python 数据分析阶段的目标是：**能用 NumPy/Pandas 读取并清洗 CSV，做分组统计、排序筛选、join 与透视表，用 Matplotlib/Plotly 画趋势图和柱状图，形成"清洗 → 统计 → 可视化 → 结论"的完整分析链路**。这一阶段把 ph08 的 numpy/pandas/matplotlib 入门升级为系统能力，同时把四个必会概念内化为习惯——**数据清洗通常比建模更耗时、DataFrame 操作要关注索引、分组统计是核心能力、图表要服务结论**——这是 Web 后端（ph10 数据接口）、AI/ML（ph15 特征工程）与车联网数据平台方向共同的地基。

| 核心维度 | 覆盖内容 |
|----------|---------|
| NumPy 数组与 Pandas 表格 | `ndarray`（形状/索引/广播/向量化）、`Series`/`DataFrame`（索引、列操作、`info()`/`describe()`） |
| 数据读取与清洗 | `read_csv`（`dtype`/`parse_dates`/`chunksize`）、缺失值、重复、异常值、类型转换 |
| 筛选排序与索引 | `loc`/`iloc`、布尔掩码、`sort_values`、`reset_index` |
| 分组统计 | `groupby` + `agg`/`transform` |
| 合并、透视与时间序列 | `merge`/`concat`/`join`、`pivot_table`、日期索引与 `resample` |
| 可视化与导出 | Matplotlib 折线/柱状/散点/分布、Plotly 交互图、`to_csv`/`to_excel` 报告 |

**范围边界**：本阶段承接 ph08 第三方库阶段，把 numpy/pandas/matplotlib 从"会用"推向"系统掌握"。不涉及 Web 后端深入（ph10：FastAPI 进阶、数据库 ORM、认证鉴权）、AI/ML（ph15：模型训练、特征工程、模型评估）、并发采集（ph14：大规模流式采集、异步流水线）；本阶段的"统计"以描述性统计（均值、方差、相关性）为主，推断统计与建模在 ph15 铺垫。

## 2. 来源与演变

数据科学三件套的源头是科学计算。**NumPy** 的前身是 1995 年 Jim Hugunin 为 C 数值计算写的 **Numeric**，2001 年 Travis Oliphant 与 Pearu Peterson 开发了更灵活的 **Numarray**，两套 API 并存割裂社区；2006 年二者合并为 **numpy 1.0**，其核心 `ndarray` 以"一块连续内存上的同类型数组"成为 Python 数值计算的地基，之后 scipy、pandas、scikit-learn 全部构建其上。

**pandas** 由 Wes McKinney 于 2008 年在 AQR 对冲基金为解决金融时间序列分析而创建：在 numpy 之上提供带标签行/列的 **Series 与 DataFrame**，把"数据清洗与分析"从几十行循环变成几行声明式代码，2011 年发布 1.0 前已成为数据科学事实标准。机器学习生态随之成型：**scikit-learn**（2007 年起源于 scikits.learn，2010 年正式发布）统一了"数据预处理 → 建模 → 评估"的 API，其输入约定就是 pandas 的 DataFrame；**Jupyter**（2014 年从 IPython Notebook 独立，IPython 本身始于 2001 年）提供"代码 + 结果 + 图表 + 叙述"合一的交互环境，让分析过程可复现、可分享。

可视化侧同样在演化：**matplotlib**（2003，John Hunter）以 MATLAB 风格 API 成为底层绘图标准；**seaborn**（2012）在其上提供统计图表（分布、箱线图、热力图）；**plotly**（2012）另辟蹊径提供浏览器交互图表。pandas 自身也在迭代：2020 年 1.0 稳定 API，2023 年 2.0 引入 PyArrow 后端与 **copy-on-write（写时复制）** 机制，并预告 3.0 将默认开启 CoW——"DataFrame 操作要关注索引与视图"这一课题正在被从根上缓解。

| 时间 | 里程碑 |
|------|-------|
| 1995 | Numeric 诞生（numpy 前身） |
| 2003 | matplotlib 发布（John Hunter） |
| 2006 | numpy 1.0：Numeric 与 Numarray 合并 |
| 2008 | pandas 发布（Wes McKinney，AQR） |
| 2010 | scikit-learn 正式发布——ML 生态成型 |
| 2014 | Jupyter Notebook 发布（IPython 演进） |
| 2020 | pandas 1.0（API 稳定） |
| 2023 | pandas 2.0（PyArrow 后端、copy-on-write 演进） |

## 3. 语法与参数

### 3.1 NumPy 数组基础（ndarray·形状·索引·广播·向量化）

```python
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
print(arr + 10, arr * 2)                # 向量化：整数组运算，无 for 循环
print(np.mean(arr), np.std(arr))        # 3.0 1.414...

m = np.arange(12).reshape(3, 4)         # 0..11 排成 3 行 4 列
print(m.shape, m.dtype)                 # (3, 4) int64
print(m[1, 2], m[:, 1])                 # 元素 / 整列切片

a = np.array([[1], [2], [3]])           # 形状 (3,1)
b = np.array([10, 20, 30])              # 形状 (3,)
print(a + b)                            # 广播成 (3,3)
```

要点：

- **向量化（vectorization）**：用数组表达式替代 Python 循环，性能差几十倍（原理见 4.1）；`np.arange`/`np.linspace`/`np.zeros`/`np.random.normal` 是常用构造器。
- **广播规则**：两个数组维度从右往左对齐，相等或其一为 1 才能扩展运算；`reshape(-1, 4)` 自动推断行数。
- **坑（axis 方向）**：`axis=0` 是"沿行方向"坍缩（对每列求均值），`axis=1` 是"沿列方向"——记法：axis 指"被压掉的那个轴"。

### 3.2 数据读取（pd.read_csv 等：dtype·parse_dates·chunksize）

```python
import pandas as pd

df = pd.read_csv("sales.csv")                     # 最常用：读 CSV
df2 = pd.read_csv("sales.csv",
                  dtype={"vehicle_id": str},      # 指定列类型（防 001 变 1）
                  parse_dates=["time"],           # 自动解析为 datetime
                  encoding="utf-8")               # 中文文件防乱码
print(df2.dtypes)                                 # 每列类型

for chunk in pd.read_csv("big.csv", chunksize=10000):   # 分块读取大文件
    print(chunk.shape)

df3 = pd.read_excel("report.xlsx")                # 读 Excel，需 openpyxl
```

要点：

- **读取后第一件事 `df.info()`/`df.dtypes`/`df.head()`**：看清列类型与空值再动手——"数据清洗通常比建模更耗时"的第一步就是摸清数据。
- `dtype` 显式指定类型：`"001"` 这类 ID 列默认会被读成 int 丢掉前导零；`parse_dates` 把时间字符串转成 `datetime64`，是时间序列分析的前提。
- **坑（编码）**：`read_csv` 默认 `utf-8`，中文 Excel 导出的 GBK/GB18030 文件要显式 `encoding="gbk"` 或 `"utf-8-sig"`，否则报 `UnicodeDecodeError`。

### 3.3 数据清洗（缺失值·重复·异常值·类型转换）

```python
import pandas as pd
import numpy as np

df = pd.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "speed": [80, np.nan, 95, 60, 72],          # np.nan 表示缺失
    "soc": [78.5, 76.0, 90.1, 88.4, 85.0],
})
print(df.isna().sum())                          # 每列缺失数量
print(df.dropna())                              # 删掉有缺失的行（默认 any）
print(df.fillna({"speed": df["speed"].median()}))   # 缺失填中位数
print(df.duplicated().sum())                    # 重复行数量
print(df.drop_duplicates())                     # 删重复行
print(df["speed"].astype(float))                # 类型转换
```

要点：

- 清洗四件事：**缺失值（NaN）、重复行、异常值、类型/格式**。缺失值处理三选：`dropna()` 删行（数据量大、缺失少）、`fillna(统计量)` 填充、保留 NaN 让统计函数自动跳过。
- **坑（NaN 传染）**：NaN 参与运算会传染——`df["speed"].sum()` 默认跳过 NaN，但把含 NaN 的列直接丢给 `np.mean` 会返回 NaN；`df["speed"].mean()` 会跳过。统计聚合前先确认缺失处理策略。
- 异常值：先用 `describe()`/直方图看分布，再 `clip(lower, upper)` 截断或布尔条件过滤（见示例 2）。
- 类型转换：`astype()`；"80 km/h" 这类脏字符串要先 `str.replace` 清理再转数值。

### 3.4 筛选排序与索引（loc/iloc·布尔掩码·sort_values）

```python
import pandas as pd

df = pd.DataFrame({
    "vehicle_id": ["V001", "V002", "V003", "V004"],
    "speed": [80, 95, 60, 72],
    "soc": [78.5, 76.0, 90.1, 88.4],
})
print(df.loc[1])                        # 按索引标签取行（此处行号即标签）
print(df.iloc[0])                       # 按位置取第 1 行
fast = df[df["speed"] > 70]             # 布尔掩码筛选
print(fast)
print(df.sort_values("speed", ascending=False))            # 单列降序
print(df.reset_index(drop=True))        # 恢复 0..n-1 连续索引
```

要点：

- **DataFrame 操作要关注索引**（roadmap 必会概念）：`iloc` 按位置、`loc` 按标签——筛选后两者指向可能不同；`reset_index(drop=True)` 是筛选/排序/分组后的常规收尾。
- 布尔掩码：`df["speed"] > 70` 生成布尔 Series，True 保留 False 丢弃；多条件用 `&`（与）、`|`（或）、`~`（非），**每个条件必须加括号**：`df[(df["speed"] > 70) & (df["soc"] < 80)]`。
- **坑（链式赋值 SettingWithCopyWarning）**：`df[df["speed"] > 70]["soc"] = 0` 触发警告且**可能不生效**——改数据一律 `df.loc[df["speed"] > 70, "soc"] = 0` 单步完成（原理见 4.3）。

### 3.5 分组统计（groupby·agg·transform）

```python
import pandas as pd

df = pd.DataFrame({
    "vehicle_id": ["V001", "V001", "V002", "V002"],
    "day": [1, 2, 1, 2],
    "speed": [80, 95, 60, 72],
    "soc": [78.5, 76.0, 90.1, 88.4],
})
print(df.groupby("vehicle_id")["speed"].mean())        # 每车平均速度
g = df.groupby("vehicle_id")[["speed", "soc"]].agg(["mean", "max"])
print(g)                                               # 多列多聚合
df["speed_z"] = df.groupby("vehicle_id")["speed"].transform(
    lambda x: (x - x.mean()) / x.std())                # transform 保持行数
```

要点：

- **分组统计是核心能力**（roadmap 必会概念）：`groupby("键")["指标"].聚合()` 三步走；常用聚合：`mean`/`sum`/`count`/`min`/`max`/`std`/`median`/`nunique`。
- `agg` 一次多个聚合（传列表或 dict）；`transform` 返回与原 DataFrame **等长的结果**（用于组内标准化、组内占比），不压缩行数。
- **坑（groupby 后索引）**：`groupby` 结果的分组键变成索引——后续操作常要 `reset_index()` 或 `as_index=False` 把它变回普通列；`groupby(...).size()` 统计组内行数（`count` 只统计非空值）。

### 3.6 合并与连接（merge·concat·join）

```python
import pandas as pd

left = pd.DataFrame({"vehicle_id": ["V001", "V002"],
                     "model": ["A", "B"]})
right = pd.DataFrame({"vehicle_id": ["V001", "V002", "V003"],
                      "speed": [80, 95, 60]})
print(pd.merge(left, right, on="vehicle_id", how="inner"))   # 交集
print(pd.merge(left, right, on="vehicle_id", how="left"))    # 左表全保留

df1 = pd.DataFrame({"speed": [80, 95]})
df2 = pd.DataFrame({"soc": [78.5, 76.0]})
print(pd.concat([df1, df2], axis=1))                   # 横向拼接：加列
df3 = pd.DataFrame({"speed": [60]})
print(pd.concat([df1, df3], axis=0, ignore_index=True))  # 纵向拼接：加行

right2 = right.set_index("vehicle_id")
print(left.join(right2, on="vehicle_id"))              # join：按索引连接
```

要点：

- 四种连接：`how="inner"`（默认，交集）/`"left"`/`"right"`/`"outer"`（并集）。join 是"关系型数据库思维"——**多表先想清楚主键（key）和保留方向**。
- `concat` 管"堆叠"：`axis=0` 加行、`axis=1` 加列；`merge` 按列连接，`join` 按索引连接。
- **坑（索引对齐陷阱）**：`merge` 按列匹配、不要求索引一致，但 `concat`/`join`/算术运算**按索引对齐**——两个 DataFrame 索引不同会错位拼出 NaN 行；拼接前统一 `reset_index(drop=True)`。

### 3.7 透视表与时间序列（pivot_table·resample·日期索引）

```python
import pandas as pd

df = pd.DataFrame({
    "vehicle_id": ["V001", "V001", "V002", "V002"],
    "day": ["周一", "周二", "周一", "周二"],
    "speed": [80, 95, 60, 72],
})
pt = pd.pivot_table(df, values="speed", index="day",
                    columns="vehicle_id", aggfunc="mean")
print(pt)                                            # 行=day，列=vehicle_id

ts = pd.DataFrame({
    "time": pd.to_datetime(["2024-06-01 08:00:00", "2024-06-01 08:01:00",
                            "2024-06-01 08:02:00", "2024-06-01 08:03:00"]),
    "speed": [80, 95, 60, 72],
})
ts = ts.set_index("time")                            # 时间列变成索引
print(ts.resample("2min").mean())                    # 重采样：2 分钟聚合
print(ts["speed"].rolling(2).mean())                 # 滚动均值
```

要点：

- 透视表把"长表"变"宽表"：`index`（行维）、`columns`（列维）、`values`（值）、`aggfunc`（聚合）；`groupby` 与 `pivot_table` 是同一能力的两种视角。
- 时间序列三步：`pd.to_datetime` 解析 → `set_index` 变成日期索引 → `resample`（降采样聚合）/`rolling`（滚动窗口）/时间切片。
- **坑（时区）**：`to_datetime` 解析带时区字符串（`+08:00`）得到带时区索引，与 naive 索引比较/拼接会报错——日志数据统一先转 UTC 或统一去时区再分析（呼应 ph06 时区纪律）。
- **坑（resample 规则）**：`"2min"`/`"1H"`/`"D"`/`"W"` 是偏移别名、大小写敏感（`h` 会报错）；`resample` 要求**日期索引**且已排序。

### 3.8 Matplotlib 与 Plotly 可视化（折线·柱状·散点·分布）

```python
import matplotlib
matplotlib.use("Agg")                       # 无显示环境也能 savefig
import matplotlib.pyplot as plt
import numpy as np

x = np.array([1, 2, 3, 4, 5])
y = np.array([80, 95, 60, 72, 88])

fig, axes = plt.subplots(2, 2, figsize=(10, 7))     # 2x2 子图
axes[0, 0].plot(x, y, marker="o")                    # 折线：趋势
axes[0, 0].set_title("Trend")
axes[0, 1].bar(x, y)                                 # 柱状：对比
axes[0, 1].set_title("Compare")
axes[1, 0].scatter(x, y)                             # 散点：关联
axes[1, 0].set_title("Relation")
axes[1, 1].hist(np.random.normal(70, 10, 500), bins=20)   # 分布
axes[1, 1].set_title("Distribution")
plt.tight_layout()
plt.savefig("charts.png", dpi=150)
```

要点：

- 四种基础图各回答一个问题：**折线看趋势、柱状看对比、散点看关联、直方图看分布**——先想清楚"这张图服务什么结论"再选图型（roadmap 必会概念"图表要服务结论"）。
- 脚本画图**必须 `savefig()`**，`plt.show()` 在无显示环境会报错或挂起；`figsize`/`dpi`/`tight_layout` 控制出图质量。
- Plotly 交互图：`pip install plotly`，`fig = px.line(df, x="time", y="speed")` 后 `fig.write_html("trend.html")` 生成可缩放、可悬停的网页图表，适合汇报与 Dashboard。

### 3.9 数据导出与报告

```python
import pandas as pd

df = pd.DataFrame({"vehicle_id": ["V001", "V002"], "speed": [80, 95]})
df.to_csv("out.csv", index=False, encoding="utf-8-sig")   # Excel 中文不乱码
df.to_excel("out.xlsx", index=False)                      # 需 openpyxl
df.to_json("out.json", orient="records", force_ascii=False)
print(df.to_markdown())                                   # 需 tabulate，输出表格文本
```

要点：

- **`index=False` 几乎必写**：不写会多一列行号（0,1,2...）污染数据；`utf-8-sig` 让 Excel 打开中文不乱码（承接 ph06 习惯）。
- 报告 = 表格 + 图表 + 结论：pandas 管表格、matplotlib 管图，最后用 f-string/`to_markdown()` 拼"结论 + 数字 + 图引用"的 Markdown 报告（见示例 5）。
- **坑（重名覆盖）**：`to_csv`/`savefig` 静默覆盖同名文件——报告脚本的文件名带日期或参数，防误覆盖历史结果。

## 4. 底层原理

### 4.1 NumPy 的连续内存与向量化（C 循环 vs Python 循环）

numpy 的 **ndarray 是 C 语言实现的**：数据存放在一块**连续的同类型内存**里，元素是裸 C 数值而非 Python 对象。Python 循环慢的本质：每个元素都是 PyObject（对象头 + 引用计数 + 类型分派），解释器逐条执行字节码。向量化运算（如 `arr + 10`）把整个表达式**下沉为一层 C 循环**：一次遍历连续内存、零解释器开销，现代 numpy 还会用 **SIMD** 指令一次处理多个元素——这就是"差几十倍"的来源。**广播（broadcasting）**依赖 **strides（步长）** 机制：形状不同的数组通过扩展步长描述"逻辑形状"参与运算，不复制数据、不新建数组，几乎零成本；代价是广播结果仍是视图语义，写回时要留意（呼应 4.3 的视图问题）。

### 4.2 DataFrame 的列式存储与索引（RangeIndex/多级索引）

pandas 的 DataFrame 本质是"**列优先**"结构：每一列是一个独立的 numpy 数组（即 Series），多列共享同一个 **Index**（行标签对象）。默认的 **RangeIndex** 是 0..n-1 的惰性整数序列（不实际存储每个标签）；一旦筛选、排序、分组，索引会变成稀疏、无序或**多级索引（MultiIndex）**——`groupby` 结果的分组键就是典型的多级索引。这就是"DataFrame 操作要关注索引"的底层原因：索引是定位数据的**寻址系统**，`loc` 按标签寻址、`iloc` 按位置寻址，两者在索引被改动后不再等价。列式存储带来两个收益：**按列聚合只遍历相关列**（`mean`/`sum` 快），且同列类型统一、压缩友好；代价是**按行操作慢**（`df.apply(axis=1)` 逐行是 Python 循环），能用列式向量化就别逐行。

### 4.3 复制 vs 视图（copy-on-write 演进，Pandas 3.0 预告）

numpy 的切片返回**共享内存的视图**——修改视图会改动原数组。pandas 为安全起见多数操作返回**副本**，但 `df["col"]`、布尔掩码取出的子集可能仍是视图：**链式赋值** `df[df["a"] > 1]["b"] = 2` 先取视图再赋值，第一次取值可能已返回副本，赋值落空并触发 SettingWithCopyWarning。规则：**要修改就用 `df.loc[条件, 列] = 值` 单步完成；要独立数据就显式 `.copy()`**。pandas 2.x 引入 **copy-on-write（写时复制）** 机制（`pd.options.mode.copy_on_write = True`）：对象间共享底层数据，仅在**任一修改发生时**才真正复制——既杜绝链式赋值的悬空修改，又省内存；pandas 3.0 起 CoW 成为默认，链式赋值将彻底失效（不再有"侥幸生效"的情况），从现在起养成 `loc` 单步赋值的习惯即是面向未来。

### 4.4 分块读取与内存上限（chunksize·dtype 压缩）

`read_csv` 默认把整个文件读进内存，GB 级文件会直接 OOM。**`chunksize=N`** 让 `read_csv` 返回一个迭代器，每次只读 N 行——适合"逐块聚合、最后合并"的流水线（示例：`sum += chunk["speed"].sum()` 按块累加）。内存还能靠 **dtype 压缩**：pandas 默认 int64/float64 每元素 8 字节，用 `dtype` 指定 `int8`/`float32` 或 category 类型可降数倍内存；`usecols` 只读需要的列；`df.memory_usage(deep=True)` 可精确估算。pandas 的定位是**"单机内存装得下"的数据**——超过内存的数亿行数据交给 polars（惰性求值 + 多核）或数据库（ph10 SQLAlchemy 对接），不必强求 pandas 硬扛。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 销售日报/月报统计 | `read_csv` + 清洗 + `groupby` + `pivot_table` + 柱状图 |
| 车辆行驶速度分析 | 时间序列 + 异常值过滤 + 折线趋势图 + 滚动均值 |
| 电池健康监控 | SOC/电压关联 + 缺失值插值 + 散点图 + 相关系数 |
| CAN 报文统计 | 日志字段解析 + 按 ID 分组 + 频次分布直方图 |
| 多表数据合并 | `merge`/`concat`/`join` 关联车辆档案与遥测记录 |
| 生成分析报表 | 图表 + `to_excel`/`to_markdown` 汇总导出 |

**不适合此阶段的事项**：

- Web 后端深入（FastAPI 进阶、SQLAlchemy ORM、认证鉴权、中间件、部署）：ph10 Web 后端阶段
- 机器学习建模（模型训练、特征工程、模型评估、调参）：ph15 AI/ML 阶段（本阶段只做描述性统计）
- 大规模流式处理（Kafka、Spark、Flink、实时数仓）：后续大数据阶段（pandas 只处理内存装得下的数据）

## 6. 代码示例

### 示例 1：销售数据分析（读取 + 清洗 + 分组统计 + 柱状图）

呼应"销售数据分析"练习：自造一份门店销售 CSV，走"读取 → 清洗 → 分组统计 → 柱状图"的完整链路。

```python
# 依赖：pip install pandas matplotlib
import matplotlib
matplotlib.use("Agg")                       # 无显示环境也能 savefig
import matplotlib.pyplot as plt
import pandas as pd

# 1. 构造模拟销售数据（真实场景换成 pd.read_csv("sales.csv")）
sales = pd.DataFrame({
    "store": ["东区店"] * 4 + ["西区店"] * 4 + ["南区店"] * 4,
    "month": ["2024-01", "2024-02"] * 6,
    "amount": [120, 135, None, 110, 88, 92, 150, 145, 80, 95, 88, 105],
})

# 2. 清洗：缺失值填中位数 + 去重
sales["amount"] = sales["amount"].fillna(sales["amount"].median())
sales = sales.drop_duplicates()
# 3. 分组统计：各门店月均销售额
avg = sales.groupby("store")["amount"].mean().sort_values(ascending=False)
print(avg.round(1))
# 4. 透视表：门店 × 月份
pt = sales.pivot_table(values="amount", index="store",
                       columns="month", aggfunc="mean")
print(pt.round(1))
# 5. 柱状图：服务"哪家门店卖得好"的结论
ax = avg.plot.bar(figsize=(6, 4), color="steelblue")
ax.set_title("门店月均销售额对比")
ax.set_ylabel("金额（万元）")
plt.tight_layout()
plt.savefig("sales_summary.png", dpi=150)
print("已保存 sales_summary.png")
```

### 示例 2：车辆速度分析（时间序列 + 过滤异常值 + 趋势图）

呼应"车辆速度分析"练习：30 秒一条遥测记录，注入 GPS 跳变异常值，过滤后看趋势。

```python
# 依赖：pip install pandas matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# 1. 构造模拟遥测数据（含异常值：GPS 跳变）
rng = np.random.default_rng(42)
n = 200
df = pd.DataFrame({
    "time": pd.date_range("2024-06-01 08:00:00", periods=n, freq="30s"),
    "speed": rng.normal(60, 15, n).clip(0, 120),
})
df.loc[50, "speed"] = 320                # 注入异常值（物理上不可能的速度）
# 2. 时间索引 + 过滤异常值（速度物理上限 200 km/h）
df = df.set_index("time")
valid = df[(df["speed"] >= 0) & (df["speed"] <= 200)]
print("原始行数:", len(df), "过滤后:", len(valid), "剔除:", len(df) - len(valid))
# 3. 重采样到 5 分钟均值 + 滚动均值，画趋势图
trend = valid.resample("5min")["speed"].mean()
smooth = valid["speed"].rolling(10).mean()
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(valid.index, valid["speed"], alpha=0.3, label="原始")
ax.plot(trend.index, trend, marker="o", label="5min 均值")
ax.plot(smooth.index, smooth, label="滚动均值")
ax.set_title("车辆速度趋势")
ax.set_ylabel("km/h")
ax.legend()
plt.tight_layout()
plt.savefig("speed_trend.png", dpi=150)
print("已保存 speed_trend.png；平均速度:", round(valid["speed"].mean(), 1), "km/h")
```

### 示例 3：电池数据分析（SOC/电压关联 + 缺失值处理 + 散点图）

呼应"电池数据分析"练习：SOC 每下降 1% 记录一次电压，缺失值用线性插值填充，画关联散点图。

```python
# 依赖：pip install pandas matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# 1. 构造模拟电池数据（电压随 SOC 近似线性，注入缺失值）
soc = np.arange(0, 101, 1)
rng = np.random.default_rng(7)
voltage = 3.0 + soc * 0.004 + rng.normal(0, 0.01, len(soc))
voltage[[5, 20, 45]] = np.nan
df = pd.DataFrame({"soc": soc, "voltage": voltage})
# 2. 缺失值处理：统计 + 线性插值（比填均值更符合物理规律）
df["voltage"] = df["voltage"].interpolate()
print("插值后缺失:", df["voltage"].isna().sum())
# 3. 关联分析：SOC 与电压的相关系数
corr = df["soc"].corr(df["voltage"])
print("SOC 与电压相关系数:", round(corr, 4))
# 4. 散点图 + 拟合线：服务"SOC 与电压强相关"的结论
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(df["soc"], df["voltage"], s=12, alpha=0.6)
fit = np.polyfit(df["soc"], df["voltage"], 1)
ax.plot(df["soc"], np.polyval(fit, df["soc"]), "r-",
        label=f"拟合线 y={fit[0]:.4f}x+{fit[1]:.3f}")
ax.set_title("电池 SOC-电压 关联")
ax.set_xlabel("SOC (%)")
ax.set_ylabel("电压 (V)")
ax.legend()
plt.tight_layout()
plt.savefig("battery_soc_voltage.png", dpi=150)
print("已保存 battery_soc_voltage.png")
```

### 示例 4：CAN 日志统计（字段解析 + 按 ID 分组 + 频次分布）

呼应"CAN 日志统计"练习：解析 CAN 报文日志文本，按报文 ID 分组统计频次并画分布图。

```python
# 依赖：pip install pandas matplotlib
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# 1. 模拟 CAN 日志（真实场景换成 open("can.log").readlines()）
log_text = """\
2024-06-01 08:00:00.123 CAN 0x123 DLC 8 78 5A 00 10 00 00 00 00
2024-06-01 08:00:00.125 CAN 0x456 DLC 8 00 00 50 00 00 00 00 00
2024-06-01 08:00:00.140 CAN 0x789 DLC 8 01 02 03 04 05 06 07 08
2024-06-01 08:00:00.155 CAN 0x123 DLC 8 80 5C 00 10 00 00 00 00
"""
pattern = re.compile(r"(\d{4}-\d{2}-\d{2} [\d:.]+) CAN (0x[0-9A-Fa-f]+) DLC \d (.*)")
rows = []
for line in log_text.strip().splitlines():
    m = pattern.match(line)
    ts, can_id, data = m.group(1), m.group(2), m.group(3)
    rows.append({"time": ts, "can_id": can_id,
                 "byte0": int(data.split()[0], 16)})    # 提取首字节（十六进制）
df = pd.DataFrame(rows)
# 2. 按报文 ID 分组统计频次
freq = df.groupby("can_id").size().sort_values(ascending=False)
print("各 CAN ID 报文频次:")
print(freq)
print("总报文数:", len(df), " 不同 ID 数:", df["can_id"].nunique())
# 3. 频次分布柱状图：服务"哪些报文最频繁"的结论
freq.plot.bar(figsize=(6, 4), color="seagreen")
plt.title("CAN 报文频次分布")
plt.ylabel("条数")
plt.tight_layout()
plt.savefig("can_freq.png", dpi=150)
print("已保存 can_freq.png")
```

### 示例 5：数据合并与透视（多表 join + pivot_table + 汇总报告导出）

呼应练习综合与"推荐项目：电池健康分析报表"：合并车辆档案与遥测记录，透视汇总后导出 Excel + Markdown 报告。

```python
# 依赖：pip install pandas openpyxl tabulate
import pandas as pd

# 1. 两张表：车辆档案 + 遥测记录
fleet = pd.DataFrame({
    "vehicle_id": ["V001", "V002", "V003"],
    "model": ["EV-A", "EV-B", "EV-A"],
})
telemetry = pd.DataFrame({
    "vehicle_id": ["V001", "V001", "V002", "V003", "V003", "V003"],
    "day": ["周一", "周二", "周一", "周一", "周二", "周三"],
    "mileage": [120.5, 135.0, 98.0, 150.2, 145.8, 88.4],
    "energy": [18.2, 20.1, 15.5, 22.0, 21.5, 13.8],
})

# 2. 多表 join：按 vehicle_id 关联（left 保留全部遥测记录）
merged = telemetry.merge(fleet, on="vehicle_id", how="left")
# 3. 分组统计：每车总里程、总能耗、百公里能耗
report = merged.groupby("vehicle_id").agg(
    total_mileage=("mileage", "sum"),
    total_energy=("energy", "sum"),
    trips=("day", "count"),
)
report["energy_per_100km"] = report["total_energy"] / report["total_mileage"] * 100
print(report.round(2))
# 4. 透视表：车辆 × 日期的里程
pt = pd.pivot_table(merged, values="mileage", index="day",
                    columns="vehicle_id", aggfunc="sum", fill_value=0)
print(pt)
# 5. 导出报告：Excel 多 Sheet + Markdown 摘要
with pd.ExcelWriter("fleet_report.xlsx") as writer:
    report.to_excel(writer, sheet_name="汇总")
    pt.to_excel(writer, sheet_name="里程透视")
print("已导出 fleet_report.xlsx")
print("汇总报告（Markdown）:")
print(report.round(2).to_markdown())
```

## 7. 总结

### 关键要点

1. **数据清洗通常比建模更耗时**：真实项目 60-80% 的时间在读取、去重、补缺、修格式——先 `info()`/`describe()` 摸清数据再动手；**缺失值处理要显式决策**（NaN 会传染运算，`dropna`/`fillna`/`interpolate` 三选一）（roadmap 必会概念）
2. **DataFrame 操作要关注索引**：区分 `loc`/`iloc`，筛选/排序/groupby 后 `reset_index(drop=True)`，改数据用 `df.loc[条件, 列] = 值` 单步完成（roadmap 必会概念）
3. **分组统计是核心能力**：`groupby("键")["指标"].agg([...])` 三步走，`transform` 保持行数做组内标准化（roadmap 必会概念）
4. **图表要服务结论**：折线看趋势、柱状看对比、散点看关联、直方图看分布——先想清楚图回答什么问题再画（roadmap 必会概念）
5. **合并前先想主键与连接方向**：`merge` 的 `how` 四选一，`concat`/`join`/算术按索引对齐——索引不一致会错位出 NaN
6. **时间序列先转日期索引**：`to_datetime` + `set_index` + `resample`/`rolling`；时区统一（UTC 或去时区）
7. **脚本画图必须 `savefig()`、导出 `index=False` 几乎必写**：`matplotlib.use("Agg")` 防无显示环境报错，`utf-8-sig` 防 Excel 中文乱码，文件名带日期防覆盖
8. **向量化优先于逐行循环**：`apply(axis=1)`/for 循环慢几十倍，能用数组表达式就绝不逐行（原理见 4.1）

### 跨语言对比：数据分析栈

| 维度 | Python（pandas） | R（tidyverse） | Julia | SQL | Excel |
|------|------------------|----------------|-------|-----|-------|
| 表格结构 | DataFrame | tibble / data.frame | DataFrame（DataFrames.jl） | 表（table） | 工作表 |
| 读取数据 | `pd.read_csv()` | `read_csv()` | `CSV.read()` | `LOAD DATA` / `SELECT` | 打开即读 |
| 缺失值处理 | `dropna`/`fillna`/`interpolate` | `drop_na`/`replace_na` | `dropmissing`/`coalesce` | `WHERE x IS NOT NULL`/`COALESCE` | 查找替换、筛选 |
| 分组统计 | `groupby` + `agg` | `group_by` + `summarise` | `groupby` + `combine` | `GROUP BY` + 聚合函数 | 数据透视表 |
| 时间序列 | `resample`/`rolling` | `tsibble`/`fable` | TimeSeries.jl | `DATE_TRUNC`/窗口函数 | 趋势线/切片器 |
| 可视化 | matplotlib / plotly | ggplot2 | Plots.jl | （配合 BI 工具） | 内置图表 |

### 阶段验收标准

- 能读取并清洗 CSV：`read_csv` + `dtype`/`parse_dates`/编码参数，缺失值、重复、异常值、类型转换四步清洗（对应 roadmap"能读取并清洗 CSV"）
- 能做分组统计：`groupby` + `agg`/`transform`，并解释结果含义（对应 roadmap"能做分组统计"）
- 能画趋势图和柱状图：`savefig` 输出 PNG，图能服务结论（对应 roadmap"能画趋势图和柱状图"）
- 能做筛选排序与 join（布尔掩码、`sort_values`、`merge`），并解释四个必会概念：清洗比建模耗时、关注索引、分组统计是核心、图表服务结论

### 进入下一阶段前

确保能完成以下练习：

- 销售数据分析：自造或下载一份 CSV，做缺失值处理 + 门店/品类分组统计 + 柱状图（提示：先 `info()` 看类型；`groupby` 后 `reset_index()` 恢复普通列）
- 车辆速度分析：时间序列 + 过滤异常值（>200 km/h 的 GPS 跳变）+ 折线趋势图（提示：`set_index` 后 `resample("5min")` 看趋势更清晰）
- 电池数据分析：SOC 与电压散点图 + 相关系数 + 缺失值处理（提示：`interpolate()` 比填均值更符合物理规律）
- CAN 日志统计：解析日志字段 → 按 CAN ID 分组 → 频次分布图（提示：先写正则验证 5 行样本；`size()` 统计组内行数）
- 数据合并与透视：两张表 `merge` 后 `pivot_table` 汇总，导出 Excel 与 Markdown 报告（提示：`how="left"` 保留主表；`index=False` 防多余行号列）

### 推荐项目

- **车辆遥测分析脚本**：读取遥测 CSV → 清洗（缺失/异常值）→ 按车辆分组统计（均速、里程、能耗）→ 折线趋势 + 柱状对比图 → 导出 Excel 报表（呼应 roadmap"车辆遥测分析脚本"）
- **电池健康分析报表**：SOC/电压/温度数据分析 → 缺失值插值 → 关联散点图与相关性 → 生成 Markdown/Excel 健康报表（呼应 roadmap"电池健康分析报表"）

### 下一阶段

**Web 后端开发阶段**（ph10-web-backend，文档规划中）—— FastAPI 深入、认证鉴权、SQLAlchemy、中间件与部署准备。
