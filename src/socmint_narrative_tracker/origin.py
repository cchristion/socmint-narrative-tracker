import pandas as pd


def trace_narrative_origins(df: pd.DataFrame) -> list[dict]:
    origins = []
    if df.empty or "narrative_id" not in df.columns:
        return origins

    for nid, group in df.groupby("narrative_id"):
        sorted_g = group.sort_values("timestamp_dt", ascending=True)
        first = sorted_g.iloc[0]
        t0 = first["timestamp_dt"]
        plat_first = sorted_g.groupby("platform")["timestamp_dt"].min().sort_values()
        spread_chain = []
        for plat, ts in plat_first.items():
            lag_mins = int((ts - t0).total_seconds() // 60)
            first_plat_author = sorted_g[sorted_g["platform"] == plat].iloc[0][
                "author_handle"
            ]
            spread_chain.append(f"{plat} ({first_plat_author} at +{lag_mins}m)")
        origins.append(
            {
                "narrative_id": int(nid),
                "narrative_label": first.get(
                    "narrative_label", f"Narrative #{nid + 1}"
                ),
                "origin_platform": first["platform"],
                "origin_account": first["author_handle"],
                "origin_timestamp": first["timestamp"],
                "origin_post_id": first["post_id"],
                "origin_link": first["link"],
                "origin_text": first["text"],
                "cross_platform_spread": " -> ".join(spread_chain),
            }
        )

    return sorted(origins, key=lambda x: x["origin_timestamp"])
