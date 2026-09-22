# 来源：languages/py/ph02-data-structure/02-data-structure.md 第 6 章「示例 3：购物车」
# 说明：用 list of dict 表达购物车记录——计算总价、按单价排序。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 ex03-cart.py
# 验证状态：已验证

"""购物车示例：演示 list of dict 嵌套结构与 sorted 的 key 参数。"""


def main() -> None:
    """演示 list of dict 购物车的总价计算与排序。"""
    # 购物车：列表中的每个元素是一个 dict，表示一条记录
    cart = [
        {"name": "apple", "price": 5.5, "quantity": 3},
        {"name": "banana", "price": 3.0, "quantity": 2},
        {"name": "milk", "price": 12.0, "quantity": 1},
    ]

    # 计算总价
    total = sum(item["price"] * item["quantity"] for item in cart)
    print(f"总价: {total:.2f}")

    # 按单价排序
    sorted_cart = sorted(cart, key=lambda x: x["price"])
    for item in sorted_cart:
        print(f"{item['name']}: {item['price']} x {item['quantity']}")


if __name__ == "__main__":
    main()
