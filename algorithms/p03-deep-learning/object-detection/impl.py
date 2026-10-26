"""目标检测：网格预测与 NMS — 手写 TinyYOLO-lite。

32×32 灰度图 → 4×4 平均池化得到 8×8 特征图 → conv(1→16, 3×3, pad1)
→ ReLU → 1×1 网格头（每格 objectness + 4 个 bbox 偏移，单类）：

    X, boxes = make_dataset(480, seed=0)
    det = TinyYOLO().fit(X, boxes).predict(X, conf=0.3, iou_thresh=0.5)

手写纪律：卷积反向、BCE/MSE 损失、IoU、NMS、AP 全部 numpy 手写；
不 import sklearn / torch。合成数据固定 seed，标注为像素 bbox (x1,y1,x2,y2)。
"""

from __future__ import annotations

import numpy as np

SIZE, GRID = 32, 8
CELL = SIZE // GRID

def _shape_mask(box: np.ndarray, kind: int) -> np.ndarray:
    """整数像素 bbox 内的矩形 / 椭圆掩码。kind=0 矩形，1 椭圆。"""
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    mask = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    if kind == 1:
        cx, cy = (x0 + x1 - 1) / 2.0, (y0 + y1 - 1) / 2.0
        rx, ry = max((x1 - x0) / 2.0, .5), max((y1 - y0) / 2.0, .5)
        mask &= ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    return mask


