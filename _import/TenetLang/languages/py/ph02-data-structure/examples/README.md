# ph02 数据结构 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：Python 3.13.12（macOS arm64），仅用标准库。

| 文件 | 说明 | 运行命令 |
|------|------|----------|
| ex01-scores.py | 用 list 管理成绩：平均分、排序取前三、及格人数、加分 | `python3 ex01-scores.py` |
| ex02-contacts.py | 用嵌套 dict 做通讯录：添加、get 安全查询、遍历 | `python3 ex02-contacts.py` |
| ex03-cart.py | 用 list of dict 表达购物车：总价、按单价排序 | `python3 ex03-cart.py` |
| ex04-word-freq.py | 用 dict 统计词频、按频率降序、set 差集去停用词 | `python3 ex04-word-freq.py` |
| ex05-group-input.py | 读标准输入「姓名 分数」并按分数段分组到 dict of list | `printf 'Alice 85\nBob 92\n' \| python3 ex05-group-input.py` |

全部已在本环境用 `python3` 实际运行验证通过（ex05 需要输入，验证时通过管道喂入）。
