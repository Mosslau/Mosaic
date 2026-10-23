"""Apriori — 性质测试（pytest）"""

import pytest
from impl import Apriori, brute_force


def toy():
    return [{"a", "b"}, {"a", "b", "c"}, {"a", "c"}, {"b", "c"},
            {"a", "b", "c", "d"}]


def test_support_counts() -> None:
    ap = Apriori(min_support=0.2, max_len=2).fit(toy())
    assert ap.support_count_[frozenset({"a", "b"})] == 3
    assert ap.frequent_itemsets_[frozenset({"a", "b"})] == pytest.approx(0.6)


def test_known_rules() -> None:
    ap = Apriori(min_support=0.2, max_len=2).fit(toy())
    rules = {frozenset(r.antecedent): r for r in ap.rules(0.5)}
    r = rules[frozenset({"d"})]
    assert r.support == pytest.approx(0.2)
    assert r.confidence == pytest.approx(1.0)
    assert r.lift > 1


def test_matches_bruteforce() -> None:
    ap = Apriori(min_support=0.2, max_len=3).fit(toy())
    bf = brute_force(toy(), min_support=0.2, max_len=3)
    assert set(ap.frequent_itemsets_) == set(bf)
    for k, v in bf.items():
        assert ap.frequent_itemsets_[k] == pytest.approx(v)


def test_confidence_threshold() -> None:
    ap = Apriori(min_support=0.2, max_len=3).fit(toy())
    assert all(r.confidence >= 0.6 for r in ap.rules(0.6))
    with pytest.raises(ValueError):
        ap.rules(1.01)


def test_max_len() -> None:
    ap = Apriori(min_support=0.2, max_len=1).fit(toy())
    assert all(len(k) == 1 for k in ap.frequent_itemsets_)


def test_empty_and_no_rule() -> None:
    with pytest.raises(ValueError):
        Apriori().fit([])
    ap = Apriori(min_support=0.9).fit(toy())
    assert ap.rules(0.99) == []


def test_invalid_params() -> None:
    with pytest.raises(ValueError):
        Apriori(min_support=0)
    with pytest.raises(ValueError):
        Apriori(max_len=0)
    ap = Apriori().fit(toy())
    with pytest.raises(ValueError):
        ap.rules(0)


def test_deterministic() -> None:
    a = Apriori(0.2, 3).fit(toy()).rules(0.5)
    b = Apriori(0.2, 3).fit(toy()).rules(0.5)
    assert [r.as_dict() for r in a] == [r.as_dict() for r in b]


def test_rule_fields() -> None:
    ap = Apriori(0.2, 3).fit(toy())
    r = ap.rules(0.5)[0]
    assert r.antecedent and r.consequent
    assert r.antecedent | r.consequent in ap.frequent_itemsets_
