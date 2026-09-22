package com.example;

import com.example.ShoppingCart.Item;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * AssertJ 流式断言：assertThat(实际值).链式断言(...)，失败信息比 JUnit 断言更可读。
 * 对应主文档 3.4；完整工程见 examples/ex05-assertj/。
 * 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + AssertJ 3.25.3（离线 mvn -o）。
 */
class ShoppingCartAssertJTest {

    private ShoppingCart cart;

    @BeforeEach
    void setUp() {
        cart = new ShoppingCart();
        cart.add(new Item("Java 编程思想", 99));
        cart.add(new Item("Effective Java", 88));
    }

    @Test
    void total_sumsAllPrices() {
        assertThat(cart.total()).isEqualTo(187);
    }

    @Test
    void items_areExposedAsUnmodifiableSnapshot() {
        // 链式断言：连续校验多个属性，失败时全部报告
        assertThat(cart.items())
                .hasSize(2)
                .extracting(Item::name)
                .containsExactly("Java 编程思想", "Effective Java");

        // 防御性拷贝生效：向返回的只读列表写数据应抛异常
        assertThatThrownBy(() -> cart.items().add(new Item("x", 1)))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void contains_matchesByName() {
        assertThat(cart.contains("Effective Java")).isTrue();
        assertThat(cart.contains("不存在的书")).isFalse();
    }

    @Test
    void add_rejectsInvalidItem() {
        // 异常断言：类型 + 消息片段双校验
        assertThatThrownBy(() -> cart.add(new Item("", 10)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("商品非法");

        assertThatThrownBy(() -> cart.add(new Item("免费", -1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("商品非法");
    }

    @Test
    void total_isZero_whenCartEmpty() {
        assertThat(new ShoppingCart().total()).isZero();
    }
}
