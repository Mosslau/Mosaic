# 练习：目标检测 · 网格预测与 NMS

题目按五级能力分级；**题面不附答案**，参考解在 `sol-NN-*`，先自己做再对照。

| 题 | 级别 | 主题 | 参考解 |
|---|---|---|---|
| 1 | 1 说清 | 复述 objectness / 偏移 / IoU / NMS | `sol-01-概念.md` |
| 2 | 2 走通 | 手算编码、IoU、NMS | `sol-02-手算.md` |
| 3 | 3 判断 | 诊断失效变体 | `sol-03-诊断.md` |
| 4 | 4 实现 | 手写 GIoU + GIoU-NMS | `sol-04-giou.py` |
| 5 | 4 实现 | 独立实现 PR 曲线与 AP | `sol-05-pr-ap.py` |
| 6 | 5 迁移 | 多目标重叠场景迁移 | `sol-06-scene.py` |

## 第 1 题（说清）objectness、偏移与 IoU

**目标**：能用自己的话讲清网格预测在预测什么。

**要求**：不看资料写出（a）objectness 的含义；（b）4 个 bbox 偏移如何解码成像素框；（c）IoU 的定义；（d）NMS 的三步规则。

**验收**：decode 必须写出 `cx=(gx+σ(tx))·4`、`w=σ(tw)·32`；说明为什么只有中心格算正样本；NMS 写出"按分数降序、保留最高、抑制 IoU 超阈值"。

**提示**：基础篇「核心量」与「手算示例」节。

## 第 2 题（走通）手算编码、IoU 与 NMS

**目标**：在纸上完成一次编码与一次 NMS。

**要求**：8×8 网格、4 像素/格。bbox `(7,6,15,14)`：
1. 求中心、所在格 `(gx,gy)`、`fx/fy/w/h`；
2. 求四项回归目标（用 logit 表示，可保留 `log`）；
3. 预测框 `(8,7,16,15)` 与它的 IoU；
4. 三个框 `A[0,0,10,10] score .9`、`B[1,1,11,11] score .8`、`C[20,20,30,30] score .4`，写出 `IoU=0.5` 的 NMS 保留集合。

**验收**：第 3 步 IoU = 49/79；第 4 步保留 A、C（B 与 A 的 IoU ≈ 0.68）。

**提示**：先画 8×8 格，标出 bbox 中心；IoU 用"交/并"手算。

## 第 3 题（判断）诊断两个失效变体

**目标**：识别失效条件并给出反例。

**要求**：有人提出两个"简化"：
- 变体甲：删掉 NMS，直接输出所有 `objectness > 0.1` 的格；
- 变体乙：NMS 的 IoU 阈值改成 0.95。

分别说明：哪个指标会先坏（P 还是 R）、为什么；各给一个具体反例（可以用坐标和分数构造）。再说明为什么置信度/NMS 阈值必须在 val 上选。

**验收**：甲能指出同一目标的邻格重复框使 P 下降；乙能指出 IoU 0.6 的重复框不会被抑制；反例可复算。

**提示**：基础篇「白话版」的失效边界；用 `impl.nms` 跑一遍反例。

## 第 4 题（实现）手写 GIoU 与 GIoU-NMS

**目标**：把 IoU 换成 GIoU，并实现对应的 NMS。

**要求**：在 `sol-04-giou.py` 中手写 `giou(box, boxes)` 与 `nms_giou(boxes, scores, thresh)`；要求 GIoU ∈ [-1,1]，同框为 1；在固定三框上验证 GIoU-NMS 与 IoU-NMS 的差异。

**验收**：运行脚本，断言全部通过；解释"为什么 GIoU 能惩罚不相交的框"。

**提示**：GIoU = IoU − (最小闭包面积 − 并集面积)/最小闭包面积。

## 第 5 题（实现）独立实现 PR 与 AP

**目标**：独立实现 precision-recall 曲线与 AP，并与 `impl.average_precision` 对拍。

**要求**：在 `sol-05-pr-ap.py` 中不调用 `impl.average_precision`，只用 `impl.iou` 做匹配；实现 VOC 全点插值 AP；在固定检测列表上比较两者。

**验收**：脚本输出两个 AP，差值 < 1e-9；手算该例 AP = 5/6。

**提示**：先按分数全局排序，再逐图贪心匹配；注意未被匹配的 GT 计入 recall 分母。

## 第 6 题（迁移）多目标重叠场景

**目标**：把检测器用到 2–3 个目标、允许部分重叠的场景。

**要求**：复用 `project/` 的场景生成器（或自己写一个），训练 TinyYOLO-lite，在测试集上报告 mAP@0.5、P/R，并与颜色阈值基线比较；至少跑 60 轮。

**验收**：测试 mAP > 0.80，且比基线高 0.20 以上；说明重叠目标为什么让连通域基线掉分。

**提示**：`project/detect_scene.py` 的 `make_scene_dataset` 已处理"中心格冲突"和"两两 IoU ≤ 0.35"。

## 参考解运行记录

```bash
cd algorithms/p03-deep-learning/object-detection
uv run python exercises/sol-04-giou.py
uv run python exercises/sol-05-pr-ap.py
uv run python exercises/sol-06-scene.py
```

实跑观察（2026-10-26，本机 `.venv`）：

- `sol-04-giou.py`：GIoU 自检、三框抑制自检通过。
- `sol-05-pr-ap.py`：手写 AP 与 `impl.average_precision` 均为 0.833333。
- `sol-06-scene.py`：TinyYOLO mAP 0.880 / 基线 0.635，验收通过。
