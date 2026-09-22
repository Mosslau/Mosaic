package com.example.msdemo.order.domain;

/**
 * 订单实体（内存存储，聚焦「数据跟着服务走」的拆分纪律，持久化是 ph13/ph15 的内容）。
 * userId 指向 user-service 的用户：订单服务不直连用户库，聚合用户名要走 user-service 的 API（主文档 3.1）。
 */
public record Order(long orderId, long userId, String item) {
}
