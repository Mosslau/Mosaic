"""参考解：第 4 题——support/confidence"""



def support(trans, itemset):
    return sum(1 for t in trans if itemset <= t) / len(trans)


def main() -> None:
    trans = [{"a", "b"}, {"a", "b", "c"}, {"a", "c"}, {"b", "c"}, {"a", "b", "c", "d"}]
    ab = frozenset({"a", "b"})
    a = frozenset({"a"})
    b = frozenset({"b"})
    s = support(trans, ab)
    conf = s / support(trans, a)
    lift = conf / support(trans, b)
    print(s, conf, lift)
    assert abs(s - .6) < 1e-12 and abs(conf - .75) < 1e-12


if __name__ == "__main__":
    main()
