#!/usr/bin/env python3
"""
OceanVerse 车辆数据模拟器
模拟 10,000 辆智能电动车，每 10 秒上报一次状态数据
注入 0.5% 异常数据（故障码、电池高温）
"""

import argparse
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests


class VehicleSimulator:
    """车辆数据模拟器"""

    # 故障码池
    FAULT_CODES = [
        "BMS_001", "BMS_002", "BMS_003",  # 电池管理系统
        "MOT_001", "MOT_002",              # 电机
        "CTL_001", "CTL_002",              # 控制器
        "GPS_001",                          # GPS
        "CHG_001", "CHG_002",              # 充电
    ]

    # 城市坐标池 (lat, lng)
    CITIES = [
        (31.23, 121.47),   # 上海
        (39.90, 116.40),   # 北京
        (22.54, 114.05),   # 深圳
        (23.13, 113.26),   # 广州
        (30.57, 104.07),   # 成都
        (30.27, 120.15),   # 杭州
    ]

    def __init__(self, vehicle_count: int = 10000, anomaly_rate: float = 0.005):
        self.vehicle_count = vehicle_count
        self.anomaly_rate = anomaly_rate
        self.vehicles = self._init_vehicles()

    def _init_vehicles(self) -> List[Dict]:
        """初始化车辆状态"""
        vehicles = []
        for i in range(self.vehicle_count):
            city = random.choice(self.CITIES)
            vehicles.append({
                "vehicle_id": f"V{i:06d}",
                "lat": city[0] + random.uniform(-0.1, 0.1),
                "lng": city[1] + random.uniform(-0.1, 0.1),
                "speed": 0.0,
                "battery_voltage": 60.0 + random.uniform(-2, 2),
                "battery_current": 0.0,
                "battery_temp": 25.0 + random.uniform(-5, 5),
                "soc": random.randint(20, 100),
                "soh": random.randint(85, 100),
                "fault_code": None,
                "is_charging": random.random() < 0.15,  # 15% 在充电
            })
        return vehicles

    def generate_event(self, vehicle: Dict) -> Dict:
        """生成单个车辆事件"""
        now = int(time.time())

        # 随机事件类型
        rand = random.random()
        if rand < 0.6:
            event_type = "status"
        elif rand < 0.75:
            event_type = "trip"
        elif rand < 0.9:
            event_type = "battery"
        else:
            event_type = "fault"

        # 更新车辆状态
        if event_type == "trip":
            vehicle["speed"] = random.uniform(15, 45)
            vehicle["lat"] += random.uniform(-0.01, 0.01)
            vehicle["lng"] += random.uniform(-0.01, 0.01)
            vehicle["soc"] = max(0, vehicle["soc"] - random.uniform(0.1, 0.5))
            vehicle["battery_current"] = -random.uniform(5, 15)
        elif event_type == "battery":
            if vehicle["is_charging"]:
                vehicle["battery_current"] = random.uniform(5, 20)
                vehicle["soc"] = min(100, vehicle["soc"] + random.uniform(0.5, 2))
            else:
                vehicle["battery_current"] = -random.uniform(0, 5)
            vehicle["battery_temp"] += random.uniform(-0.5, 0.5)
            vehicle["battery_voltage"] += random.uniform(-0.2, 0.2)
        elif event_type == "status":
            vehicle["speed"] = 0.0
            vehicle["battery_current"] = 0.0

        # 异常注入 (0.5%)
        is_anomaly = random.random() < self.anomaly_rate
        if is_anomaly:
            if random.random() < 0.5:
                # 故障码
                vehicle["fault_code"] = random.choice(self.FAULT_CODES)
                event_type = "fault"
            else:
                # 电池高温
                vehicle["battery_temp"] = random.uniform(55, 75)

        # 异常恢复 (5% 概率清除故障码)
        elif vehicle["fault_code"] and random.random() < 0.05:
            vehicle["fault_code"] = None

        return {
            "vehicle_id": vehicle["vehicle_id"],
            "timestamp": now,
            "event_type": event_type,
            "gps": {
                "lat": round(vehicle["lat"], 6),
                "lng": round(vehicle["lng"], 6),
                "speed": round(vehicle["speed"], 2),
            },
            "battery": {
                "voltage": round(vehicle["battery_voltage"], 2),
                "current": round(vehicle["battery_current"], 2),
                "temp": round(vehicle["battery_temp"], 2),
                "soc": vehicle["soc"],
                "soh": vehicle["soh"],
            },
            "fault_code": vehicle["fault_code"],
        }

    def run(self, gateway_url: str, interval: int = 10, batch_size: int = 100):
        """运行模拟器"""
        print(f"🚗 启动车辆数据模拟器: {self.vehicle_count} 辆车, 间隔 {interval}s")
        print(f"📡 上报地址: {gateway_url}")
        print(f"⚠️  异常率: {self.anomaly_rate * 100}%")
        print("-" * 50)

        session = requests.Session()
        event_count = 0
        anomaly_count = 0

        try:
            while True:
                start_time = time.time()
                events = []

                # 生成一批事件
                for vehicle in random.sample(self.vehicles, min(batch_size, self.vehicle_count)):
                    event = self.generate_event(vehicle)
                    events.append(event)
                    event_count += 1
                    if event.get("fault_code") or event["battery"]["temp"] > 55:
                        anomaly_count += 1

                # 上报
                try:
                    response = session.post(
                        gateway_url,
                        json={"events": events, "source": "simulator", "timestamp": int(time.time())},
                        timeout=5,
                    )
                    if response.status_code != 200:
                        print(f"⚠️  上报失败: HTTP {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"⚠️  连接失败: {e}")

                # 统计
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"已发送 {event_count} 事件 | 异常 {anomaly_count} | "
                    f"耗时 {elapsed:.2f}s | 休眠 {sleep_time:.2f}s"
                )

                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n🛑 模拟器停止")


def main():
    parser = argparse.ArgumentParser(description="OceanVerse 车辆数据模拟器")
    parser.add_argument("--vehicles", type=int, default=10000, help="车辆数量 (默认: 10000)")
    parser.add_argument("--interval", type=int, default=10, help="上报间隔秒数 (默认: 10)")
    parser.add_argument("--gateway", type=str, default="http://localhost:8080/api/v1/report", help="网关地址")
    parser.add_argument("--anomaly-rate", type=float, default=0.005, help="异常率 (默认: 0.005)")
    parser.add_argument("--batch-size", type=int, default=100, help="每批上报车辆数 (默认: 100)")

    args = parser.parse_args()

    simulator = VehicleSimulator(vehicle_count=args.vehicles, anomaly_rate=args.anomaly_rate)
    simulator.run(gateway_url=args.gateway, interval=args.interval, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
