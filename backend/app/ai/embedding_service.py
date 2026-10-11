import os
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    return TextEmbedding(
        model_name=MODEL_NAME,
        cache_dir=os.getenv("FASTEMBED_CACHE_DIR") or None,
    )


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text")

    vector = np.asarray(next(iter(get_embedding_model().embed([text]))), dtype=float)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()