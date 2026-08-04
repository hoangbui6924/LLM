"""Kho tri thức + truy hồi lai (BM25 + dense).

Có chủ đích KHÔNG dùng vector DB ngoài (Qdrant/Chroma). Kho kiến thức THPT chỉ vài
trăm chunk — ở quy mô đó, numpy trong bộ nhớ nhanh hơn một lượt gọi mạng tới docker,
và bỏ được một nguồn hỏng hóc ngay trước hạn nộp.

Suy giảm êm: thiếu sentence-transformers hoặc tải model lỗi thì tự lùi về BM25-only
thay vì làm sập hệ thống.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np

from ..core.config import get_settings
from ..core.schemas import KnowledgeChunk, SolvedExample

DATA_DIR = Path(__file__).parent / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.jsonl"
EXAMPLES_FILE = DATA_DIR / "solved_examples.jsonl"


# ---------------------------------------------------------------------------
# Tách từ tiếng Việt cho BM25
# ---------------------------------------------------------------------------

_STOP = {
    "và", "của", "có", "là", "cho", "với", "trong", "một", "các", "được", "khi",
    "thì", "để", "này", "đó", "những", "bằng", "từ", "đến", "ở", "về", "sẽ", "đã",
}


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def tokenize(text: str) -> list[str]:
    """Sinh cả token có dấu lẫn không dấu.

    Lý do: học sinh gõ 'dao dong dieu hoa' không dấu rất nhiều, còn kho kiến thức
    thì viết có dấu. Đánh chỉ mục cả hai dạng là cách rẻ nhất để bắt được cả hai.
    """
    text = text.lower()
    toks = re.findall(r"[a-zà-ỹ0-9_]+", text)
    toks = [t for t in toks if t not in _STOP and len(t) > 1]
    out = list(toks)
    for t in toks:
        na = strip_accents(t)
        if na != t:
            out.append(na)
    return out


# ---------------------------------------------------------------------------
# BM25 (tự cài — rank_bm25 cũng được, nhưng 30 dòng thì không cần thêm phụ thuộc)
# ---------------------------------------------------------------------------


class BM25:
    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.corpus = corpus_tokens
        self.N = len(corpus_tokens)
        self.avgdl = sum(len(d) for d in corpus_tokens) / max(self.N, 1)
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for doc in corpus_tokens:
            freq: dict[str, int] = {}
            for t in doc:
                freq[t] = freq.get(t, 0) + 1
            self.tf.append(freq)
            for t in freq:
                self.df[t] = self.df.get(t, 0) + 1
        self.idf = {
            t: math.log(1 + (self.N - d + 0.5) / (d + 0.5)) for t, d in self.df.items()
        }

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        out = np.zeros(self.N, dtype=np.float32)
        for i, freq in enumerate(self.tf):
            dl = len(self.corpus[i])
            s = 0.0
            for t in query_tokens:
                f = freq.get(t)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out[i] = s
        return out


# ---------------------------------------------------------------------------
# Kho
# ---------------------------------------------------------------------------


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = float(x.min()), float(x.max())
    return np.zeros_like(x) if hi - lo < 1e-9 else (x - lo) / (hi - lo)


class KnowledgeStore:
    def __init__(self, use_dense: bool = True) -> None:
        self.s = get_settings()
        cfg = self.s.retrieval
        self.bm25_weight = float(cfg.get("bm25_weight", 0.4))
        self.chunks: list[KnowledgeChunk] = []
        self.examples: list[SolvedExample] = []
        self._bm25: BM25 | None = None
        self._ex_bm25: BM25 | None = None
        self._embedder: Any = None
        self._emb: np.ndarray | None = None
        self.backend = "bm25"

        self._load()
        if use_dense and self.chunks:
            self._try_dense(cfg.get("embedding_model", ""))

    # ---- nạp dữ liệu ----------------------------------------------------

    def _load(self) -> None:
        if KNOWLEDGE_FILE.exists():
            for line in KNOWLEDGE_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self.chunks.append(KnowledgeChunk(**json.loads(line)))
        if EXAMPLES_FILE.exists():
            for line in EXAMPLES_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self.examples.append(SolvedExample(**json.loads(line)))

        if self.chunks:
            self._bm25 = BM25([tokenize(self._chunk_text(c)) for c in self.chunks])
        if self.examples:
            self._ex_bm25 = BM25(
                [tokenize(e.problem + " " + e.solution_sketch) for e in self.examples]
            )

    @staticmethod
    def _chunk_text(c: KnowledgeChunk) -> str:
        return f"{c.title} {c.subtopic} {c.content} {c.applicable_when} {c.pitfalls}"

    def _try_dense(self, model_name: str) -> None:
        if not model_name:
            return
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._embedder = SentenceTransformer(model_name)
            texts = [self._chunk_text(c) for c in self.chunks]
            self._emb = np.asarray(
                self._embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )
            self.backend = "hybrid"
        except Exception as e:  # noqa: BLE001
            # Không chết vì thiếu embedding — BM25 vẫn dùng được.
            print(f"[KnowledgeStore] Dense tắt ({type(e).__name__}: {e}). Dùng BM25-only.")
            self._embedder = None
            self._emb = None
            self.backend = "bm25"

    # ---- truy hồi -------------------------------------------------------

    def search_knowledge(
        self, query: str, domain: str | None = None, subtopic: str | None = None, k: int = 4
    ) -> list[KnowledgeChunk]:
        if not self.chunks:
            return []

        scores = np.zeros(len(self.chunks), dtype=np.float32)
        if self._bm25 is not None:
            scores += self.bm25_weight * _minmax(self._bm25.scores(tokenize(query)))
        if self._emb is not None and self._embedder is not None:
            qv = np.asarray(
                self._embedder.encode([query], normalize_embeddings=True, show_progress_bar=False),
                dtype=np.float32,
            )[0]
            scores += (1.0 - self.bm25_weight) * _minmax(self._emb @ qv)

        # Lọc metadata quan trọng hơn vẻ ngoài của nó: nó chặn công thức Hoá
        # lọt vào bài Vật lý, thứ mà điểm tương đồng thuần tuý không chặn được.
        for i, c in enumerate(self.chunks):
            if domain and c.domain != domain:
                scores[i] *= 0.05
            elif subtopic and c.subtopic == subtopic:
                scores[i] *= 1.5

        idx = np.argsort(-scores)[:k]
        out: list[KnowledgeChunk] = []
        for i in idx:
            if scores[i] <= 0:
                continue
            c = self.chunks[int(i)].model_copy()
            c.score = float(scores[int(i)])
            out.append(c)
        return out

    def search_examples(
        self, query: str, domain: str | None = None, k: int = 2
    ) -> list[SolvedExample]:
        if not self.examples or self._ex_bm25 is None:
            return []
        scores = self._ex_bm25.scores(tokenize(query))
        for i, e in enumerate(self.examples):
            if domain and e.domain != domain:
                scores[i] *= 0.05
        idx = np.argsort(-scores)[:k]
        out: list[SolvedExample] = []
        for i in idx:
            if scores[i] <= 0:
                continue
            e = self.examples[int(i)].model_copy()
            e.score = float(scores[int(i)])
            out.append(e)
        return out

    # ---- ghi vào bộ nhớ -------------------------------------------------

    def add_example(self, ex: SolvedExample) -> None:
        """Chỉ gọi khi lời giải đã PASS verifier. Đây là cơ chế 'memory pool' của
        đề tài: hệ thống khá lên theo thời gian sử dụng mà không cần fine-tune."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(EXAMPLES_FILE, "a", encoding="utf-8") as f:
            f.write(ex.model_dump_json() + "\n")
        self.examples.append(ex)
        self._ex_bm25 = BM25(
            [tokenize(e.problem + " " + e.solution_sketch) for e in self.examples]
        )

    def stats(self) -> dict[str, Any]:
        return {
            "knowledge_chunks": len(self.chunks),
            "solved_examples": len(self.examples),
            "backend": self.backend,
        }


_STORE: KnowledgeStore | None = None


def get_store(use_dense: bool = True) -> KnowledgeStore:
    global _STORE
    if _STORE is None:
        _STORE = KnowledgeStore(use_dense=use_dense)
    return _STORE
