# project/grade_tool.py —— 成绩等级判断工具（单条 + 批处理）
# 验证环境：Python 3.13.12（macOS）
# 运行：
#   单条模式：python3 grade_tool.py
#   批处理模式：echo "95 82 67" | python3 grade_tool.py --batch
# 验证状态：已验证

import sys


def get_grade(score):
    """根据分数返回等级 A/B/C/D/F。"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'


def single_mode():
    """单条查询模式：循环读入分数，输入 q 退出。"""
    print("成绩等级判断工具（单条模式），输入 q 退出")
    while True:
        raw = input("请输入分数 (0-100): ").strip()
        if raw.lower() == 'q':
            print("再见！")
            break
        try:
            score = int(raw)
        except ValueError:
            print("错误：请输入整数")
            continue
        if not 0 <= score <= 100:
            print("错误：分数必须在 0~100 之间")
            continue
        print(f"分数 {score} → 等级 {get_grade(score)}")


def batch_mode():
    """批处理模式：从 stdin 读入全部分数，输出等级并统计。"""
    text = sys.stdin.read()
    tokens = text.split()
    scores = []
    for t in tokens:
        try:
            s = int(t)
        except ValueError:
            print(f"跳过非法输入: {t}")
            continue
        if not 0 <= s <= 100:
            print(f"跳过超范围分数: {t}")
            continue
        scores.append(s)

    if not scores:
        print("没有有效成绩")
        return

    print("--- 成绩等级 ---")
    for i, s in enumerate(scores, 1):
        print(f"学生 {i}: 分数={s}, 等级={get_grade(s)}")

    total = len(scores)
    avg = sum(scores) / total
    counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for s in scores:
        counts[get_grade(s)] += 1

    print("--- 统计 ---")
    print(f"总人数: {total}")
    print(f"平均分: {avg:.2f}")
    print(f"最高分: {max(scores)}, 最低分: {min(scores)}")
    for g in ['A', 'B', 'C', 'D', 'F']:
        print(f"等级 {g}: {counts[g]} 人")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        batch_mode()
    else:
        single_mode()
