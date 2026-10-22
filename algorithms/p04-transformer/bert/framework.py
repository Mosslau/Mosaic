"""BERT / MLM — PyTorch 对照骨架

TODO：用 nn.TransformerEncoder（或自写 non-causal attention）+ MLM head，
与 impl.py 同数据/同 mask 策略对照。
"""


def run_framework(*args, **kwargs):
    raise NotImplementedError("TODO: PyTorch BERT/MLM 对照")


if __name__ == "__main__":
    raise SystemExit("本文件是对照骨架，由 demo.py 调用")
