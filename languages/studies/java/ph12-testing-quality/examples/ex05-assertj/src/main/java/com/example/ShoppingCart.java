package com.example;

import java.util.ArrayList;
import java.util.List;

/** 购物车：聚合商品条目并计算总价。 */
public class ShoppingCart {

    /** 商品条目（record）：名称 + 单价（分）。 */
    public record Item(String name, int price) {
    }

    private final List<Item> items = new ArrayList<>();

    public void add(Item item) {
        if (item == null || item.name().isBlank() || item.price() < 0) {
            throw new IllegalArgumentException("商品非法: " + item);
        }
        items.add(item);
    }

    /** 防御性拷贝：外部拿到的是只读快照，改它不会影响内部状态。 */
    public List<Item> items() {
        return List.copyOf(items);
    }

    public int total() {
        return items.stream().mapToInt(Item::price).sum();
    }

    public boolean contains(String name) {
        return items.stream().anyMatch(i -> i.name().equals(name));
    }
}