def _apart(a: np.ndarray, b: np.ndarray, gap: float = 1.0) -> bool:
    return bool(a[2] + gap <= b[0] or b[2] + gap <= a[0]
                or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def make_image(rng: np.random.Generator, max_objects: int = 2,
               allow_overlap: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """一张 32×32 图：噪声背景 + 1~max_objects 个亮目标。返回 (img, boxes)。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    img = rng.normal(0.16, 0.045, (SIZE, SIZE)) + 0.03 * (xx + yy) / (2 * SIZE)
    boxes: list[np.ndarray] = []
    for _ in range(int(rng.integers(1, max_objects + 1))):
        for _try in range(80):
            w, h = int(rng.integers(6, 11)), int(rng.integers(6, 11))
            x0, y0 = int(rng.integers(1, SIZE - w)), int(rng.integers(1, SIZE - h))
            box = np.array([x0, y0, x0 + w, y0 + h], dtype=float)
            if not allow_overlap and not all(_apart(box, b) for b in boxes):
                continue
            mask = _shape_mask(box, int(rng.integers(0, 2)))
            img[mask] = rng.uniform(0.62, 0.96) + rng.normal(0.0, 0.02, mask.sum())
            boxes.append(box)
            break
    img = np.clip(img + rng.normal(0.0, 0.025, (SIZE, SIZE)), 0.0, 1.0)
    return img.astype(np.float32), np.array(boxes, dtype=float).reshape(-1, 4)


def make_dataset(n: int, seed: int = 0, max_objects: int = 2,
                 allow_overlap: bool = False) -> tuple[np.ndarray, list[np.ndarray]]:
    """确定性数据集：X (n,1,32,32)，boxes 是长度 n 的 list。"""
    rng = np.random.default_rng(seed)
    X = np.empty((n, 1, SIZE, SIZE), dtype=np.float32)
    ys: list[np.ndarray] = []
    for i in range(n):
        X[i, 0], b = make_image(rng, max_objects, allow_overlap)
        ys.append(b)
    return X, ys

def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def _logit(p: np.ndarray | float, eps: float = 0.02) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    return np.log(p / (1.0 - p))


class Conv2D:
    """stride=1 的 2D 卷积；im2col 前向、col2im 反向（复用 cnn-lenet 思路）。"""

    def __init__(self, cin: int, cout: int, k: int, rng: np.random.Generator,
                 pad: int | None = None) -> None:
        self.pad = k // 2 if pad is None else pad
        self.W = rng.normal(0.0, np.sqrt(2.0 / (cin * k * k)), (cout, cin, k, k))
        self.b = np.zeros(cout)

    def forward(self, X: np.ndarray) -> np.ndarray:
        N, C, H, W = X.shape
        k, p = self.W.shape[2], self.pad
        Xp = np.pad(X, ((0, 0), (0, 0), (p, p), (p, p))) if p else X
        oh, ow = H + 2 * p - k + 1, W + 2 * p - k + 1
        cols = np.empty((N, oh, ow, C, k, k), dtype=X.dtype)
        for i in range(k):                      # 每个卷积核位置抽一列
            for j in range(k):
                cols[:, :, :, :, i, j] = Xp[:, :, i:i + oh, j:j + ow].transpose(0, 2, 3, 1)
        self.cols = cols.reshape(N * oh * ow, -1)
        self.shape = (N, C, H, W, oh, ow)
        out = self.cols @ self.W.reshape(self.W.shape[0], -1).T + self.b
        return out.reshape(N, oh, ow, -1).transpose(0, 3, 1, 2)

    def backward(self, dout: np.ndarray) -> np.ndarray:
        N, C, H, W, oh, ow = self.shape
        k, p = self.W.shape[2], self.pad
        d = dout.transpose(0, 2, 3, 1).reshape(-1, self.W.shape[0])
        self.dW = (d.T @ self.cols).reshape(self.W.shape)
        self.db = d.sum(axis=0)
        dc = (d @ self.W.reshape(self.W.shape[0], -1)).reshape(N, oh, ow, C, k, k)
        dXp = np.zeros((N, C, H + 2 * p, W + 2 * p), dtype=dout.dtype)
        for i in range(k):                      # col2im：窗口梯度按位置累加
            for j in range(k):
                dXp[:, :, i:i + oh, j:j + ow] += dc[:, :, :, :, i, j].transpose(0, 3, 1, 2)
        return dXp[:, :, p:p + H, p:p + W]

def encode_targets(boxes: np.ndarray, grid: int = GRID) -> tuple[np.ndarray, np.ndarray]:
    """bbox → (objectness (g,g), 原始 bbox 目标 (g,g,4))；中心落在哪格就算正样本。"""
    obj = np.zeros((grid, grid), dtype=np.float32)
    tbox = np.zeros((grid, grid, 4), dtype=np.float32)
    cell = SIZE / grid
    for x0, y0, x1, y1 in np.asarray(boxes, dtype=float).reshape(-1, 4):
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        gx, gy = min(int(cx / cell), grid - 1), min(int(cy / cell), grid - 1)
        obj[gy, gx] = 1.0
        tbox[gy, gx] = [_logit(cx / cell - gx), _logit(cy / cell - gy),
                        _logit((x1 - x0) / SIZE), _logit((y1 - y0) / SIZE)]
    return obj, tbox


def decode_cells(raw: np.ndarray, grid: int = GRID) -> tuple[np.ndarray, np.ndarray]:
    """raw (5,g,g) → 像素 bbox (g*g,4) 与 objectness 概率 (g*g,)。"""
    s = sigmoid(raw)
    gy, gx = np.mgrid[0:grid, 0:grid]
    cell = SIZE / grid
    cx, cy = (gx + s[1]) * cell, (gy + s[2]) * cell
    w, h = s[3] * SIZE, s[4] * SIZE
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=-1)
    return boxes.reshape(-1, 4), s[0].reshape(-1)

def iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """一个框与一组框的交并比，返回 (K,)。"""
    b = np.asarray(boxes, dtype=float).reshape(-1, 4)
    x1, y1 = np.maximum(box[0], b[:, 0]), np.maximum(box[1], b[:, 1])
    x2, y2 = np.minimum(box[2], b[:, 2]), np.minimum(box[3], b[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area, areas = (box[2] - box[0]) * (box[3] - box[1]), (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area + areas - inter, 1e-9)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.5) -> np.ndarray:
    """贪心 NMS：分数降序，删掉与已保留框 IoU > 阈值的框。返回保留下标。"""
    boxes = np.asarray(boxes, dtype=float).reshape(-1, 4)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(boxes) != len(scores):
        raise ValueError("boxes 与 scores 数量不一致")
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        order = rest[iou(boxes[i], boxes[rest]) <= iou_thresh]
    return np.asarray(keep, dtype=int)

class TinyYOLO:
    """单卷积 + 8×8 网格头；损失 = BCE(objectness) + MSE(正格 bbox)。"""

    def __init__(self, channels=16, lr=.02, epochs=60, batch_size=32, seed=0, lam=1.0) -> None:
        if channels < 1 or epochs < 1 or batch_size < 1:
            raise ValueError("channels / epochs / batch_size 必须为正")
        self.channels, self.lr, self.epochs = channels, lr, epochs
        self.batch_size, self.seed, self.lam = batch_size, seed, lam
        self.loss_history: list[float] = []

    def _init(self) -> None:
        rng = np.random.default_rng(self.seed)
        self.conv = Conv2D(1, self.channels, 3, rng)   # 输入已是 8×8 池化图
        self.head = Conv2D(self.channels, 5, 1, rng)
        self._adam: dict = {}
        self._t = 0

    def _forward(self, X: np.ndarray) -> np.ndarray:
        if not hasattr(self, "conv"):
            raise RuntimeError("模型尚未训练：先调用 fit()")
        pooled = X.reshape(len(X), 1, GRID, CELL, GRID, CELL).mean(axis=(3, 5))
        self._z = self.conv.forward(pooled)             # (N,C,8,8)
        return self.head.forward(np.maximum(self._z, 0.0))   # (N,5,8,8)

    def _loss_grad(self, raw: np.ndarray, obj: np.ndarray, tbox: np.ndarray):
        prob = sigmoid(raw[:, 0])                           # (N,8,8)
        bce = -(obj * np.log(prob + 1e-7) + (1 - obj) * np.log(1 - prob + 1e-7))
        pos, n_pos = obj > 0.5, int((obj > 0.5).sum())
        diff = raw[:, 1:].transpose(0, 2, 3, 1)[pos] - tbox[pos]
        loss_box = float((diff ** 2).sum(axis=1).mean()) if n_pos else 0.0
        d_box = np.zeros((len(raw), GRID, GRID, 4))
        if n_pos:
            d_box[pos] = 2.0 * diff / n_pos
        grad = np.zeros_like(raw)
        grad[:, 0] = (prob - obj) / prob.size             # BCE + sigmoid 的梯度
        grad[:, 1:] = d_box.transpose(0, 3, 1, 2)
        return float(bce.mean()) + self.lam * loss_box, grad

    def _step(self) -> None:
        self._t += 1
        for key, layer in (("conv", self.conv), ("head", self.head)):
            for name, g in (("W", layer.dW), ("b", layer.db)):
                p = getattr(layer, name)
                st = self._adam.setdefault((key, name), [np.zeros_like(p), np.zeros_like(p)])
                st[0] = 0.9 * st[0] + 0.1 * g
                st[1] = 0.999 * st[1] + 0.001 * g ** 2
                p -= self.lr * (st[0] / (1 - 0.9 ** self._t)) / (
                    np.sqrt(st[1] / (1 - 0.999 ** self._t)) + 1e-8)

    def fit(self, X: np.ndarray, boxes: list[np.ndarray]) -> TinyYOLO:
        X = np.asarray(X, dtype=float)
        if X.ndim != 4 or X.shape[1:] != (1, SIZE, SIZE) or len(X) != len(boxes):
            raise ValueError("X 应为 (N,1,32,32)，boxes 长度与 N 相同")
        obj_all, box_all = zip(*(encode_targets(b) for b in boxes))
        obj_all, box_all = np.stack(obj_all), np.stack(box_all)  # (N,8,8) / (N,8,8,4)
        self._init()
        rng = np.random.default_rng(self.seed + 1)
        for _ in range(self.epochs):
            order = rng.permutation(len(X))
            for s in range(0, len(X), self.batch_size):
                idx = order[s:s + self.batch_size]
                _, grad = self._loss_grad(self._forward(X[idx]), obj_all[idx], box_all[idx])
                self._backward_head(grad)
                self._step()
            loss, _ = self._loss_grad(self._forward(X), obj_all, box_all)
            self.loss_history.append(loss)
        return self

    def _backward_head(self, grad: np.ndarray) -> None:
        # 池化发生在输入侧且无参数，梯度到 8×8 特征图即止
        self.conv.backward(self.head.backward(grad) * (self._z > 0.0))

    def raw_predict(self, X: np.ndarray, iou_thresh: float = 0.5) -> list[np.ndarray]:
        X = np.asarray(X, dtype=float)
        if X.ndim != 4 or X.shape[1:] != (1, SIZE, SIZE):
            raise ValueError("X 应为 (N,1,32,32)")
        out = []
        for r in self._forward(X):
            b, s = decode_cells(r)
            keep = nms(b, s, iou_thresh)
            out.append(np.column_stack([np.clip(b[keep], 0.0, SIZE), s[keep]]))
        return out

    def predict(self, X: np.ndarray, conf: float = 0.3,
                iou_thresh: float = 0.5) -> list[np.ndarray]:
        return [d[d[:, 4] >= conf] for d in self.raw_predict(X, iou_thresh)]

def average_precision(dets: list[np.ndarray], gts: list[np.ndarray],
                      iou_thresh: float = 0.5) -> float:
    """单类 AP@iou（VOC 全点插值）；dets[i] 为 (k,5)，gts[i] 为 (m,4)。"""
    records = sorted([(float(d[4]), i, d[:4]) for i, ds in enumerate(dets) for d in ds],
                     key=lambda r: -r[0])
    used = [np.zeros(len(g), dtype=bool) for g in gts]
    tp, total = np.zeros(len(records)), sum(len(g) for g in gts)
    for k, (_, i, box) in enumerate(records):
        if not len(gts[i]):
            continue
        ov = iou(box, gts[i])
        ov[used[i]] = -1.0
        j = int(np.argmax(ov))
        if ov[j] >= iou_thresh:
            tp[k], used[i][j] = 1.0, True
    if not tp.sum() or not total:
        return 0.0
    ctp = np.cumsum(tp)
    rec = ctp / total
    prec = ctp / np.maximum(ctp + np.cumsum(1 - tp), 1e-9)
    mrec, mpre = np.concatenate([[0.0], rec, [1.0]]), np.concatenate([[0.0], prec, [0.0]])
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    return float(np.sum((mrec[1:] - mrec[:-1]) * mpre[1:]))


def match_counts(dets: list[np.ndarray], gts: list[np.ndarray], conf: float,
                 iou_thresh: float = 0.5) -> tuple[int, int, int]:
    """给定置信度阈值，返回 (TP, FP, FN)；每图按分数降序贪心匹配。"""
    tp = fp = fn = 0
    for ds, g in zip(dets, gts):
        ds = ds[ds[:, 4] >= conf] if len(ds) else ds
        used = np.zeros(len(g), dtype=bool)
        for d in ds[np.argsort(-ds[:, 4])] if len(ds) else []:
            ov = iou(d[:4], g) if len(g) else np.zeros(0)
            if len(g):
                ov[used] = -1.0
                j = int(np.argmax(ov))
                if ov[j] >= iou_thresh:
                    tp += 1
                    used[j] = True
                    continue
            fp += 1
        fn += int((~used).sum())
    return tp, fp, fn

