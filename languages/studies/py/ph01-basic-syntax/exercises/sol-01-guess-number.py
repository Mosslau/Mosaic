# exercises/sol-01-guess-number.py —— 猜数字游戏：随机 1~100，循环猜直到命中
# 验证环境：Python 3.13.12（macOS）
# 运行：python3 sol-01-guess-number.py   （交互输入猜测）
# 验证状态：已验证

import random

secret = random.randint(1, 100)
attempts = 0

print("猜一个 1-100 之间的数字！")

while True:
    guess = int(input("你的猜测: "))
    attempts += 1

    if guess < secret:
        print("太小了！")
    elif guess > secret:
        print("太大了！")
    else:
        print(f"猜对了！共尝试 {attempts} 次。")
        break
