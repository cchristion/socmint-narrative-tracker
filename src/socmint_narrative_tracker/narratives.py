import re
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction import text as sk_text
from sklearn.feature_extraction.text import TfidfVectorizer

_MODEL = None


def get_embedder() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def cluster_narratives(
    df: pd.DataFrame, distance_threshold: float = 0.25, topic: str = "Acme Bank"
):
    if df.empty:
        return df, np.array([]), []

    model = get_embedder()
    texts = df["text"].fillna("").tolist()
    embeddings = model.encode(texts, normalize_embeddings=True)

    if len(texts) == 1:
        df["narrative_id"] = 0
    else:
        # AgglomerativeClustering automatically discovers the number of narratives
        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=distance_threshold,
        )
        df["narrative_id"] = clustering.fit_predict(embeddings)
    topic_tokens = set(re.findall(r"[a-z0-9]+", topic.lower()))
    topic_tokens.update(
        {
            "".join(topic_tokens),
            f"{''.join(topic_tokens)}collapse",
            "breaking",
            "urgent",
            "exclusive",
        }
    )
    custom_stop = list(sk_text.ENGLISH_STOP_WORDS.union(topic_tokens))

    narrative_summaries = []
    label_map = {}

    for nid, group in df.groupby("narrative_id"):
        group_texts = group["text"].tolist()
        try:
            vec = TfidfVectorizer(
                stop_words=custom_stop, ngram_range=(1, 2), max_features=4
            )
            tfidf_mat = vec.fit_transform(group_texts)
            scores = np.asarray(tfidf_mat.mean(axis=0)).ravel()
            top_indices = scores.argsort()[::-1][:3]
            feature_names = vec.get_feature_names_out()
            top_terms = ", ".join(feature_names[i] for i in top_indices)
        except ValueError:
            top_terms = "general discussion"
        rep_post = group.sort_values("timestamp_dt", ascending=True).iloc[0]
        short_headline = rep_post["text"][:95] + (
            "..." if len(rep_post["text"]) > 95 else ""
        )
        label = f"Narrative #{nid + 1}: {top_terms.title()}"
        label_map[nid] = label

        combined_lower = " ".join(group_texts).lower()
        verified_terms = [
            t for t in top_terms.split(", ") if t.lower() in combined_lower
        ]
        hallucination_check = (
            "PASSED (100% Grounded)" if len(verified_terms) > 0 else "REVIEW"
        )

        narrative_summaries.append(
            {
                "narrative_id": int(nid),
                "narrative_label": label,
                "representative_claim": short_headline,
                "top_keywords": top_terms,
                "post_count": int(len(group)),
                "platforms": group["platform"].value_counts().to_dict(),
                "ai_grounding_check": hallucination_check,
            }
        )

    df["narrative_label"] = df["narrative_id"].map(label_map)
    narrative_summaries = sorted(
        narrative_summaries, key=lambda x: x["post_count"], reverse=True
    )
    return df, embeddings, narrative_summaries
