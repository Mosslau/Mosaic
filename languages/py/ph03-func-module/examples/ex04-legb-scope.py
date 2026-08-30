# examples/ex04-legb-scope.py —— LEGB 作用域完整追踪
# 验证环境：Python 3.13.12
# 运行：python3 ex04-legb-scope.py
# 已验证：本环境运行输出与注释中期望值一致

name = "Global"              # G: Global
PI = 3.14159                 # G: Global

def outer(prefix):
    name = "Outer"           # E: Enclosing
    multiplier = 10          # E: Enclosing

    def inner(value):
        name = "Inner"       # L: Local
        return f"[{name}] {prefix} {value}*{multiplier}={value * multiplier}"

    print(f"[{name}] {inner(7)}")   # multiplier → Enclosing
    print(f"[{name}] PI={PI}")      # PI → Global; print → Built-in

print(f"[{name}] before outer")
outer("val:")
print(f"[{name}] after outer")
