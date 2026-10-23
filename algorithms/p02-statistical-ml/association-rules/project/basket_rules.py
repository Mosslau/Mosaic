"""迁移项目：购物篮规则筛选

    uv run python basket_rules.py

在合成购物篮上挖掘规则，按 lift/confidence 过滤，输出可执行建议。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from demo import make_transactions  # noqa: E402
from impl import Apriori  # noqa: E402


def main() -> None:
    trans = make_transactions(300, seed=0)
    ap = Apriori(min_support=0.05, max_len=3).fit(trans)
    rules = ap.rules(min_confidence=0.5)
    good = [r for r in rules if r.lift >= 1.1 and r.confidence >= 0.8]
    print(f"规则 {len(rules)}，筛选后 {len(good)}")
    for r in good[:6]:
        print(f"  {sorted(r.antecedent)} → {sorted(r.consequent)} "
              f"(sup {r.support:.2f}, conf {r.confidence:.2f}, lift {r.lift:.2f})")
    assert len(good) >= 3
    print("→ 规则可做交叉销售候选；但共现不等于因果，需 A/B 验证。")


if __name__ == "__main__":
    main()
