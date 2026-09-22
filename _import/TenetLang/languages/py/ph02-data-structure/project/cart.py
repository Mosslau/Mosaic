# 来源：languages/py/ph02-data-structure/project/README.md「ph02 阶段项目：购物车」
# 说明：交互式命令行购物车——list of dict 管理商品，支持增删查、总价、按单价排序。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 cart.py（交互）；printf '1\napple\n5.5\n3\n4\n0\n' | python3 cart.py（管道喂输入）
# 验证状态：已验证

"""购物车阶段项目：用 list of dict 管理商品的交互式 CLI。"""


def find_item(cart: list, name: str) -> dict | None:
    """按名称查找购物车条目，找不到返回 None。"""
    for item in cart:
        if item["name"] == name:
            return item
    return None


def add_item(cart: list) -> None:
    """添加商品；重名商品累加数量。"""
    name = input("商品名称: ").strip()
    price = float(input("单价: "))
    quantity = int(input("数量: "))

    item = find_item(cart, name)
    if item is None:
        cart.append({"name": name, "price": price, "quantity": quantity})
        print(f"已添加: {name}")
    else:
        item["quantity"] += quantity
        print(f"{name} 数量更新为 {item['quantity']}")


def remove_item(cart: list) -> None:
    """按名称删除商品；不存在时提示。"""
    name = input("要删除的商品名称: ").strip()
    item = find_item(cart, name)
    if item is None:
        print(f"未找到 {name}")
    else:
        cart.remove(item)
        print(f"已删除: {name}")


def list_items(cart: list) -> None:
    """列出购物车全部商品及小计。"""
    if not cart:
        print("购物车为空")
        return
    for item in cart:
        subtotal = item["price"] * item["quantity"]
        print(
            f"{item['name']}: {item['price']:.2f} x {item['quantity']}"
            f" = {subtotal:.2f}"
        )


def show_total(cart: list) -> None:
    """输出购物车总价。"""
    total = sum(item["price"] * item["quantity"] for item in cart)
    print(f"总价: {total:.2f}")


def show_sorted(cart: list) -> None:
    """按单价升序展示商品。"""
    for item in sorted(cart, key=lambda x: x["price"]):
        print(f"{item['name']}: {item['price']:.2f} x {item['quantity']}")


def main() -> None:
    """交互式菜单主循环。"""
    cart: list = []
    menu = (
        "===== 购物车 =====\n"
        "1. 添加商品\n"
        "2. 删除商品\n"
        "3. 查看购物车\n"
        "4. 计算总价\n"
        "5. 按单价排序\n"
        "0. 退出"
    )

    while True:
        print(menu)
        choice = input("请选择: ").strip()
        if choice == "0":
            print("再见")
            break
        elif choice == "1":
            add_item(cart)
        elif choice == "2":
            remove_item(cart)
        elif choice == "3":
            list_items(cart)
        elif choice == "4":
            show_total(cart)
        elif choice == "5":
            show_sorted(cart)
        else:
            print("无效选项")


if __name__ == "__main__":
    main()
