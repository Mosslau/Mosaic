# examples/ex02-args-kwargs.py —— *args/**kwargs 打包与拆包综合演示
# 验证环境：Python 3.13.12
# 运行：python3 ex02-args-kwargs.py
# 已验证：本环境运行输出与注释中期望值一致

def create_report(title, *sections, **options):
    """生成报告：title 必传，*sections 打包位置参数，**options 打包关键字参数。"""
    lines = [f"=== {title} ===", ""]
    for i, sec in enumerate(sections, 1):
        lines.append(f"  {i}. {sec}")
    for k, v in sorted(options.items()):
        lines.append(f"  [{k}] {v}")
    return "\n".join(lines)

# 打包调用
report = create_report(
    "2024 Q1", "Revenue up 12%", "New hires: 5",
    author="Alice", date="2024-04-01", confidential=True
)
print(report)
print()

# 拆包调用：*list → 位置参数，**dict → 关键字参数
headers = ["Monthly Report", "Overview"]
details = {"author": "Bob", "status": "draft"}
print(create_report(*headers, **details))
