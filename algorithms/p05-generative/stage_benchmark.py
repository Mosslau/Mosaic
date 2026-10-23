"""p05 阶段横向对照（成本/质量/边界）

    uv run python stage_benchmark.py

VAE/DDPM/RAG 的任务不同，不能把 MSE/acc/Recall 硬排成一张榜；
这里在同一份 digits/小型语料上比较**参数量、训练/构建、采样/查询、质量代理**。
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

BASE = Path(__file__).resolve().parent


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BASE / rel)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def nparams(d):
    return int(sum(np.asarray(v).size for v in d.values()))


def main() -> None:
    vae_mod = load("p05_vae", "vae/impl.py")
    ddpm_mod = load("p05_ddpm", "mini-diffusion/impl.py")
    rag_impl = load("p05_rag", "mini-rag/impl.py")
    import sys
    sys.path.insert(0, str(BASE / "mini-rag"))
    rag_demo = load("p05_rag_demo", "mini-rag/demo.py")
    sys.path.pop(0)

    X, y = load_digits(return_X_y=True)
    X = X / 16.0
    Xtr, Xte, ytr, yte = train_test_split(X, y, train_size=1200, random_state=0,
                                          stratify=y)

    print("== p05 成本/质量/边界（不同任务，不能直接排名） ==\n")

    t0 = time.perf_counter()
    vae = vae_mod.VAE(latent_dim=2, beta=1.0, epochs=100, random_state=0).fit(Xtr)
    t_vae_train = time.perf_counter() - t0
    t0 = time.perf_counter()
    vae.sample(16)
    t_vae_sample = time.perf_counter() - t0
    vae_mse = float(np.mean((vae.reconstruct(Xte) - Xte) ** 2))

    t0 = time.perf_counter()
    ddpm = ddpm_mod.DDPM(n_steps=100, epochs=100, num_classes=10, hidden=128,
                         random_state=0)
    ddpm.train(Xtr, ytr)
    t_ddpm_train = time.perf_counter() - t0
    labels = np.tile(np.arange(10), 20)
    t0 = time.perf_counter()
    ds = ddpm.sample(200, labels=labels, guidance=3.0, seed=1)
    t_ddpm_sample = time.perf_counter() - t0
    clf = LogisticRegression(max_iter=5000).fit(Xtr, ytr)
    ddpm_acc = float((clf.predict(ds) == labels).mean())

    idx = rag_impl.Index(chunk_size=200, overlap=40)
    t0 = time.perf_counter()
    idx.build(rag_demo.DOCS)
    t_rag_build = time.perf_counter() - t0
    t0 = time.perf_counter()
    hits = [idx.search(q, 3) for q, _, _ in rag_demo.QUERIES]
    t_rag_query = time.perf_counter() - t0
    rec, mrr = [], []
    for h, (_, gold, _) in zip(hits, rag_demo.QUERIES):
        ids = [x.doc_id for x in h]
        rec.append(1.0 if gold in ids else 0.0)
        rank = next((i + 1 for i, d in enumerate(ids) if d == gold), None)
        mrr.append(1.0 / rank if rank else 0.0)

    print(f"{'方法':6} | {'参数/索引':>12} | {'训练/构建':>9} | {'采样/查询':>9} | 质量代理")
    print("-" * 86)
    print(f"{'VAE':6} | {nparams(vae.params):12d} | {t_vae_train * 1000:7.0f}ms | "
          f"{t_vae_sample * 1000:7.1f}ms | MSE {vae_mse:.4f}（2D latent）")
    print(f"{'DDPM':6} | {nparams(ddpm.net.params()):12d} | {t_ddpm_train * 1000:7.0f}ms | "
          f"{t_ddpm_sample * 1000:7.1f}ms | CFG acc {ddpm_acc:.3f}（w=3）")
    print(f"{'RAG':6} | {len(idx.chunks):5d} chunks/{idx.vectors.shape[1]:3d}d | "
          f"{t_rag_build * 1000:7.1f}ms | {t_rag_query * 1000:7.1f}ms | "
          f"Recall@3 {np.mean(rec):.3f}, MRR {np.mean(mrr):.3f}")

    print("\n== 边界 ==")
    print("- VAE：一步解码，采样 O(1)；2D latent 重构/生成模糊；"
          "KL 权重敏感（beta=4 会 collapse）。")
    print("- DDPM：100 步串行采样，成本高；条件/CFG 强；MLP/8×8 视觉仍模糊。")
    print("- RAG：不训练生成模型，知识在索引；依赖检索质量；本实验无 LLM，抽取式降级。")
    print("\n→ 三者不是同一任务：VAE 学 latent，DDPM 学去噪，RAG 学‘检索+组织上下文’。")


if __name__ == "__main__":
    main()
