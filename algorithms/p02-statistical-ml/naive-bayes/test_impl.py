"""朴素贝叶斯 — 性质测试（pytest）

用法（本目录内）：uv run pytest test_impl.py -q

覆盖：
- 词袋：词表、计数、binary、min_df、未知词忽略
- 多项式 NB：先验、平滑后的条件概率、概率归一、与 sklearn 对齐
- alpha=0 的零概率（log −inf）；alpha>0 有限
- 高斯 NB：均值/方差、概率、与 sklearn 对齐
- 条件独立被违反时后验更极端
- 契约
"""

import numpy as np
import pytest
from impl import CountVectorizer, GaussianNB, MultinomialNB


def blobs(n=200, seed=0):
    from sklearn.datasets import make_blobs
    from sklearn.model_selection import train_test_split
    X, y = make_blobs(n_samples=n, centers=2, cluster_std=1.2, random_state=seed)
    return train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)


def test_vectorizer() -> None:
    docs = ["good good bad", "good", "bad bad"]
    vec = CountVectorizer().fit(docs)
    assert set(vec.vocabulary_) == {"good", "bad"}
    X = vec.transform(docs)
    assert X.shape == (3, 2)
    assert X[0, vec.vocabulary_["good"]] == 2
    assert X[1, vec.vocabulary_["bad"]] == 0
    binary = CountVectorizer(binary=True).fit_transform(docs)
    assert binary[0, vec.vocabulary_["good"]] == 1
    with pytest.raises(RuntimeError):
        CountVectorizer().transform(["x"])


def test_min_df_and_unknown() -> None:
    docs = ["a a b", "a c"]
    vec = CountVectorizer(min_df=2).fit(docs)
    assert vec.vocabulary_ == {"a": 0}
    X = vec.transform(["a zzz"])
    assert X.tolist() == [[1.0]]


def test_multinomial_priors_and_smoothing() -> None:
    X = np.array([[2.0, 0.0], [0.0, 2.0]])
    y = np.array(["A", "B"])
    nb = MultinomialNB(alpha=1.0).fit(X, y)
    assert nb.class_log_prior_[0] == pytest.approx(np.log(0.5))
    # A 类：平滑后 [3,1]/4；B 类：[1,3]/4
    assert np.exp(nb.feature_log_prob_[0, 0]) == pytest.approx(0.75)
    assert np.exp(nb.feature_log_prob_[0, 1]) == pytest.approx(0.25)
    assert np.exp(nb.feature_log_prob_[1, 1]) == pytest.approx(0.75)
    assert nb.predict(np.array([[1.0, 0.0]]))[0] == "A"


def test_multinomial_matches_sklearn() -> None:
    from framework import fit_multinomial
    docs, labels = [], []
    rng = np.random.default_rng(0)
    for i in range(60):
        label = i % 2
        words = ["good"] * rng.integers(1, 4) + ["bad"] * rng.integers(0, 3)
        if label == 1:
            words = ["bad"] * rng.integers(1, 4) + ["good"] * rng.integers(0, 3)
        docs.append(" ".join(words))
        labels.append(label)
    vec = CountVectorizer().fit(docs)
    X, y = vec.transform(docs), np.array(labels)
    hand = MultinomialNB(alpha=1.0).fit(X, y)
    sk = fit_multinomial(X, y, alpha=1.0)
    np.testing.assert_allclose(hand.predict_proba(X), sk.predict_proba(X), atol=1e-8)
    np.testing.assert_array_equal(hand.predict(X), sk.predict(X))


def test_alpha_zero_zero_probability() -> None:
    X = np.array([[2.0, 0.0], [0.0, 2.0]])
    y = np.array([0, 1])
    nb = MultinomialNB(alpha=0.0).fit(X, y)
    assert np.isneginf(nb.feature_log_prob_[0, 1])
    smoothed = MultinomialNB(alpha=1.0).fit(X, y)
    assert np.isfinite(smoothed.feature_log_prob_[0, 1])


def test_alpha_zero_all_unseen_posterior_uniform() -> None:
    X = np.array([[2.0, 0.0], [0.0, 2.0]])
    y = np.array([0, 1])
    nb = MultinomialNB(alpha=0.0).fit(X, y)
    proba = nb.predict_proba(np.array([[1.0, 1.0]]))   # 两类都各有一个未见词
    assert np.isfinite(proba).all()
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)
    np.testing.assert_allclose(proba[0], [0.5, 0.5])


def test_multinomial_proba_normalized() -> None:
    X = np.array([[2.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
    y = np.array(["A", "B", "A"])
    nb = MultinomialNB(alpha=0.5).fit(X, y)
    proba = nb.predict_proba(X)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)
    assert proba.min() > 0


def test_gaussian_matches_sklearn() -> None:
    from framework import fit_gaussian
    X_tr, X_te, y_tr, y_te = blobs()
    hand = GaussianNB().fit(X_tr, y_tr)
    sk = fit_gaussian(X_tr, y_tr)
    np.testing.assert_allclose(hand.predict_proba(X_te), sk.predict_proba(X_te), atol=1e-8)
    np.testing.assert_array_equal(hand.predict(X_te), sk.predict(X_te))


def test_gaussian_duplicate_feature_overconfident() -> None:
    X_tr, X_te, y_tr, y_te = blobs()
    base = GaussianNB().fit(X_tr, y_tr)
    dup = GaussianNB().fit(np.hstack([X_tr] * 3), y_tr)
    c1 = float(np.mean(base.predict_proba(X_te).max(axis=1)))
    c2 = float(np.mean(dup.predict_proba(np.hstack([X_te] * 3)).max(axis=1)))
    assert c2 > c1


def test_invalid_inputs() -> None:
    X_tr, X_te, y_tr, _ = blobs()
    with pytest.raises(ValueError):
        MultinomialNB(alpha=-1)
    with pytest.raises(ValueError):
        MultinomialNB().fit(np.array([[-1.0, 1.0]]), np.array([0]))
    with pytest.raises(ValueError):
        MultinomialNB().fit(X_tr, y_tr[:-1])
    with pytest.raises(ValueError):
        GaussianNB().fit(X_tr[:, 0], y_tr)
    with pytest.raises(ValueError):
        GaussianNB().fit(X_tr, y_tr[:-1])
    with pytest.raises(ValueError):
        CountVectorizer(min_df=0)


def test_predict_before_fit() -> None:
    with pytest.raises((RuntimeError, AttributeError)):
        MultinomialNB().predict(np.ones((3, 2)))
