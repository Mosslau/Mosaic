# examples/ex02-grade-judge.py —— 成绩等级判定：分数 → A/B/C/D/F
# 验证环境：Python 3.13.12（macOS）
# 运行：python3 ex02-grade-judge.py
# 验证状态：已验证


def get_grade(score):
    """根据分数返回等级。"""
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


scores = [95, 82, 67, 54, 78, 91]
for i, s in enumerate(scores):
    print(f"学生 {i+1}: 分数={s}, 等级={get_grade(s)}")
