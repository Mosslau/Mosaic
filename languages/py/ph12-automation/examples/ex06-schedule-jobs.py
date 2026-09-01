#!/usr/bin/env python3
# examples/ex06-schedule-jobs.py —— 定时任务：schedule 注册任务 + run_pending 调度循环
# 验证环境：Python 3.13.9，schedule 1.2.2（pip install schedule；本机全局 python3 未装，
#           本示例在临时 venv（/tmp/ph12-venv）中安装 schedule 1.2.2 后实测通过）
# 运行：/tmp/ph12-venv/bin/python ex06-schedule-jobs.py（或用装好 schedule 的解释器运行）
# 说明：对应主文档 3.7。schedule 是「进程内轮询」式调度：注册任务 → 主循环反复
#       run_pending() 检查到期任务 → sleep 到下一个到期时刻。演示每秒任务 + 每日 08:00 任务。
import time

import schedule


def job(name: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] 执行任务:", name)


def heartbeat(executed: list[str]) -> None:
    """心跳任务：记录执行次数（真实脚本里只管干活，计数只为让演示能终止）。"""
    executed.append("heartbeat")
    job("上报心跳")


def main() -> None:
    executed: list[str] = []
    schedule.every(1).seconds.do(heartbeat, executed)  # 每秒一次（演示用）
    daily = schedule.every().day.at("08:00").do(job, "生成日报")  # 每天 08:00（已过则明天）
    print("注册任务数:", len(schedule.get_jobs()))
    print("日报任务下次运行:", daily.next_run.strftime("%Y-%m-%d %H:%M:%S"))
    print("--- 调度循环开始（心跳任务触发 3 次后结束）---")
    rounds = 0
    while len(executed) < 3 and rounds < 10:  # 真实脚本是永不退出的 while True
        schedule.run_pending()  # 检查并执行到期任务
        time.sleep(0.5)        # 睡到接近下一个到期时刻，别空转烧 CPU
        rounds += 1
    print("--- 调度循环结束（心跳已执行", len(executed), "次）---")
    schedule.clear()
    print("清空任务后注册数:", len(schedule.get_jobs()))


if __name__ == "__main__":
    main()
