"""参考解：第 4 题（实现）——字符 tokenizer

    uv run python sol-04-tokenizer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from impl import CharTokenizer  # noqa: E402


def main() -> None:
    tok = CharTokenizer().fit("the cat sees the ball. the dog sees the cat.")
    text = "the cat sees the ball."
    ids = tok.encode(text)
    print(f"chars={len(tok.itos)} ids={ids[:8].tolist()} ...")
    assert tok.decode(ids) == text
    assert tok.encode("z")[0] == 0


if __name__ == "__main__":
    main()
