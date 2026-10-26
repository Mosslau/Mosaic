"""TinyYOLO-lite 性质测试：IoU / NMS / 网格编解码 / 损失 / 形状边界。"""

from __future__ import annotations

import numpy as np
import pytest
from impl import (
    TinyYOLO,
    average_precision,
    decode_cells,
    encode_targets,
    iou,
    make_dataset,
    make_image,
    match_counts,
    nms,
    sigmoid,
)


def test_iou_identity_and_disjoint() -> None:
    a = np.array([0.0, 0.0, 10.0, 10.0])
    np.testing.assert_allclose(iou(a, a[None]), [1.0], atol=1e-12)
    b = np.array([[20.0, 20.0, 30.0, 30.0], [10.0, 0.0, 20.0, 10.0]])
    np.testing.assert_allclose(iou(a, b), [0.0, 0.0], atol=1e-12)


def test_iou_known_and_symmetric() -> None:
    a = np.array([0.0, 0.0, 10.0, 10.0])
    b = np.array([5.0, 0.0, 15.0, 10.0])
    val = iou(a, b[None])[0]
    assert abs(val - 50.0 / 150.0) < 1e-12
    assert abs(val - iou(b, a[None])[0]) < 1e-12


def test_iou_bounds_random() -> None:
    rng = np.random.default_rng(0)
    for _ in range(200):
        xy = rng.uniform(0, 24, size=(2, 2))
        wh = rng.uniform(1, 8, size=(2, 2))
        boxes = np.concatenate([xy, xy + wh], axis=1)
        val = iou(boxes[0], boxes[1:])
        assert 0.0 <= val[0] <= 1.0


def test_nms_known_case() -> None:
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [20, 20, 30, 30]], float)
    scores = np.array([0.9, 0.8, 0.4])
    keep = nms(boxes, scores, iou_thresh=0.5)
    assert keep.tolist() == [0, 2]          # 第二个与第一个 IoU≈0.68 > 0.5 被抑制


def test_nms_empty_and_sorted() -> None:
    assert nms(np.zeros((0, 4)), np.zeros(0)).size == 0
    boxes = np.array([[0, 0, 5, 5], [10, 10, 15, 15]], float)
    scores = np.array([0.2, 0.9])
    keep = nms(boxes, scores, iou_thresh=0.5)
    assert keep.tolist() == [1, 0]          # 先保留分数最高的
    with pytest.raises(ValueError):
        nms(boxes, np.array([0.5]))


def test_grid_encode_roundtrip() -> None:
    boxes = np.array([[5.0, 4.0, 13.0, 12.0], [19.0, 21.0, 27.0, 29.0],
                      [2.0, 18.0, 10.0, 25.0]])
    obj, tbox = encode_targets(boxes)
    assert obj.shape == (8, 8) and tbox.shape == (8, 8, 4)
    for box in boxes:
        cy, cx = (box[1] + box[3]) / 2, (box[0] + box[2]) / 2
        gy, gx = int(cy // 4), int(cx // 4)
        raw = np.zeros((5, 8, 8))
        raw[0, gy, gx] = 12.0
        raw[1:, gy, gx] = tbox[gy, gx]
        decoded, scores = decode_cells(raw)
        idx = gy * 8 + gx
        assert scores[idx] > 0.99
        assert iou(box, decoded[idx:idx + 1])[0] > 0.97


def test_encode_center_cell_and_offsets() -> None:
    # 手算示例：bbox (11,5,19,13) 的中心 (15,9) 落在第 3 列、第 2 行
    obj, tbox = encode_targets(np.array([[11.0, 5.0, 19.0, 13.0]]))
    assert obj.sum() == 1 and obj[2, 3] == 1
    np.testing.assert_allclose(tbox[2, 3], [np.log(3.0), np.log(1.0 / 3.0),
                                            np.log(0.25 / 0.75), np.log(0.25 / 0.75)],
                               atol=1e-6)


def test_forward_shapes_and_ranges() -> None:
    X, boxes = make_dataset(24, seed=5)
    m = TinyYOLO(channels=8, epochs=2, seed=0).fit(X, boxes)
    raw = m._forward(X[:3])
    assert raw.shape == (3, 5, 8, 8)
    prob = sigmoid(raw[:, 0])
    assert np.all(prob > 0) and np.all(prob < 1)
    dets = m.predict(X[:3], conf=0.0)
    assert len(dets) == 3
    for d in dets:
        assert d.shape[1] == 5
        assert np.all(d[:, :4] >= 0) and np.all(d[:, :4] <= 32)


def test_loss_decreases() -> None:
    X, boxes = make_dataset(160, seed=3)
    m = TinyYOLO(channels=8, epochs=30, batch_size=32, seed=0).fit(X, boxes)
    assert m.loss_history[-1] < 0.5 * m.loss_history[0]


def test_dataset_deterministic_and_valid() -> None:
    X1, b1 = make_dataset(12, seed=7)
    X2, b2 = make_dataset(12, seed=7)
    X3, _ = make_dataset(12, seed=8)
    np.testing.assert_array_equal(X1, X2)
    assert all(np.array_equal(a, b) for a, b in zip(b1, b2))
    assert not np.array_equal(X1, X3)
    assert X1.shape == (12, 1, 32, 32) and X1.min() >= 0 and X1.max() <= 1
    for boxes in b1:
        assert 1 <= len(boxes) <= 2
        assert np.all(boxes >= 0) and np.all(boxes <= 32)
        assert np.all(boxes[:, 2] > boxes[:, 0]) and np.all(boxes[:, 3] > boxes[:, 1])
        if len(boxes) == 2:
            assert iou(boxes[0], boxes[1:])[0] == 0.0   # 教学集目标不重叠


def test_training_learns_detection() -> None:
    Xtr, btr = make_dataset(240, seed=10)
    Xte, bte = make_dataset(60, seed=11)
    m = TinyYOLO(channels=16, epochs=40, batch_size=32, seed=0).fit(Xtr, btr)
    dets = m.raw_predict(Xte)
    ap = average_precision(dets, bte)
    assert ap > 0.80, f"AP 太低：{ap:.3f}"
    tp, fp, fn = match_counts(dets, bte, conf=0.1)
    assert tp > 0 and fp < tp and fn < tp


def test_invalid_inputs_and_single_image() -> None:
    with pytest.raises(ValueError):
        TinyYOLO(channels=0)
    with pytest.raises(ValueError):
        TinyYOLO().fit(np.zeros((2, 1, 32, 31)), [np.zeros((0, 4))] * 2)
    with pytest.raises(RuntimeError):
        TinyYOLO().raw_predict(np.zeros((1, 1, 32, 32)))
    rng = np.random.default_rng(0)
    img, boxes = make_image(rng)
    assert img.shape == (32, 32) and img.dtype == np.float32 and len(boxes) >= 1
