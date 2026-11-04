import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


def detect_coordinated_groups(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    sim_threshold: float = 0.85,
    time_window_sec: int = 300,
) -> list[dict]:
    if df.empty or len(df) < 2:
        return []

    sim_matrix = cosine_similarity(embeddings)
    records = df.to_dict("records")
    G = nx.Graph()
    n = len(records)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = records[i], records[j]
            if a["author_handle"] == b["author_handle"]:
                continue

            reasons = []
            sim_score = float(sim_matrix[i, j])

            # 1. Near-identical text
            if sim_score >= sim_threshold:
                reasons.append(f"Near-identical text (cosine sim: {sim_score:.2f})")

            # 2. Posting within minutes of each other
            if pd.notna(a["timestamp_dt"]) and pd.notna(b["timestamp_dt"]):
                delta_sec = abs((a["timestamp_dt"] - b["timestamp_dt"]).total_seconds())
                if delta_sec <= time_window_sec and (
                    sim_score >= 0.65 or a["narrative_id"] == b["narrative_id"]
                ):
                    reasons.append(f"Synchronized posting ({int(delta_sec)}s apart)")

            # 3. Accounts created around the same time (<= 24 hours)
            if pd.notna(a["author_created_dt"]) and pd.notna(b["author_created_dt"]):
                create_delta = abs(
                    (a["author_created_dt"] - b["author_created_dt"]).total_seconds()
                )
                if create_delta <= 86400 and sim_score >= 0.60:
                    reasons.append(
                        f"Batch account creation ({int(create_delta // 60)}m apart)"
                    )
            # 4. Reused profile photos
            if a.get("avatar_hash") and a.get("avatar_hash") == b.get("avatar_hash"):
                reasons.append(f"Reused profile photo (hash: {a['avatar_hash']})")

            # 5. Amplifying each other
            if (
                a.get("amplified_handle") == b["author_handle"]
                or b.get("amplified_handle") == a["author_handle"]
                or (
                    a.get("amplified_handle")
                    and a.get("amplified_handle") == b.get("amplified_handle")
                )
            ):
                target = a.get("amplified_handle") or b.get("amplified_handle")
                reasons.append(f"Coordinated amplification (target: {target})")

            # Require >= 2 signals OR very high text match to suppress false positives
            if len(reasons) >= 2 or sim_score >= 0.92:
                u, v = a["author_handle"], b["author_handle"]
                if G.has_edge(u, v):
                    G[u][v]["reasons"].update(reasons)
                else:
                    G.add_edge(u, v, reasons=set(reasons))
    coordinated_groups = []
    for idx, comp in enumerate(nx.connected_components(G), start=1):
        subG = G.subgraph(comp)
        group_reasons = set()
        for _, _, edge_data in subG.edges(data=True):
            group_reasons.update(edge_data["reasons"])

        member_posts = df[df["author_handle"].isin(comp)]
        platforms_used = sorted(member_posts["platform"].unique().tolist())
        confidence = min(99, 35 + 15 * len(group_reasons) + 5 * len(comp))

        coordinated_groups.append(
            {
                "group_id": f"COORD-RING-{idx:02d}",
                "confidence_score": f"{confidence}/100",
                "account_count": len(comp),
                "accounts": sorted(list(comp)),
                "platforms": platforms_used,
                "post_count": int(len(member_posts)),
                "reasons": sorted(list(group_reasons)),
            }
        )

    return sorted(coordinated_groups, key=lambda x: x["account_count"], reverse=True)
