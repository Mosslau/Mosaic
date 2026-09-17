# device-codec 车端二进制编解码服务

> OceanVerse 第 1 阶段收尾（提前量）——二进制链路的 L1→L2 翻译层
> 职责：消费 `ov.raw.binary.v1` → 按 `proto_ver` 选解码器 → 输出 `VehicleReport` 到 `vehicle-report-raw`（与 JSON 通道汇合，下游无感）
> 纪律：未知版本不猜、直接 DLQ；不做鉴权/限流/业务判断；无状态可横扩
> 📐 规格：《../docs/GB32960-二进制协议与字段映射-v1.md》（已定稿 v1.4）

## 链路位置

```
T-BOX → MQTT(二进制载荷) → EMQX → webhook → device-gateway 透传(不解帧)
  → Kafka: ov.raw.binary.v1 {vin, ts, proto_ver, cmd, payload:base64}
  → 本服务解码 → Kafka: vehicle-report-raw
  → 失败 → Kafka: ov.dlq.codec.v1 (带原始帧 base64 + 失败原因 + stage)
```

## 运行

```bash
# 默认配置即可本地联调(Kafka localhost:19092)
go run ./cmd/server

# 环境变量
KAFKA_BROKERS=localhost:19092   # broker 列表(逗号分隔)
CODEC_SRC_TOPIC=ov.raw.binary.v1
CODEC_DST_TOPIC=vehicle-report-raw
CODEC_DLQ_TOPIC=ov.dlq.codec.v1
CODEC_GROUP=device-codec-v1     # 消费者组(横扩 = 同组多副本)
```

## 可靠性语义

- **写出全部成功才提交位移**：崩溃/失败 → 重读，at-least-once（下游按 `(vin,ts)` 幂等）
- **DLQ 两级**：帧级（同步/长度/BCC/时间/未知 proto_ver）整帧进；单元级（自定义单元未知版本、信息体长度不足）只丢该单元，帧其余部分照常解析
- **单字段非法只丢字段**（无效值 0xFF/0xFFFF、非法枚举码），不进 DLQ（§5.2 粒度纪律）

## 目录

```
ingest/device-codec/
├── cmd/server/             # 主程序: 消费→解码→投递+DLQ→提交位移
├── internal/gbt32960/      # v1 解码器(帧解析 + 全部信息体; 黄金样本对拍测试)
└── README.md               # 本文件
```

## 对拍关系

本解码器与模拟器模块的 `internal/simframe` 造帧器（`ingest/device-simulator/`）**独立实现同一规格**（映射文档 §5/§5.1/§5.2），
黄金样本（58B 示例帧）双端各存一份，对不上即 bug 或文档歧义——已实抓一处字节错位（0x08 子系统头偏移）。
