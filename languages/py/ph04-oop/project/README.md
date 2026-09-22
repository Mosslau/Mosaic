# ph04 阶段项目：设备管理系统

## 需求

对应 Roadmap「ph04 面向对象 OOP 阶段」推荐项目第一个「设备管理系统」。用类组织设备与服务实体模型，核心教学点是**类层次 + 继承多态 + 简单数据持久化**：

- `Component` 基类（设备编号、名称、在线状态）→ `Sensor` / `Actuator` 子类差异化行为
- `Device` 组合一组组件，实现 `__len__` / `__getitem__` 容器协议
- `DeviceManager` 管理多台设备，支持批量上线、状态汇报、JSON 持久化

数据经 `to_dict` / `from_dict` 与 JSON 互转（`json.dump` / `json.load` 最简形态；`with` 与异常处理属于 ph05 文件操作与异常处理阶段，这里提前使用不展开）。

## 功能清单

- [ ] `add device <did> <名称>`：添加设备，编号重复报错
- [ ] `add sensor <did> <名称> <单位> <值>` / `add actuator <did> <名称> <最大输出>`：向设备添加组件
- [ ] `online`：全部设备的所有组件批量上线
- [ ] `control <did> <组件索引> <百分比>`：控制指定执行器输出（非执行器报错）
- [ ] `show`：汇报全部设备、组件状态与在线统计
- [ ] `save`：全部设备序列化为 `devices.json`
- [ ] `load`：从 `devices.json` 重建全部设备（`kind` 字段分发到对应子类）
- [ ] 未知命令、不存在的设备编号、越界组件索引均给出错误提示不崩溃

## 验收标准

- 交互命令流可完成「建设备 → 加传感器/执行器 → 上线 → 控制 → 查看 → 保存」，全程无异常退出
- 二次运行 `load` 后 `show` 恢复全部设备与组件**配置**（类型/编号/名称/单位/量程），与保存前一致
- 运行期状态（在线状态、执行器当前输出）不持久化——加载后默认 offline，重新 `online` 后恢复
- 对不存在的设备编号执行 `control` 输出 `错误: 设备不存在: ...`；对未知命令输出可用命令列表
- `devices.json` 中组件带 `kind` 字段（`sensor` / `actuator`），可直接阅读

## 扩展方向（可选）

- 给 `Sensor` 增加读数记录与阈值告警，锻炼 `__eq__` / `__lt__` 排序 —— 本阶段魔术方法
- 用 `pickle` 直接序列化对象，省去 `to_dict` / `from_dict` —— 但与版本绑定、不可读
- 把 JSON 读写升级为完整错误处理（`FileNotFoundError` / `json.JSONDecodeError`）—— 属于 ph05 文件操作与异常处理阶段
- 数据存到 SQLite —— 属于 ph11 数据库阶段

## 验证环境

Python 3.13.12，仅标准库（`json` / `os`）。运行（在 `project/` 目录下）：

```bash
# 1. 首次运行：交互创建数据并保存
printf 'add device EV01 高压电池组\nadd sensor EV01 绕组温度 °C 32.5\nadd sensor EV01 母线电压 V 400.0\nadd actuator EV01 驱动电机 5000\nonline\ncontrol EV01 2 60\nshow\nsave\nquit\n' | python3 device_manager.py

# 2. 二次运行：验证从 devices.json 加载
printf 'load\nonline\nshow\nquit\n' | python3 device_manager.py
```

已验证：以上两条命令流与本机 python3（3.13.12）实际运行输出一致。
