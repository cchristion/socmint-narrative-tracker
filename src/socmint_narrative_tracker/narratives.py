from sentence_transformers import SentenceTransformer


_MODEL = None

def get_embedder() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL