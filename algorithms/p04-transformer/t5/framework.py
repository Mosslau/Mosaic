"""T5 / encoder-decoder — PyTorch 对照骨架

TODO：用 nn.Transformer（encoder-decoder）或自写 cross-attention，
与 impl.py 同数据/同 teacher forcing 对照。
"""


def run_framework(*args, **kwargs):
    raise NotImplementedError("TODO: PyTorch encoder-decoder 对照")


if __name__ == "__main__":
    raise SystemExit("本文件是对照骨架，由 demo.py 调用")
