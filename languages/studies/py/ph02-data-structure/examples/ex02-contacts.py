# 来源：languages/py/ph02-data-structure/02-data-structure.md 第 6 章「示例 2：通讯录」
# 说明：用嵌套 dict 做通讯录——添加、get 安全查询、遍历嵌套信息。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 ex02-contacts.py
# 验证状态：已验证

"""通讯录示例：演示嵌套 dict 的增查与遍历。"""


def main() -> None:
    """演示 dict 通讯录的添加、查询与遍历。"""
    contacts = {
        "Alice": {"phone": "13800138000", "city": "Shanghai"},
        "Bob": {"phone": "13900139000", "city": "Beijing"},
    }

    # 添加联系人
    contacts["Carol"] = {"phone": "13700137000", "city": "Shenzhen"}

    # 查询：get 拿不到时返回 None，避免 KeyError
    name = "Bob"
    info = contacts.get(name)
    if info:
        print(f"{name}: {info['phone']}, {info['city']}")
    else:
        print(f"未找到 {name}")

    # 列出所有城市
    for name, info in contacts.items():
        print(f"{name} 住在 {info['city']}")


if __name__ == "__main__":
    main()
